from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile, ZipInfo

from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.project_codec import ProjectDocument, ProjectFormatError, load_project_document


PACKAGE_FORMAT = "geolog-project-package"
PACKAGE_VERSION = 1
PACKAGE_MANIFEST = "manifest.json"
PACKAGE_PROJECT = "project.geolog.json"


class ProjectPackageError(ProjectFormatError):
    pass


@dataclass(frozen=True, slots=True)
class PackageEntry:
    path: str
    size_bytes: int
    sha256: str


class PackageProjectRepository:
    """Single-file, checksummed project package repository."""

    def __init__(
        self,
        *,
        max_entries: int = 20_000,
        max_uncompressed_bytes: int = 2 * 1024**3,
    ) -> None:
        self.max_entries = max_entries
        self.max_uncompressed_bytes = max_uncompressed_bytes

    def save(self, document: ProjectDocument, target: Path) -> None:
        destination = Path(target)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=f".{destination.stem}-package-", dir=destination.parent
        ) as temporary:
            root = Path(temporary)
            project_path = root / PACKAGE_PROJECT
            save_project(
                document.project,
                project_path,
                tablet_layouts=document.tablet_layouts,
                tablet_presets=document.tablet_presets,
                source_documents=document.source_documents,
                import_reports=document.import_reports,
                image_assets=document.image_assets,
            )
            entries = self._collect_entries(root)
            manifest = {
                "format": PACKAGE_FORMAT,
                "package_version": PACKAGE_VERSION,
                "project_path": PACKAGE_PROJECT,
                "entries": [
                    {
                        "path": entry.path,
                        "size_bytes": entry.size_bytes,
                        "sha256": entry.sha256,
                    }
                    for entry in entries
                ],
            }
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
            )
            os.close(descriptor)
            try:
                with ZipFile(temporary_name, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
                    archive.writestr(
                        PACKAGE_MANIFEST,
                        json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
                    )
                    for entry in entries:
                        archive.write(root / Path(entry.path), entry.path)
                # Windows requires a writable descriptor for ``fsync``.
                with open(temporary_name, "rb+") as stream:
                    os.fsync(stream.fileno())
                os.replace(temporary_name, destination)
            except Exception:
                Path(temporary_name).unlink(missing_ok=True)
                raise

    def load(self, source: Path) -> ProjectDocument:
        package = Path(source)
        try:
            package_stat = package.lstat()
        except OSError as exc:
            raise ProjectPackageError(f"Пакет проекта не найден: {package}") from exc
        if not stat.S_ISREG(package_stat.st_mode) or package.is_symlink():
            raise ProjectPackageError("Пакет проекта должен быть обычным файлом")
        try:
            with ZipFile(package, "r") as archive:
                infos = archive.infolist()
                self._validate_infos(infos)
                manifest = self._read_manifest(archive)
                entries = self._manifest_entries(manifest)
                archive_names = {info.filename for info in infos if info.filename != PACKAGE_MANIFEST}
                if archive_names != {entry.path for entry in entries}:
                    raise ProjectPackageError("Состав пакета не совпадает с манифестом")
                with tempfile.TemporaryDirectory(prefix="geolog-package-open-") as temporary:
                    root = Path(temporary)
                    for entry in entries:
                        payload = archive.read(entry.path)
                        if len(payload) != entry.size_bytes or sha256(payload).hexdigest() != entry.sha256:
                            raise ProjectPackageError(
                                f"Контрольная сумма файла пакета не совпадает: {entry.path}"
                            )
                        target = root.joinpath(*PurePosixPath(entry.path).parts)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(payload)
                    project_name = manifest.get("project_path")
                    if project_name != PACKAGE_PROJECT:
                        raise ProjectPackageError("Пакет содержит неизвестный путь проекта")
                    return load_project_document(root / PACKAGE_PROJECT)
        except (BadZipFile, OSError, KeyError, UnicodeError, json.JSONDecodeError) as exc:
            raise ProjectPackageError(f"Не удалось открыть пакет проекта: {package}") from exc

    def _collect_entries(self, root: Path) -> tuple[PackageEntry, ...]:
        entries: list[PackageEntry] = []
        total = 0
        for path in sorted(root.rglob("*"), key=lambda item: str(item).casefold()):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(root).as_posix()
            payload = path.read_bytes()
            total += len(payload)
            if total > self.max_uncompressed_bytes:
                raise ProjectPackageError("Пакет проекта превышает допустимый размер")
            entries.append(PackageEntry(relative, len(payload), sha256(payload).hexdigest()))
        if len(entries) > self.max_entries:
            raise ProjectPackageError("Пакет проекта содержит слишком много файлов")
        return tuple(entries)

    def _validate_infos(self, infos: list[ZipInfo]) -> None:
        if len(infos) > self.max_entries + 1:
            raise ProjectPackageError("Пакет содержит слишком много записей")
        total = 0
        names: set[str] = set()
        for info in infos:
            self._validate_member_name(info.filename)
            if info.filename in names:
                raise ProjectPackageError(f"Пакет содержит повторяющийся путь: {info.filename}")
            names.add(info.filename)
            total += info.file_size
            if total > self.max_uncompressed_bytes:
                raise ProjectPackageError("Распакованный пакет превышает допустимый размер")
            if info.compress_size == 0 and info.file_size > 0:
                raise ProjectPackageError("Пакет содержит подозрительно сжатую запись")
            if info.compress_size > 0 and info.file_size / info.compress_size > 1000:
                raise ProjectPackageError("Коэффициент сжатия пакета превышает безопасный лимит")
        if PACKAGE_MANIFEST not in names or PACKAGE_PROJECT not in names:
            raise ProjectPackageError("Пакет не содержит manifest.json или project.geolog.json")

    @staticmethod
    def _validate_member_name(value: str) -> None:
        if not value or "\\" in value or "\x00" in value:
            raise ProjectPackageError("Пакет содержит недопустимый путь")
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "." in path.parts:
            raise ProjectPackageError(f"Пакет содержит небезопасный путь: {value}")

    @staticmethod
    def _read_manifest(archive: ZipFile) -> dict[str, object]:
        raw = archive.read(PACKAGE_MANIFEST)
        if len(raw) > 16 * 1024**2:
            raise ProjectPackageError("Манифест пакета слишком большой")
        manifest = json.loads(raw.decode("utf-8"))
        if not isinstance(manifest, dict):
            raise ProjectPackageError("Манифест пакета должен быть объектом")
        if manifest.get("format") != PACKAGE_FORMAT or manifest.get("package_version") != PACKAGE_VERSION:
            raise ProjectPackageError("Версия пакета проекта не поддерживается")
        return manifest

    def _manifest_entries(self, manifest: dict[str, object]) -> tuple[PackageEntry, ...]:
        raw_entries = manifest.get("entries")
        if not isinstance(raw_entries, list):
            raise ProjectPackageError("Манифест пакета не содержит entries")
        entries: list[PackageEntry] = []
        for raw in raw_entries:
            if not isinstance(raw, dict):
                raise ProjectPackageError("Запись манифеста должна быть объектом")
            path = raw.get("path")
            size = raw.get("size_bytes")
            digest = raw.get("sha256")
            if not isinstance(path, str):
                raise ProjectPackageError("Путь записи манифеста отсутствует")
            self._validate_member_name(path)
            if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                raise ProjectPackageError("Размер записи манифеста некорректен")
            if not isinstance(digest, str) or len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest
            ):
                raise ProjectPackageError("SHA-256 записи манифеста некорректен")
            entries.append(PackageEntry(path, size, digest))
        if len({entry.path for entry in entries}) != len(entries):
            raise ProjectPackageError("Манифест содержит повторяющиеся пути")
        return tuple(entries)
