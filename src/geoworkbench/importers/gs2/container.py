from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import zipfile


_DATA_FILE = re.compile(r"^GS2#.+\.db$", re.IGNORECASE)
_MULTIPART_FILE = re.compile(
    r"^(?P<base>GS2#\d+)(?:_(?P<part>\d+))?\.db$",
    re.IGNORECASE,
)
_COPY_CHUNK_SIZE = 1024 * 1024


class Gs2ContainerError(ValueError):
    """Raised when a source is not a safe GeoScape II container."""


@dataclass(frozen=True, slots=True)
class Gs2ContainerLimits:
    max_members: int = 10_000
    max_member_size: int = 2 * 1024**3
    max_uncompressed_size: int = 8 * 1024**3
    # Sparse GeoScape tables can legitimately compress above 500:1. Absolute
    # member and total-size limits remain the primary zip-bomb boundary.
    max_compression_ratio: float = 1_000.0


@dataclass(frozen=True, slots=True)
class Gs2Member:
    name: str
    size: int
    compressed_size: int
    crc: int


@dataclass(frozen=True, slots=True)
class Gs2TableSummary:
    member_name: str
    record_count: int
    record_size: int
    header_size: int
    field_names: tuple[str, ...]
    field_types: tuple[int, ...]
    field_sizes: tuple[int, ...]

    @property
    def field_count(self) -> int:
        return len(self.field_names)

    @property
    def has_depth(self) -> bool:
        return any(name.casefold() == "depth" for name in self.field_names)

    @property
    def has_time(self) -> bool:
        return any(name.casefold() == "time" for name in self.field_names)


@dataclass(frozen=True, slots=True)
class Gs2MultipartSummary:
    base_name: str
    member_names: tuple[str, ...]
    record_count: int
    field_names: tuple[str, ...]

    @property
    def field_count(self) -> int:
        return len(self.field_names)

    @property
    def has_depth(self) -> bool:
        return any(name.casefold() == "depth" for name in self.field_names)

    @property
    def has_time(self) -> bool:
        return any(name.casefold() == "time" for name in self.field_names)


@dataclass(frozen=True, slots=True)
class Gs2ContainerManifest:
    source: Path
    metadata_member: Gs2Member
    data_members: tuple[Gs2Member, ...]
    members: tuple[Gs2Member, ...]
    uncompressed_size: int
    compressed_size: int
    tables: tuple[Gs2TableSummary, ...] = ()

    @property
    def preferred_table(self) -> Gs2TableSummary | None:
        if not self.tables:
            return None
        return max(
            self.tables,
            key=lambda table: (
                table.has_depth,
                table.field_count,
                table.record_count,
            ),
        )

    @property
    def multipart_groups(self) -> tuple[Gs2MultipartSummary, ...]:
        tables_by_name = {
            table.member_name.casefold(): table for table in self.tables
        }
        grouped: dict[str, list[tuple[int, Gs2TableSummary]]] = {}
        for table in self.tables:
            match = _MULTIPART_FILE.fullmatch(
                PurePosixPath(table.member_name).name
            )
            if match is None:
                continue
            base = match.group("base")
            part_text = match.group("part")
            part = int(part_text) if part_text is not None else 0
            grouped.setdefault(base.casefold(), []).append((part, table))

        summaries: list[Gs2MultipartSummary] = []
        for base_key, parts in grouped.items():
            if len(parts) < 2 or 0 not in {part for part, _table in parts}:
                continue
            ordered = sorted(parts, key=lambda item: item[0])
            expected_parts = list(range(len(ordered)))
            if [part for part, _table in ordered] != expected_parts:
                continue
            first = ordered[0][1]
            if any(
                table.field_names != first.field_names
                or table.field_types != first.field_types
                or table.field_sizes != first.field_sizes
                or table.record_size != first.record_size
                for _part, table in ordered[1:]
            ):
                continue
            if not first.has_time:
                continue
            base_name = PurePosixPath(first.member_name).stem
            summaries.append(
                Gs2MultipartSummary(
                    base_name=base_name,
                    member_names=tuple(
                        table.member_name for _part, table in ordered
                    ),
                    record_count=sum(
                        tables_by_name[table.member_name.casefold()].record_count
                        for _part, table in ordered
                    ),
                    field_names=first.field_names,
                )
            )
        return tuple(
            sorted(summaries, key=lambda group: group.base_name.casefold())
        )


def _safe_member_name(raw_name: str) -> str:
    name = raw_name.replace("\\", "/")
    path = PurePosixPath(name)
    if (
        not name
        or name.startswith("/")
        or path.is_absolute()
        or ".." in path.parts
        or any(":" in part for part in path.parts)
    ):
        raise Gs2ContainerError(f"Небезопасный путь внутри GS2: {raw_name!r}")
    return path.as_posix()


def inspect_gs2(
    source: str | Path,
    *,
    limits: Gs2ContainerLimits | None = None,
) -> Gs2ContainerManifest:
    """Validate and inventory a GeoScape II ZIP container without extracting it."""

    path = Path(source).expanduser().resolve()
    safety = limits or Gs2ContainerLimits()
    try:
        if not path.is_file():
            raise Gs2ContainerError(f"Файл GS2 не найден: {path}")
        if not zipfile.is_zipfile(path):
            raise Gs2ContainerError("Файл не содержит ZIP-сигнатуру GeoScape II")
        with zipfile.ZipFile(path, "r") as archive:
            infos = archive.infolist()
            if len(infos) > safety.max_members:
                raise Gs2ContainerError(
                    f"Слишком много элементов в GS2: {len(infos)} > {safety.max_members}"
                )

            members: list[Gs2Member] = []
            normalized_names: set[str] = set()
            total_size = 0
            total_compressed = 0
            for info in infos:
                name = _safe_member_name(info.filename)
                folded = name.casefold()
                if folded in normalized_names:
                    raise Gs2ContainerError(f"Повторяющийся путь внутри GS2: {name}")
                normalized_names.add(folded)
                if info.flag_bits & 0x1:
                    raise Gs2ContainerError(f"Зашифрованный элемент GS2 не поддерживается: {name}")
                if info.is_dir():
                    continue
                if info.file_size > safety.max_member_size:
                    raise Gs2ContainerError(
                        f"Элемент GS2 превышает лимит размера: {name}"
                    )
                ratio = info.file_size / max(1, info.compress_size)
                if ratio > safety.max_compression_ratio:
                    raise Gs2ContainerError(
                        f"Подозрительно высокий коэффициент сжатия GS2: {name}"
                    )
                total_size += info.file_size
                total_compressed += info.compress_size
                if total_size > safety.max_uncompressed_size:
                    raise Gs2ContainerError("Распакованный GS2 превышает безопасный лимит")
                members.append(
                    Gs2Member(
                        name=name,
                        size=info.file_size,
                        compressed_size=info.compress_size,
                        crc=info.CRC,
                    )
                )
    except Gs2ContainerError:
        raise
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise Gs2ContainerError(f"Не удалось прочитать контейнер GS2: {exc}") from exc

    metadata = tuple(
        member
        for member in members
        if PurePosixPath(member.name).name.casefold() == "gs2.mdb"
    )
    if len(metadata) != 1:
        raise Gs2ContainerError(
            "Контейнер GS2 должен содержать ровно один файл GS2.mdb"
        )
    data_members = tuple(
        member
        for member in members
        if _DATA_FILE.fullmatch(PurePosixPath(member.name).name)
    )
    if not data_members:
        raise Gs2ContainerError("В контейнере не найдены массивы GS2#*.db")
    tables: list[Gs2TableSummary] = []
    try:
        with zipfile.ZipFile(path, "r") as archive:
            info_by_name = {
                _safe_member_name(info.filename).casefold(): info
                for info in archive.infolist()
                if not info.is_dir()
            }
            for member in data_members:
                info = info_by_name[member.name.casefold()]
                summary = _inspect_paradox_table(archive, info, member.name)
                if summary is not None:
                    tables.append(summary)
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise Gs2ContainerError(f"Не удалось проверить таблицы GS2: {exc}") from exc
    return Gs2ContainerManifest(
        source=path,
        metadata_member=metadata[0],
        data_members=data_members,
        members=tuple(members),
        uncompressed_size=total_size,
        compressed_size=total_compressed,
        tables=tuple(tables),
    )


def _inspect_paradox_table(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    member_name: str,
) -> Gs2TableSummary | None:
    with archive.open(info, "r") as stream:
        fixed = stream.read(0x78)
        if len(fixed) < 0x78:
            return None
        record_size = int.from_bytes(fixed[0:2], "little")
        header_size = int.from_bytes(fixed[2:4], "little")
        file_type = fixed[4]
        record_count = int.from_bytes(fixed[6:10], "little")
        field_count = int.from_bytes(fixed[0x21:0x23], "little")
        if (
            record_size <= 0
            or not 0x78 <= header_size <= min(info.file_size, 16 * 1024 * 1024)
            or file_type not in {0, 2, 3, 4, 5, 6, 7, 8}
            or not 1 <= field_count <= 4096
        ):
            return None
        remainder = stream.read(header_size - len(fixed))
    header = fixed + remainder
    schema_start = 0x78
    schema_end = schema_start + field_count * 2
    if len(header) < schema_end:
        return None
    field_types = tuple(
        header[schema_start + 2 * index] for index in range(field_count)
    )
    field_sizes = tuple(
        header[schema_start + 2 * index + 1] for index in range(field_count)
    )
    if sum(field_sizes) != record_size:
        return None
    marker = b"".join(
        ordinal.to_bytes(2, "little") for ordinal in range(1, field_count + 1)
    )
    marker_position = header.find(marker, schema_end)
    if marker_position < 0:
        return None
    chunks = [
        chunk
        for chunk in header[schema_end:marker_position].split(b"\x00")
        if chunk
    ]
    if len(chunks) < field_count:
        return None
    names = tuple(
        chunk.decode("cp1252", errors="replace").strip()
        for chunk in chunks[-field_count:]
    )
    return Gs2TableSummary(
        member_name=member_name,
        record_count=record_count,
        record_size=record_size,
        header_size=header_size,
        field_names=names,
        field_types=field_types,
        field_sizes=field_sizes,
    )


@contextmanager
def extract_gs2(
    source: str | Path,
    *,
    limits: Gs2ContainerLimits | None = None,
) -> Iterator[tuple[Path, Gs2ContainerManifest]]:
    """Safely extract a validated container into an automatically removed directory."""

    manifest = inspect_gs2(source, limits=limits)
    with tempfile.TemporaryDirectory(prefix="geoworkbench-gs2-") as temporary:
        destination = Path(temporary)
        try:
            with zipfile.ZipFile(manifest.source, "r") as archive:
                for info in archive.infolist():
                    relative = PurePosixPath(_safe_member_name(info.filename))
                    target = destination.joinpath(*relative.parts)
                    if info.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info, "r") as reader, target.open("wb") as writer:
                        shutil.copyfileobj(reader, writer, length=_COPY_CHUNK_SIZE)
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            raise Gs2ContainerError(f"Не удалось распаковать контейнер GS2: {exc}") from exc
        yield destination, manifest


@contextmanager
def extract_gs2_table(
    source: str | Path,
    member_name: str,
    *,
    limits: Gs2ContainerLimits | None = None,
) -> Iterator[tuple[Path, Gs2ContainerManifest]]:
    """Extract one validated Paradox table for the existing import pipeline."""

    manifest = inspect_gs2(source, limits=limits)
    selected = next(
        (
            member
            for member in manifest.data_members
            if member.name.casefold() == member_name.casefold()
        ),
        None,
    )
    if selected is None:
        raise Gs2ContainerError(f"Таблица отсутствует в контейнере GS2: {member_name}")
    with tempfile.TemporaryDirectory(prefix="geoworkbench-gs2-table-") as temporary:
        destination = Path(temporary)
        target = destination / PurePosixPath(selected.name).name
        try:
            with zipfile.ZipFile(manifest.source, "r") as archive:
                info = next(
                    info
                    for info in archive.infolist()
                    if _safe_member_name(info.filename).casefold()
                    == selected.name.casefold()
                )
                with archive.open(info, "r") as reader, target.open("wb") as writer:
                    shutil.copyfileobj(reader, writer, length=_COPY_CHUNK_SIZE)
        except (OSError, zipfile.BadZipFile, RuntimeError, StopIteration) as exc:
            raise Gs2ContainerError(f"Не удалось извлечь таблицу GS2: {exc}") from exc
        yield target, manifest


@contextmanager
def extract_gs2_metadata(
    source: str | Path,
    *,
    limits: Gs2ContainerLimits | None = None,
) -> Iterator[tuple[Path, Gs2ContainerManifest]]:
    """Extract only ``GS2.mdb`` for the replaceable Access metadata adapter."""

    manifest = inspect_gs2(source, limits=limits)
    selected = manifest.metadata_member
    with tempfile.TemporaryDirectory(prefix="geoworkbench-gs2-metadata-") as temporary:
        destination = Path(temporary)
        target = destination / PurePosixPath(selected.name).name
        try:
            with zipfile.ZipFile(manifest.source, "r") as archive:
                info = next(
                    info
                    for info in archive.infolist()
                    if not info.is_dir()
                    and _safe_member_name(info.filename).casefold()
                    == selected.name.casefold()
                )
                with archive.open(info, "r") as reader, target.open("wb") as writer:
                    shutil.copyfileobj(reader, writer, length=_COPY_CHUNK_SIZE)
        except (OSError, zipfile.BadZipFile, RuntimeError, StopIteration) as exc:
            raise Gs2ContainerError(f"Не удалось извлечь GS2.mdb: {exc}") from exc
        yield target, manifest


@contextmanager
def extract_gs2_tables(
    source: str | Path,
    member_names: tuple[str, ...],
    *,
    limits: Gs2ContainerLimits | None = None,
    progress: Callable[[str, int, int], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> Iterator[tuple[tuple[Path, ...], Gs2ContainerManifest]]:
    """Extract a validated ordered set of inner tables into one temporary directory."""

    if not member_names:
        raise Gs2ContainerError("Не выбраны таблицы GS2 для извлечения")
    manifest = inspect_gs2(source, limits=limits)
    available = {
        member.name.casefold(): member for member in manifest.data_members
    }
    selected: list[Gs2Member] = []
    for member_name in member_names:
        member = available.get(member_name.casefold())
        if member is None:
            raise Gs2ContainerError(
                f"Таблица отсутствует в контейнере GS2: {member_name}"
            )
        selected.append(member)
    if len({member.name.casefold() for member in selected}) != len(selected):
        raise Gs2ContainerError("Список таблиц GS2 содержит дубликаты")

    with tempfile.TemporaryDirectory(prefix="geoworkbench-gs2-tables-") as temporary:
        destination = Path(temporary)
        targets: list[Path] = []
        extracted_size = 0
        total_size = sum(member.size for member in selected)
        if progress is not None:
            progress("extract", 0, total_size)
        try:
            with zipfile.ZipFile(manifest.source, "r") as archive:
                info_by_name = {
                    _safe_member_name(info.filename).casefold(): info
                    for info in archive.infolist()
                    if not info.is_dir()
                }
                for member in selected:
                    if cancelled is not None and cancelled():
                        raise Gs2ContainerError(
                            "Извлечение таблиц GS2 отменено пользователем"
                        )
                    info = info_by_name[member.name.casefold()]
                    target = destination / PurePosixPath(member.name).name
                    with archive.open(info, "r") as reader, target.open("wb") as writer:
                        while True:
                            if cancelled is not None and cancelled():
                                raise Gs2ContainerError(
                                    "Извлечение таблиц GS2 отменено пользователем"
                                )
                            chunk = reader.read(_COPY_CHUNK_SIZE)
                            if not chunk:
                                break
                            writer.write(chunk)
                            extracted_size += len(chunk)
                            if progress is not None:
                                progress("extract", extracted_size, total_size)
                    targets.append(target)
        except Gs2ContainerError:
            raise
        except (KeyError, OSError, zipfile.BadZipFile, RuntimeError) as exc:
            raise Gs2ContainerError(
                f"Не удалось извлечь таблицы GS2: {exc}"
            ) from exc
        yield tuple(targets), manifest
