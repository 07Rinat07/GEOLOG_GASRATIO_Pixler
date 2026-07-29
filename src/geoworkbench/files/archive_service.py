from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import importlib
import importlib.util
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile
from typing import Any, Iterable, Iterator
import zipfile


class ArchiveError(RuntimeError):
    pass


class ArchiveFormat(StrEnum):
    ZIP = "zip"
    SEVEN_Z = "7z"
    TAR = "tar"
    TAR_GZ = "tar.gz"
    TAR_BZ2 = "tar.bz2"
    TAR_XZ = "tar.xz"
    RAR = "rar"


@dataclass(frozen=True, slots=True)
class ArchiveCapability:
    archive_format: ArchiveFormat
    can_create: bool
    can_extract: bool
    explanation: str = ""


@dataclass(frozen=True, slots=True)
class ArchiveEntry:
    name: str
    size: int
    is_directory: bool


class ArchiveService:
    """Create and securely extract common archives.

    ZIP and TAR-family formats use the Python standard library. 7Z and RAR are
    optional: the service discovers ``py7zr``/``rarfile`` or an installed
    7-Zip/WinRAR/RAR executable without making them mandatory at application
    startup.
    """

    MAX_MEMBERS = 50_000
    MAX_TOTAL_BYTES = 20 * 1024 * 1024 * 1024
    MAX_SINGLE_BYTES = 5 * 1024 * 1024 * 1024

    def capabilities(self) -> tuple[ArchiveCapability, ...]:
        seven_create = self._py7zr() is not None or self._find_7z() is not None
        seven_extract = seven_create
        rar_creator = self._find_rar_creator()
        rar_extract = self._rarfile() is not None or self._find_rar_extractor() is not None
        return (
            ArchiveCapability(ArchiveFormat.ZIP, True, True),
            ArchiveCapability(ArchiveFormat.SEVEN_Z, seven_create, seven_extract, self._optional_note(seven_create, "7-Zip/py7zr")),
            ArchiveCapability(ArchiveFormat.TAR, True, True),
            ArchiveCapability(ArchiveFormat.TAR_GZ, True, True),
            ArchiveCapability(ArchiveFormat.TAR_BZ2, True, True),
            ArchiveCapability(ArchiveFormat.TAR_XZ, True, True),
            ArchiveCapability(
                ArchiveFormat.RAR,
                rar_creator is not None,
                rar_extract,
                self._optional_note(
                    rar_creator is not None or rar_extract,
                    "WinRAR/RAR/UnRAR или rarfile",
                ),
            ),
        )

    def create(
        self,
        output_path: Path,
        sources: Iterable[Path],
        archive_format: ArchiveFormat,
    ) -> Path:
        paths = tuple(Path(item).resolve() for item in sources)
        if not paths:
            raise ArchiveError("Не выбраны файлы или папки")
        for path in paths:
            if not path.exists():
                raise ArchiveError(f"Источник не найден: {path}")
            if path.is_symlink():
                raise ArchiveError(f"Символические ссылки не архивируются: {path}")

        output = self._with_archive_suffix(Path(output_path).resolve(), archive_format)
        output.parent.mkdir(parents=True, exist_ok=True)
        for source in paths:
            if output == source or (source.is_dir() and self._is_relative_to(output, source)):
                raise ArchiveError("Результирующий архив не должен находиться внутри источника")

        temporary = output.with_name(f".{output.name}.tmp")
        temporary.unlink(missing_ok=True)
        try:
            if archive_format is ArchiveFormat.ZIP:
                self._create_zip(temporary, paths)
            elif archive_format is ArchiveFormat.SEVEN_Z:
                self._create_7z(temporary, paths)
            elif archive_format in {
                ArchiveFormat.TAR,
                ArchiveFormat.TAR_GZ,
                ArchiveFormat.TAR_BZ2,
                ArchiveFormat.TAR_XZ,
            }:
                self._create_tar(temporary, paths, archive_format)
            elif archive_format is ArchiveFormat.RAR:
                self._create_rar(temporary, paths)
            else:
                raise ArchiveError(f"Формат не поддерживается: {archive_format}")
            temporary.replace(output)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return output

    def list_entries(self, archive_path: Path) -> tuple[ArchiveEntry, ...]:
        path = Path(archive_path).resolve()
        if not path.is_file():
            raise ArchiveError(f"Архив не найден: {path}")
        archive_format = self.detect_format(path)
        try:
            if archive_format is ArchiveFormat.ZIP:
                with zipfile.ZipFile(path) as archive:
                    entries = tuple(
                        ArchiveEntry(item.filename, item.file_size, item.is_dir())
                        for item in archive.infolist()
                    )
            elif archive_format in {
                ArchiveFormat.TAR,
                ArchiveFormat.TAR_GZ,
                ArchiveFormat.TAR_BZ2,
                ArchiveFormat.TAR_XZ,
            }:
                with tarfile.open(path, "r:*") as archive:
                    entries = tuple(
                        ArchiveEntry(item.name, item.size, item.isdir())
                        for item in archive.getmembers()
                    )
            elif archive_format is ArchiveFormat.SEVEN_Z:
                entries = self._list_7z(path)
            elif archive_format is ArchiveFormat.RAR:
                entries = self._list_rar(path)
            else:
                raise ArchiveError("Формат архива не распознан")
        except (OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
            raise ArchiveError(f"Не удалось прочитать архив: {exc}") from exc
        self._validate_entries(entries)
        return entries

    def extract(self, archive_path: Path, destination: Path) -> tuple[Path, ...]:
        source = Path(archive_path).resolve()
        if not source.is_file():
            raise ArchiveError(f"Архив не найден: {source}")
        destination = Path(destination).resolve()
        destination.mkdir(parents=True, exist_ok=True)
        archive_format = self.detect_format(source)
        with tempfile.TemporaryDirectory(prefix="geoworkbench-extract-") as temporary:
            staging = Path(temporary) / "payload"
            staging.mkdir()
            if archive_format is ArchiveFormat.ZIP:
                self._extract_zip(source, staging)
            elif archive_format in {
                ArchiveFormat.TAR,
                ArchiveFormat.TAR_GZ,
                ArchiveFormat.TAR_BZ2,
                ArchiveFormat.TAR_XZ,
            }:
                self._extract_tar(source, staging)
            elif archive_format is ArchiveFormat.SEVEN_Z:
                self._extract_7z(source, staging)
            elif archive_format is ArchiveFormat.RAR:
                self._extract_rar(source, staging)
            else:
                raise ArchiveError("Формат архива не поддерживается")
            self._validate_staging(staging)
            results: list[Path] = []
            for child in staging.iterdir():
                target = self._unique_target(destination / child.name)
                shutil.move(str(child), str(target))
                results.append(target)
            return tuple(results)

    @staticmethod
    def detect_format(path: Path) -> ArchiveFormat:
        name = path.name.casefold()
        if name.endswith((".tar.gz", ".tgz")):
            return ArchiveFormat.TAR_GZ
        if name.endswith((".tar.bz2", ".tbz2")):
            return ArchiveFormat.TAR_BZ2
        if name.endswith((".tar.xz", ".txz")):
            return ArchiveFormat.TAR_XZ
        mapping = {
            ".zip": ArchiveFormat.ZIP,
            ".7z": ArchiveFormat.SEVEN_Z,
            ".tar": ArchiveFormat.TAR,
            ".rar": ArchiveFormat.RAR,
        }
        try:
            return mapping[path.suffix.casefold()]
        except KeyError as exc:
            raise ArchiveError(f"Неизвестное расширение архива: {path.name}") from exc

    def _create_zip(self, output: Path, sources: tuple[Path, ...]) -> None:
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for source, arcname in self._source_items(sources):
                archive.write(source, arcname.as_posix())

    def _create_tar(
        self,
        output: Path,
        sources: tuple[Path, ...],
        archive_format: ArchiveFormat,
    ) -> None:
        modes = {
            ArchiveFormat.TAR: "w",
            ArchiveFormat.TAR_GZ: "w:gz",
            ArchiveFormat.TAR_BZ2: "w:bz2",
            ArchiveFormat.TAR_XZ: "w:xz",
        }
        with tarfile.open(output, modes[archive_format]) as archive:
            for source in sources:
                archive.add(source, arcname=source.name, recursive=True, filter=self._tar_filter)

    def _create_7z(self, output: Path, sources: tuple[Path, ...]) -> None:
        backend = self._py7zr()
        if backend is not None:
            with backend.SevenZipFile(output, "w") as archive:
                for source in sources:
                    if source.is_dir():
                        archive.writeall(source, arcname=source.name)
                    else:
                        archive.write(source, arcname=source.name)
            return
        executable = self._find_7z()
        if executable is None:
            raise ArchiveError("Создание 7Z недоступно: установите 7-Zip или py7zr")
        self._run_checked(
            [str(executable), "a", "-t7z", "-y", str(output), *(str(path) for path in sources)],
            "7Z не создан",
        )

    def _create_rar(self, output: Path, sources: tuple[Path, ...]) -> None:
        executable = self._find_rar_creator()
        if executable is None:
            raise ArchiveError("Создание RAR недоступно: установите WinRAR или RAR")
        self._run_checked(
            [str(executable), "a", "-idq", str(output), *(str(path) for path in sources)],
            "RAR не создан",
        )

    def _extract_zip(self, source: Path, staging: Path) -> None:
        try:
            with zipfile.ZipFile(source) as archive:
                entries = tuple(
                    ArchiveEntry(item.filename, item.file_size, item.is_dir())
                    for item in archive.infolist()
                )
                self._validate_entries(entries)
                for item in archive.infolist():
                    if self._zip_is_symlink(item):
                        raise ArchiveError(f"Ссылки в архиве запрещены: {item.filename}")
                    target = self._safe_target(staging, item.filename)
                    if item.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(item) as input_file, target.open("wb") as output_file:
                        self._copy_bounded(input_file, output_file, item.filename)
        except zipfile.BadZipFile as exc:
            raise ArchiveError(f"Повреждённый ZIP: {exc}") from exc

    def _extract_tar(self, source: Path, staging: Path) -> None:
        try:
            with tarfile.open(source, "r:*") as archive:
                members = archive.getmembers()
                entries = tuple(
                    ArchiveEntry(item.name, item.size, item.isdir()) for item in members
                )
                self._validate_entries(entries)
                for item in members:
                    if item.issym() or item.islnk() or item.isdev():
                        raise ArchiveError(f"Ссылки и устройства в TAR запрещены: {item.name}")
                    target = self._safe_target(staging, item.name)
                    if item.isdir():
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    if not item.isfile():
                        raise ArchiveError(f"Неподдерживаемый элемент TAR: {item.name}")
                    extracted = archive.extractfile(item)
                    if extracted is None:
                        raise ArchiveError(f"Не удалось прочитать: {item.name}")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with extracted, target.open("wb") as output_file:
                        self._copy_bounded(extracted, output_file, item.name)
        except tarfile.TarError as exc:
            raise ArchiveError(f"Повреждённый TAR: {exc}") from exc

    def _list_7z(self, source: Path) -> tuple[ArchiveEntry, ...]:
        backend = self._py7zr()
        if backend is not None:
            try:
                with backend.SevenZipFile(source, "r") as archive:
                    information = getattr(archive, "list", lambda: [])()
                    if information:
                        return tuple(
                            ArchiveEntry(
                                str(item.filename),
                                int(getattr(item, "uncompressed", 0) or 0),
                                bool(getattr(item, "is_directory", False)),
                            )
                            for item in information
                        )
                    return tuple(
                        ArchiveEntry(name, 0, name.endswith("/"))
                        for name in archive.getnames()
                    )
            except Exception as exc:
                raise ArchiveError(f"Не удалось прочитать 7Z: {exc}") from exc
        executable = self._find_7z()
        if executable is None:
            raise ArchiveError("Чтение 7Z недоступно: установите 7-Zip или py7zr")
        result = self._run_checked(
            [str(executable), "l", "-slt", str(source)], "Не удалось прочитать 7Z"
        )
        entries: list[ArchiveEntry] = []
        record: dict[str, str] = {}
        for line in result.stdout.splitlines() + [""]:
            if not line.strip():
                if "Path" in record and record.get("Type") is None:
                    name = record["Path"]
                    if name != str(source):
                        size = int(record.get("Size", "0") or 0)
                        attributes = record.get("Attributes", "")
                        entries.append(ArchiveEntry(name, size, "D" in attributes))
                record = {}
                continue
            if " = " in line:
                key, value = line.split(" = ", 1)
                record[key] = value
        return tuple(entries)

    def _extract_7z(self, source: Path, staging: Path) -> None:
        entries = self._list_7z(source)
        self._validate_entries(entries)
        backend = self._py7zr()
        if backend is not None:
            try:
                with backend.SevenZipFile(source, "r") as archive:
                    archive.extractall(path=staging)  # nosec B202 - 7Z paths were validated by _validate_entries
                return
            except Exception as exc:
                raise ArchiveError(f"7Z не распакован: {exc}") from exc
        executable = self._find_7z()
        if executable is None:
            raise ArchiveError("Распаковка 7Z недоступна")
        self._extract_external_streams(executable, source, staging, entries, seven_zip=True)

    def _list_rar(self, source: Path) -> tuple[ArchiveEntry, ...]:
        backend = self._rarfile()
        if backend is not None:
            try:
                with backend.RarFile(source) as archive:
                    return tuple(
                        ArchiveEntry(item.filename, item.file_size, item.isdir())
                        for item in archive.infolist()
                    )
            except Exception as exc:
                raise ArchiveError(f"Не удалось прочитать RAR: {exc}") from exc
        executable = self._find_rar_extractor()
        if executable is None:
            raise ArchiveError("Чтение RAR недоступно: установите WinRAR/RAR/UnRAR")
        result = self._run_checked(
            [str(executable), "lb", str(source)], "Не удалось прочитать RAR"
        )
        return tuple(
            ArchiveEntry(name.strip(), 0, name.rstrip().endswith(("/", "\\")))
            for name in result.stdout.splitlines()
            if name.strip()
        )

    def _extract_rar(self, source: Path, staging: Path) -> None:
        entries = self._list_rar(source)
        self._validate_entries(entries)
        backend = self._rarfile()
        if backend is not None:
            try:
                with backend.RarFile(source) as archive:
                    for item in archive.infolist():
                        name = item.filename
                        if getattr(item, "is_symlink", lambda: False)():
                            raise ArchiveError(f"Ссылки в RAR запрещены: {name}")
                        target = self._safe_target(staging, name)
                        if item.isdir():
                            target.mkdir(parents=True, exist_ok=True)
                            continue
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(item) as input_file, target.open("wb") as output_file:
                            self._copy_bounded(input_file, output_file, name)
                return
            except ArchiveError:
                raise
            except Exception as exc:
                raise ArchiveError(f"RAR не распакован: {exc}") from exc
        executable = self._find_rar_extractor()
        if executable is None:
            raise ArchiveError("Распаковка RAR недоступна")
        self._extract_external_streams(executable, source, staging, entries, seven_zip=False)

    def _extract_external_streams(
        self,
        executable: Path,
        archive: Path,
        staging: Path,
        entries: tuple[ArchiveEntry, ...],
        *,
        seven_zip: bool,
    ) -> None:
        total = 0
        for entry in entries:
            target = self._safe_target(staging, entry.name)
            if entry.is_directory:
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            command = (
                [str(executable), "x", "-so", str(archive), entry.name]
                if seven_zip
                else [str(executable), "p", "-inul", str(archive), entry.name]
            )
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if process.stdout is None:
                process.kill()
                raise ArchiveError(f"Backend не вернул данные: {entry.name}")
            written = 0
            try:
                with target.open("wb") as output_file:
                    while True:
                        chunk = process.stdout.read(1024 * 1024)
                        if not chunk:
                            break
                        written += len(chunk)
                        total += len(chunk)
                        if written > self.MAX_SINGLE_BYTES or total > self.MAX_TOTAL_BYTES:
                            process.kill()
                            raise ArchiveError("Распакованный архив превышает допустимый размер")
                        output_file.write(chunk)
                stderr = process.stderr.read() if process.stderr is not None else b""
                return_code = process.wait()
                if return_code != 0:
                    target.unlink(missing_ok=True)
                    message = stderr.decode(errors="replace").strip() or "неизвестная ошибка"
                    raise ArchiveError(f"Не удалось извлечь {entry.name}: {message}")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()

    def _source_items(self, sources: tuple[Path, ...]) -> Iterator[tuple[Path, Path]]:
        for source in sources:
            if source.is_dir():
                yield source, Path(source.name)
                for child in sorted(source.rglob("*")):
                    if child.is_symlink():
                        raise ArchiveError(f"Символические ссылки не архивируются: {child}")
                    yield child, Path(source.name) / child.relative_to(source)
            else:
                yield source, Path(source.name)

    def _validate_entries(self, entries: Iterable[ArchiveEntry]) -> None:
        total = 0
        count = 0
        for entry in entries:
            count += 1
            if count > self.MAX_MEMBERS:
                raise ArchiveError("В архиве слишком много элементов")
            self._validate_member_name(entry.name)
            if entry.size < 0 or entry.size > self.MAX_SINGLE_BYTES:
                raise ArchiveError(f"Слишком большой элемент архива: {entry.name}")
            total += entry.size
            if total > self.MAX_TOTAL_BYTES:
                raise ArchiveError("Распакованный архив превышает допустимый размер")

    def _validate_staging(self, staging: Path) -> None:
        count = 0
        total = 0
        for path in staging.rglob("*"):
            count += 1
            if count > self.MAX_MEMBERS:
                raise ArchiveError("После распаковки обнаружено слишком много элементов")
            if path.is_symlink():
                raise ArchiveError(f"Ссылки после распаковки запрещены: {path.name}")
            if path.is_file():
                size = path.stat().st_size
                if size > self.MAX_SINGLE_BYTES:
                    raise ArchiveError(f"Слишком большой файл: {path.name}")
                total += size
                if total > self.MAX_TOTAL_BYTES:
                    raise ArchiveError("Распакованный архив превышает допустимый размер")

    def _safe_target(self, root: Path, name: str) -> Path:
        self._validate_member_name(name)
        pure = PurePosixPath(name.replace("\\", "/"))
        target = (root / Path(*pure.parts)).resolve()
        if not self._is_relative_to(target, root.resolve()):
            raise ArchiveError(f"Путь выходит за каталог распаковки: {name}")
        return target

    @staticmethod
    def _validate_member_name(name: str) -> None:
        normalized = name.replace("\\", "/")
        pure = PurePosixPath(normalized)
        if not normalized or pure.is_absolute() or ".." in pure.parts:
            raise ArchiveError(f"Опасный путь в архиве: {name}")
        if pure.parts and ":" in pure.parts[0]:
            raise ArchiveError(f"Опасный Windows-путь в архиве: {name}")

    def _copy_bounded(self, input_file: Any, output_file: Any, name: str) -> None:
        written = 0
        while True:
            chunk = input_file.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > self.MAX_SINGLE_BYTES:
                raise ArchiveError(f"Слишком большой файл: {name}")
            output_file.write(chunk)

    @staticmethod
    def _zip_is_symlink(item: zipfile.ZipInfo) -> bool:
        return ((item.external_attr >> 16) & 0o170000) == 0o120000

    @staticmethod
    def _tar_filter(item: tarfile.TarInfo) -> tarfile.TarInfo:
        if item.issym() or item.islnk() or item.isdev():
            raise ArchiveError(f"Ссылки и устройства не архивируются: {item.name}")
        return item

    @staticmethod
    def _unique_target(path: Path) -> Path:
        if not path.exists():
            return path
        counter = 2
        while True:
            candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    @staticmethod
    def _with_archive_suffix(path: Path, archive_format: ArchiveFormat) -> Path:
        expected = f".{archive_format.value}"
        if path.name.casefold().endswith(expected):
            return path
        return path.with_name(f"{path.name}{expected}")

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    @staticmethod
    def _optional_note(available: bool, backend: str) -> str:
        return "" if available else f"Требуется {backend}."

    @staticmethod
    def _optional_module(name: str) -> Any | None:
        if importlib.util.find_spec(name) is None:
            return None
        try:
            return importlib.import_module(name)
        except ImportError:
            return None

    def _py7zr(self) -> Any | None:
        return self._optional_module("py7zr")

    def _rarfile(self) -> Any | None:
        return self._optional_module("rarfile")

    @staticmethod
    def _candidate_executables(names: tuple[str, ...], paths: tuple[Path, ...]) -> Path | None:
        for name in names:
            located = shutil.which(name)
            if located:
                return Path(located)
        for path in paths:
            if path.is_file():
                return path
        return None

    def _find_7z(self) -> Path | None:
        program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
        program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
        return self._candidate_executables(
            ("7z", "7zz", "7za"),
            (program_files / "7-Zip/7z.exe", program_files_x86 / "7-Zip/7z.exe"),
        )

    def _find_rar_creator(self) -> Path | None:
        program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
        program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
        return self._candidate_executables(
            ("rar", "WinRAR"),
            (program_files / "WinRAR/Rar.exe", program_files_x86 / "WinRAR/Rar.exe"),
        )

    def _find_rar_extractor(self) -> Path | None:
        program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
        program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
        return self._candidate_executables(
            ("unrar", "rar", "WinRAR"),
            (
                program_files / "WinRAR/UnRAR.exe",
                program_files / "WinRAR/Rar.exe",
                program_files_x86 / "WinRAR/UnRAR.exe",
                program_files_x86 / "WinRAR/Rar.exe",
            ),
        )

    @staticmethod
    def _run_checked(command: list[str], label: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "неизвестная ошибка"
            raise ArchiveError(f"{label}: {message}")
        return result
