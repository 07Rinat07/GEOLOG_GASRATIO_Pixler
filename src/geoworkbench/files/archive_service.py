from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
import os
import shutil
import subprocess
import tarfile
import tempfile
from typing import Iterable
import zipfile

import py7zr
import rarfile


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
    MAX_MEMBERS = 50_000
    MAX_TOTAL_BYTES = 20 * 1024 * 1024 * 1024
    MAX_SINGLE_BYTES = 5 * 1024 * 1024 * 1024

    def capabilities(self) -> tuple[ArchiveCapability, ...]:
        rar_creator = self._find_rar_creator()
        rar_extractor = self._rar_extract_available()
        return (
            ArchiveCapability(ArchiveFormat.ZIP, True, True),
            ArchiveCapability(ArchiveFormat.SEVEN_Z, True, True),
            ArchiveCapability(ArchiveFormat.TAR, True, True),
            ArchiveCapability(ArchiveFormat.TAR_GZ, True, True),
            ArchiveCapability(ArchiveFormat.TAR_BZ2, True, True),
            ArchiveCapability(ArchiveFormat.TAR_XZ, True, True),
            ArchiveCapability(
                ArchiveFormat.RAR,
                rar_creator is not None,
                rar_extractor,
                "Для RAR требуется установленный WinRAR/RAR/UnRAR или совместимый backend.",
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
        output = Path(output_path).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        if output in paths:
            raise ArchiveError("Архив не может быть одновременно источником")
        if archive_format is ArchiveFormat.ZIP:
            self._create_zip(output, paths)
        elif archive_format is ArchiveFormat.SEVEN_Z:
            self._create_7z(output, paths)
        elif archive_format in {
            ArchiveFormat.TAR,
            ArchiveFormat.TAR_GZ,
            ArchiveFormat.TAR_BZ2,
            ArchiveFormat.TAR_XZ,
        }:
            self._create_tar(output, paths, archive_format)
        elif archive_format is ArchiveFormat.RAR:
            self._create_rar(output, paths)
        else:
            raise ArchiveError(f"Формат не поддерживается: {archive_format}")
        return output

    def list_entries(self, archive_path: Path) -> tuple[ArchiveEntry, ...]:
        path = Path(archive_path)
        archive_format = self.detect_format(path)
        if archive_format is ArchiveFormat.ZIP:
            with zipfile.ZipFile(path) as archive:
                return tuple(
                    ArchiveEntry(item.filename, item.file_size, item.is_dir())
                    for item in archive.infolist()
                )
        if archive_format in {
            ArchiveFormat.TAR,
            ArchiveFormat.TAR_GZ,
            ArchiveFormat.TAR_BZ2,
            ArchiveFormat.TAR_XZ,
        }:
            with tarfile.open(path, "r:*") as archive:
                return tuple(
                    ArchiveEntry(item.name, item.size, item.isdir()) for item in archive.getmembers()
                )
        if archive_format is ArchiveFormat.SEVEN_Z:
            with py7zr.SevenZipFile(path, mode="r") as archive:
                return tuple(ArchiveEntry(name, 0, name.endswith("/")) for name in archive.getnames())
        if archive_format is ArchiveFormat.RAR:
            try:
                with rarfile.RarFile(path) as archive:
                    return tuple(
                        ArchiveEntry(item.filename, item.file_size, item.isdir())
                        for item in archive.infolist()
                    )
            except rarfile.Error as exc:
                raise ArchiveError(f"Не удалось прочитать RAR: {exc}") from exc
        raise ArchiveError("Формат архива не распознан")

    def extract(self, archive_path: Path, destination: Path) -> tuple[Path, ...]:
        source = Path(archive_path).resolve()
        if not source.is_file():
            raise ArchiveError(f"Архив не найден: {source}")
        destination = Path(destination).resolve()
        destination.mkdir(parents=True, exist_ok=True)
        archive_format = self.detect_format(source)
        with tempfile.TemporaryDirectory(prefix="geoworkbench-extract-") as temporary:
            staging = Path(temporary)
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
            extracted = self._validate_staging(staging)
            results: list[Path] = []
            for child in staging.iterdir():
                target = self._unique_target(destination / child.name)
                shutil.move(str(child), str(target))
                results.append(target)
            return tuple(results)

    @staticmethod
    def detect_format(path: Path) -> ArchiveFormat:
        name = path.name.casefold()
        if name.endswith(".tar.gz") or name.endswith(".tgz"):
            return ArchiveFormat.TAR_GZ
        if name.endswith(".tar.bz2") or name.endswith(".tbz2"):
            return ArchiveFormat.TAR_BZ2
        if name.endswith(".tar.xz") or name.endswith(".txz"):
            return ArchiveFormat.TAR_XZ
        suffix = path.suffix.casefold()
        mapping = {
            ".zip": ArchiveFormat.ZIP,
            ".7z": ArchiveFormat.SEVEN_Z,
            ".tar": ArchiveFormat.TAR,
            ".rar": ArchiveFormat.RAR,
        }
        try:
            return mapping[suffix]
        except KeyError as exc:
            raise ArchiveError(f"Неизвестное расширение архива: {path.name}") from exc

    def _create_zip(self, output: Path, sources: tuple[Path, ...]) -> None:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for source, arcname in self._source_items(sources):
                archive.write(source, arcname.as_posix())

    def _create_7z(self, output: Path, sources: tuple[Path, ...]) -> None:
        with py7zr.SevenZipFile(output, "w") as archive:
            for source in sources:
                if source.is_dir():
                    archive.writeall(source, arcname=source.name)
                else:
                    archive.write(source, arcname=source.name)

    def _create_tar(
        self, output: Path, sources: tuple[Path, ...], archive_format: ArchiveFormat
    ) -> None:
        modes = {
            ArchiveFormat.TAR: "w",
            ArchiveFormat.TAR_GZ: "w:gz",
            ArchiveFormat.TAR_BZ2: "w:bz2",
            ArchiveFormat.TAR_XZ: "w:xz",
        }
        with tarfile.open(output, modes[archive_format]) as archive:
            for source in sources:
                archive.add(source, arcname=source.name, recursive=True)

    def _create_rar(self, output: Path, sources: tuple[Path, ...]) -> None:
        executable = self._find_rar_creator()
        if executable is None:
            raise ArchiveError(
                "Создание RAR недоступно: установите WinRAR или командный RAR и повторите проверку."
            )
        command = [str(executable), "a", "-idq", str(output), *(str(path) for path in sources)]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "неизвестная ошибка"
            raise ArchiveError(f"RAR не создан: {message}")

    def _extract_zip(self, source: Path, staging: Path) -> None:
        with zipfile.ZipFile(source) as archive:
            entries = archive.infolist()
            self._validate_entry_metadata(
                (item.filename, item.file_size, item.is_dir(), self._zip_is_symlink(item))
                for item in entries
            )
            for item in entries:
                target = self._safe_target(staging, item.filename)
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(item) as source_file, target.open("wb") as target_file:
                    shutil.copyfileobj(source_file, target_file, length=1024 * 1024)

    def _extract_tar(self, source: Path, staging: Path) -> None:
        with tarfile.open(source, "r:*") as archive:
            entries = archive.getmembers()
            self._validate_entry_metadata(
                (item.name, item.size, item.isdir(), item.issym() or item.islnk()) for item in entries
            )
            for item in entries:
                target = self._safe_target(staging, item.name)
                if item.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if not item.isfile():
                    raise ArchiveError(f"Неподдерживаемый элемент TAR: {item.name}")
                target.parent.mkdir(parents=True, exist_ok=True)
                extracted = archive.extractfile(item)
                if extracted is None:
                    raise ArchiveError(f"Не удалось извлечь: {item.name}")
                with extracted, target.open("wb") as target_file:
                    shutil.copyfileobj(extracted, target_file, length=1024 * 1024)

    def _extract_7z(self, source: Path, staging: Path) -> None:
        with py7zr.SevenZipFile(source, mode="r") as archive:
            names = archive.getnames()
            self._validate_entry_metadata((name, 0, name.endswith("/"), False) for name in names)
            archive.extractall(path=staging)

    def _extract_rar(self, source: Path, staging: Path) -> None:
        if not self._rar_extract_available():
            raise ArchiveError(
                "Распаковка RAR недоступна: установите WinRAR, UnRAR или 7-Zip backend."
            )
        try:
            with rarfile.RarFile(source) as archive:
                entries = archive.infolist()
                self._validate_entry_metadata(
                    (item.filename, item.file_size, item.isdir(), item.is_symlink())
                    for item in entries
                )
                for item in entries:
                    target = self._safe_target(staging, item.filename)
                    if item.isdir():
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(item) as source_file, target.open("wb") as target_file:
                        shutil.copyfileobj(source_file, target_file, length=1024 * 1024)
        except rarfile.Error as exc:
            raise ArchiveError(f"RAR не распакован: {exc}") from exc

    def _validate_entry_metadata(
        self, entries: Iterable[tuple[str, int, bool, bool]]
    ) -> None:
        total = 0
        count = 0
        for name, size, _is_directory, is_link in entries:
            count += 1
            if count > self.MAX_MEMBERS:
                raise ArchiveError("В архиве слишком много элементов")
            self._validate_member_name(name)
            if is_link:
                raise ArchiveError(f"Ссылки в архиве запрещены: {name}")
            if size < 0 or size > self.MAX_SINGLE_BYTES:
                raise ArchiveError(f"Слишком большой элемент архива: {name}")
            total += size
            if total > self.MAX_TOTAL_BYTES:
                raise ArchiveError("Распакованный архив превышает допустимый размер")

    def _validate_staging(self, staging: Path) -> tuple[Path, ...]:
        files: list[Path] = []
        total = 0
        for path in staging.rglob("*"):
            if path.is_symlink():
                raise ArchiveError(f"Ссылки после распаковки запрещены: {path.name}")
            if path.is_file():
                size = path.stat().st_size
                if size > self.MAX_SINGLE_BYTES:
                    raise ArchiveError(f"Слишком большой файл: {path.name}")
                total += size
                if total > self.MAX_TOTAL_BYTES:
                    raise ArchiveError("Распакованный архив превышает допустимый размер")
                files.append(path)
        return tuple(files)

    @staticmethod
    def _validate_member_name(name: str) -> None:
        normalized = name.replace("\\", "/")
        pure = PurePosixPath(normalized)
        if not normalized or pure.is_absolute() or ".." in pure.parts:
            raise ArchiveError(f"Опасный путь в архиве: {name}")
        if pure.parts and ":" in pure.parts[0]:
            raise ArchiveError(f"Абсолютный Windows-путь в архиве: {name}")

    @classmethod
    def _safe_target(cls, root: Path, name: str) -> Path:
        cls._validate_member_name(name)
        target = (root / name.replace("\\", "/")).resolve()
        try:
            target.relative_to(root.resolve())
        except ValueError as exc:
            raise ArchiveError(f"Путь выходит за каталог распаковки: {name}") from exc
        return target

    @staticmethod
    def _zip_is_symlink(item: zipfile.ZipInfo) -> bool:
        return ((item.external_attr >> 16) & 0o170000) == 0o120000

    @staticmethod
    def _source_items(sources: tuple[Path, ...]) -> Iterable[tuple[Path, PurePosixPath]]:
        for source in sources:
            if source.is_file():
                yield source, PurePosixPath(source.name)
                continue
            yield source, PurePosixPath(source.name)
            for child in source.rglob("*"):
                relative = child.relative_to(source)
                yield child, PurePosixPath(source.name) / PurePosixPath(relative.as_posix())

    @staticmethod
    def _unique_target(target: Path) -> Path:
        if not target.exists():
            return target
        index = 2
        while True:
            candidate = target.with_name(f"{target.stem} ({index}){target.suffix}")
            if not candidate.exists():
                return candidate
            index += 1

    @staticmethod
    def _find_rar_creator() -> Path | None:
        candidates = [shutil.which("rar"), shutil.which("rar.exe"), shutil.which("WinRAR.exe")]
        if os.name == "nt":
            candidates.extend(
                [
                    r"C:\Program Files\WinRAR\Rar.exe",
                    r"C:\Program Files\WinRAR\WinRAR.exe",
                    r"C:\Program Files (x86)\WinRAR\Rar.exe",
                ]
            )
        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                return Path(candidate)
        return None

    @staticmethod
    def _rar_extract_available() -> bool:
        try:
            rarfile.tool_setup(unrar=True, unar=True, bsdtar=True, sevenzip=True)
        except rarfile.RarCannotExec:
            return False
        return True
