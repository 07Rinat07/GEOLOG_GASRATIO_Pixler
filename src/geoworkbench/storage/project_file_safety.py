from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from geoworkbench.project.repository import ProjectRepository
from geoworkbench.storage.package_project_repository import PackageProjectRepository
from geoworkbench.storage.project_codec import ProjectDocument
from geoworkbench.storage.project_repository_router import ProjectRepositoryRouter


_INDEX_FORMAT = "geolog-project-backup-index"
_INDEX_VERSION = 1
_INDEX_NAME = "index.v1.json"
_INDEX_LOCK_NAME = ".index.lock"
_HASH_CHUNK_BYTES = 1024 * 1024
_MAX_INDEX_BYTES = 8 * 1024 * 1024
_MAX_BACKUP_RECORDS = 10_000
_SYMLINK_REPARSE_TAG = 0xA000000C
_MOUNT_POINT_REPARSE_TAG = 0xA0000003


class SaveMode(StrEnum):
    EXPLICIT = "explicit"
    MATERIAL_AUTOSAVE = "material_autosave"


class ProjectFileSafetyError(RuntimeError):
    """Base error for verified project persistence."""


class UnsafeProjectPathError(ProjectFileSafetyError):
    """Raised when a project path is redirected or is not a regular file."""


class ProjectChangedExternallyError(ProjectFileSafetyError):
    """Raised when another process changed the project since it was opened."""


class ExistingTargetRequiresExpectedStateError(ProjectFileSafetyError):
    """Raised when an existing target would be overwritten without a baseline."""


class LegacyAutosaveRequiresPackageError(ProjectFileSafetyError):
    """Raised when material autosave is requested for a legacy multi-file project."""


class BackupValidationError(ProjectFileSafetyError):
    """Raised when a managed backup or its index cannot be trusted."""


class RecoveryValidationError(ProjectFileSafetyError):
    """Raised when a recovery candidate or restore destination is unsafe."""


@dataclass(frozen=True, slots=True)
class FileFingerprint:
    size_bytes: int
    mtime_ns: int
    sha256: str
    device: int
    inode: int


@dataclass(frozen=True, slots=True)
class ProjectDiskState:
    path: Path
    path_id: str
    storage_kind: str
    project_id: str
    save_revision: int
    fingerprint: FileFingerprint
    bundle_sha256: str


@dataclass(frozen=True, slots=True)
class ProjectBackupRecord:
    record_id: str
    backup_path: Path
    source_path_id: str
    source_kind: str
    project_id: str
    save_revision: int
    created_at: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class BackupPolicy:
    keep_last: int = 5
    directory_name: str = ".geolog-backups"

    def __post_init__(self) -> None:
        if (
            isinstance(self.keep_last, bool)
            or not isinstance(self.keep_last, int)
            or self.keep_last < 1
        ):
            raise ValueError("keep_last должен быть положительным целым числом")
        directory = Path(self.directory_name)
        if (
            not self.directory_name
            or directory.is_absolute()
            or len(directory.parts) != 1
            or directory.name in {".", ".."}
        ):
            raise ValueError("directory_name должен быть именем каталога")


@dataclass(frozen=True, slots=True)
class SafeSaveResult:
    path: Path
    disk_state: ProjectDiskState
    backup: ProjectBackupRecord | None
    pruned: tuple[Path, ...] = ()
    warnings: tuple[str, ...] = ()


class ProjectFileSafetyService:
    """Verified saves, external-change detection and self-contained recovery copies.

    The service deliberately sits outside Qt.  A package is first written and reopened in
    the destination directory, while the canonical file is still untouched.  Existing
    content is then captured as a verified ``.geologpkg`` backup before the atomic replace.
    """

    def __init__(
        self,
        repository: ProjectRepository | None = None,
        *,
        policy: BackupPolicy | None = None,
        package_repository: PackageProjectRepository | None = None,
    ) -> None:
        self.repository = repository or ProjectRepositoryRouter()
        self.policy = policy or BackupPolicy()
        self.package_repository = package_repository or PackageProjectRepository()

    def open_verified(self, source: Path) -> tuple[ProjectDocument, ProjectDiskState]:
        project_path = Path(source)
        before = _fingerprint_regular(project_path)
        first_document = self.repository.load(project_path)
        middle = _fingerprint_regular(project_path)
        if not _same_payload(before, middle):
            raise ProjectChangedExternallyError(
                "Файл проекта изменился во время открытия. Повторите открытие после синхронизации."
            )

        storage_kind = _storage_kind(project_path)
        if storage_kind == "package":
            return first_document, _disk_state(project_path, first_document, middle, middle.sha256)

        first_bundle = _legacy_bundle_sha256(first_document, middle.sha256)
        second_document = self.repository.load(project_path)
        after = _fingerprint_regular(project_path)
        second_bundle = _legacy_bundle_sha256(second_document, after.sha256)
        if not _same_payload(middle, after) or first_bundle != second_bundle:
            raise ProjectChangedExternallyError(
                "Файлы legacy-проекта изменились во время открытия. Повторите операцию."
            )
        return second_document, _disk_state(
            project_path,
            second_document,
            after,
            second_bundle,
        )

    def inspect(self, source: Path) -> ProjectDiskState:
        _document, state = self.open_verified(source)
        return state

    def save(
        self,
        document: ProjectDocument,
        target: Path,
        *,
        expected: ProjectDiskState | None,
        mode: SaveMode = SaveMode.EXPLICIT,
        allow_existing_target: bool = False,
    ) -> SafeSaveResult:
        destination = Path(target)
        if mode is SaveMode.MATERIAL_AUTOSAVE and _storage_kind(destination) != "package":
            raise LegacyAutosaveRequiresPackageError(
                "Автосохранение после наращивания доступно только для .geologpkg. "
                "Сначала сохраните проект как переносимый пакет."
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        _validate_target_entry(destination)

        previous_document: ProjectDocument | None = None
        baseline: ProjectDiskState | None = None
        if _path_exists(destination):
            if expected is None and not allow_existing_target:
                raise ExistingTargetRequiresExpectedStateError(
                    "Существующий проект нельзя перезаписать без проверенного состояния. "
                    "Используйте «Сохранить как» и подтвердите замену."
                )
            try:
                previous_document, baseline = self.open_verified(destination)
            except Exception as exc:
                if expected is not None:
                    raise ProjectChangedExternallyError(
                        "Открытый проект больше не совпадает с файлом на диске. "
                        "Сохраните текущую работу как копию."
                    ) from exc
                raise
            if expected is not None:
                self._assert_expected(destination, expected, baseline)
        elif expected is not None and expected.path_id == _path_id(destination):
            raise ProjectChangedExternallyError(
                "Файл проекта был удалён или перемещён другим процессом. "
                "Сохраните текущую работу как копию."
            )

        if _storage_kind(destination) == "package":
            return self._save_package(
                document,
                destination,
                baseline=baseline,
                previous_document=previous_document,
            )
        return self._save_legacy(
            document,
            destination,
            baseline=baseline,
            previous_document=previous_document,
        )

    def recovery_candidates(self, original_path: Path) -> tuple[ProjectBackupRecord, ...]:
        source = Path(original_path)
        root = source.parent / self.policy.directory_name
        if not _path_exists(root):
            return ()
        _validate_backup_root(root)
        records = self._load_index(root)
        matching = [record for record in records if record.source_path_id == _path_id(source)]
        for record in matching:
            self._validate_backup_record(record, recovery=True)
        return tuple(sorted(matching, key=_record_sort_key, reverse=True))

    def restore_as_copy(
        self,
        record: ProjectBackupRecord,
        target: Path,
    ) -> ProjectDiskState:
        destination = Path(target)
        if _storage_kind(destination) != "package":
            raise RecoveryValidationError("Восстановленная копия должна иметь расширение .geologpkg")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if _path_exists(destination) or destination.is_symlink():
            raise RecoveryValidationError(
                "Восстановление не перезаписывает существующие файлы. Выберите новое имя."
            )
        _validate_target_entry(destination)

        root = record.backup_path.parent
        _validate_backup_root(root)
        indexed = self._load_index(root)
        if record not in indexed:
            raise RecoveryValidationError("Резервная копия отсутствует в управляемом индексе")
        self._validate_backup_record(record, recovery=True)

        stage = _new_stage_path(destination, suffix=".geologpkg")
        try:
            shutil.copyfile(record.backup_path, stage)
            staged_fingerprint = _fingerprint_regular(stage)
            if (
                staged_fingerprint.size_bytes != record.size_bytes
                or staged_fingerprint.sha256 != record.sha256
            ):
                raise RecoveryValidationError("Контрольная сумма восстановленной копии не совпадает")
            staged_document = self.package_repository.load(stage)
            if (
                staged_document.project.project_id != record.project_id
                or staged_document.project.save_revision != record.save_revision
            ):
                raise RecoveryValidationError("Восстановленная копия относится к другому проекту")
            staged_state = _disk_state(
                stage,
                staged_document,
                staged_fingerprint,
                staged_fingerprint.sha256,
            )
            if _path_exists(destination) or destination.is_symlink():
                raise RecoveryValidationError("Целевой файл появился во время восстановления")
            os.replace(stage, destination)
            _fsync_directory(destination.parent)
            restored_state = _relocate_state(staged_state, destination)
            try:
                verified_state = self.inspect(destination)
            except Exception:
                return restored_state
            if _same_project_state(restored_state, verified_state):
                return verified_state
            return restored_state
        finally:
            _unlink_generated_file(stage)

    def _save_package(
        self,
        document: ProjectDocument,
        destination: Path,
        *,
        baseline: ProjectDiskState | None,
        previous_document: ProjectDocument | None,
    ) -> SafeSaveResult:
        stage = _new_stage_path(destination, suffix=".geologpkg")
        backup: ProjectBackupRecord | None = None
        warnings: list[str] = []
        try:
            self.repository.save(document, stage)
            staged_document, staged_state = self.open_verified(stage)
            _assert_round_trip(document, staged_document)
            self._assert_target_unchanged(destination, baseline)
            if baseline is not None and previous_document is not None:
                backup = self._create_backup(previous_document, baseline)
                self._assert_target_unchanged(destination, baseline)
            os.replace(stage, destination)
            _fsync_directory(destination.parent)
        except Exception:
            _unlink_generated_file(stage)
            raise
        saved_state = _relocate_state(staged_state, destination)
        try:
            verified_state = self.inspect(destination)
            if not _same_project_state(saved_state, verified_state):
                warnings.append(
                    "Проект записан, но его состояние успело измениться до контрольного чтения."
                )
            else:
                saved_state = verified_state
        except Exception as exc:
            warnings.append(f"Проект записан; повторная проверка будет выполнена при открытии: {exc}")
        try:
            pruned, rotation_warnings = self._rotate_backups(destination)
        except Exception as exc:
            pruned = ()
            rotation_warnings = (f"Ротация резервных копий пропущена: {exc}",)
        warnings.extend(rotation_warnings)
        return SafeSaveResult(destination, saved_state, backup, pruned, tuple(warnings))

    def _save_legacy(
        self,
        document: ProjectDocument,
        destination: Path,
        *,
        baseline: ProjectDiskState | None,
        previous_document: ProjectDocument | None,
    ) -> SafeSaveResult:
        backup: ProjectBackupRecord | None = None
        temporary_root = Path(
            tempfile.mkdtemp(prefix=f".{destination.name}.stage-", dir=destination.parent)
        )
        stage = temporary_root / destination.name
        warnings: list[str] = []
        try:
            self.repository.save(document, stage)
            staged_document, staged_state = self.open_verified(stage)
            _assert_round_trip(document, staged_document)
            self._assert_target_unchanged(destination, baseline)
            if baseline is not None and previous_document is not None:
                backup = self._create_backup(previous_document, baseline)
                self._assert_target_unchanged(destination, baseline)
            _install_staged_legacy_assets(stage, destination)
            self._assert_target_unchanged(destination, baseline)
            os.replace(stage, destination)
            _fsync_directory(destination.parent)
        except Exception:
            shutil.rmtree(temporary_root, ignore_errors=True)
            raise
        shutil.rmtree(temporary_root, ignore_errors=True)

        saved_state = _relocate_state(staged_state, destination)
        try:
            verified_state = self.inspect(destination)
            if not _same_project_state(saved_state, verified_state):
                warnings.append(
                    "Legacy-проект записан, но изменился до контрольного чтения."
                )
            else:
                saved_state = verified_state
        except Exception as exc:
            warnings.append(
                f"Legacy-проект записан; повторная проверка будет выполнена при открытии: {exc}"
            )
        try:
            pruned, rotation_warnings = self._rotate_backups(destination)
        except Exception as exc:
            pruned = ()
            rotation_warnings = (f"Ротация резервных копий пропущена: {exc}",)
        warnings.extend(rotation_warnings)
        return SafeSaveResult(destination, saved_state, backup, pruned, tuple(warnings))

    def _assert_expected(
        self,
        destination: Path,
        expected: ProjectDiskState,
        current: ProjectDiskState,
    ) -> None:
        if expected.path_id != _path_id(destination) or not _same_project_state(expected, current):
            raise ProjectChangedExternallyError(
                "Проект в синхронизируемой папке изменён после открытия. "
                "Автоматическая перезапись отменена; сохраните работу как копию."
            )

    def _assert_target_unchanged(
        self,
        destination: Path,
        baseline: ProjectDiskState | None,
    ) -> None:
        if baseline is None:
            if _path_exists(destination) or destination.is_symlink():
                raise ProjectChangedExternallyError(
                    "Целевой файл появился во время сохранения. Выберите другое имя."
                )
            return
        try:
            current = self.inspect(destination)
        except Exception as exc:
            raise ProjectChangedExternallyError(
                "Не удалось повторно проверить проект перед заменой. "
                "Исходный файл не перезаписан."
            ) from exc
        if not _same_project_state(baseline, current):
            raise ProjectChangedExternallyError(
                "Проект изменён другим процессом во время сохранения. "
                "Исходный файл оставлен без изменений."
            )

    def _create_backup(
        self,
        document: ProjectDocument,
        state: ProjectDiskState,
    ) -> ProjectBackupRecord:
        root = state.path.parent / self.policy.directory_name
        _prepare_backup_root(root)
        with _backup_index_lock(root):
            records = list(self._load_index(root, missing_ok=True))
            record_id = uuid4().hex
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
            filename = (
                f"{state.path_id[:16]}-{timestamp}-r{state.save_revision}-{record_id}.geologpkg"
            )
            backup_path = root / filename
            try:
                self.package_repository.save(document, backup_path)
                fingerprint = _fingerprint_regular(backup_path)
                restored = self.package_repository.load(backup_path)
                _assert_round_trip(document, restored)
                record = ProjectBackupRecord(
                    record_id=record_id,
                    backup_path=backup_path,
                    source_path_id=state.path_id,
                    source_kind=state.storage_kind,
                    project_id=state.project_id,
                    save_revision=state.save_revision,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    size_bytes=fingerprint.size_bytes,
                    sha256=fingerprint.sha256,
                )
                records.append(record)
                self._write_index(root, records)
                return record
            except Exception:
                _unlink_generated_file(backup_path)
                raise

    def _rotate_backups(self, source: Path) -> tuple[tuple[Path, ...], tuple[str, ...]]:
        root = source.parent / self.policy.directory_name
        if not _path_exists(root):
            return (), ()
        pruned: list[Path] = []
        warnings: list[str] = []
        try:
            _validate_backup_root(root)
            with _backup_index_lock(root):
                records = list(self._load_index(root))
                source_id = _path_id(source)
                owned = sorted(
                    (record for record in records if record.source_path_id == source_id),
                    key=_record_sort_key,
                    reverse=True,
                )
                candidates = owned[self.policy.keep_last :]
                removable: list[ProjectBackupRecord] = []
                for record in candidates:
                    try:
                        self._validate_backup_record(record, recovery=False)
                    except ProjectFileSafetyError as exc:
                        warnings.append(f"Резервная копия не удалена: {exc}")
                    else:
                        removable.append(record)
                if not removable:
                    return (), tuple(warnings)
                remaining = [record for record in records if record not in removable]
                self._write_index(root, remaining)
                for record in removable:
                    try:
                        record.backup_path.unlink()
                    except OSError as exc:
                        warnings.append(
                            f"Не удалось удалить старую резервную копию {record.backup_path.name}: {exc}"
                        )
                    else:
                        pruned.append(record.backup_path)
        except ProjectFileSafetyError as exc:
            warnings.append(f"Ротация резервных копий пропущена: {exc}")
        return tuple(pruned), tuple(warnings)

    def _validate_backup_record(
        self,
        record: ProjectBackupRecord,
        *,
        recovery: bool,
    ) -> ProjectDocument:
        error_type = RecoveryValidationError if recovery else BackupValidationError
        root = record.backup_path.parent
        try:
            _validate_backup_root(root)
            if record.backup_path != root / record.backup_path.name:
                raise error_type("Путь резервной копии выходит за управляемый каталог")
            backup_stat = _regular_file_stat(record.backup_path)
            if _any_reparse(backup_stat):
                raise error_type("Резервная копия не может быть reparse-файлом")
            fingerprint = _fingerprint_regular(record.backup_path)
            if (
                fingerprint.size_bytes != record.size_bytes
                or fingerprint.sha256 != record.sha256
            ):
                raise error_type(
                    f"Контрольная сумма резервной копии не совпадает: {record.backup_path.name}"
                )
            document = self.package_repository.load(record.backup_path)
            if (
                document.project.project_id != record.project_id
                or document.project.save_revision != record.save_revision
            ):
                raise error_type(
                    f"Метаданные резервной копии не совпадают: {record.backup_path.name}"
                )
            return document
        except error_type:
            raise
        except Exception as exc:
            raise error_type(
                f"Резервная копия не прошла проверку: {record.backup_path.name}"
            ) from exc

    def _load_index(
        self,
        root: Path,
        *,
        missing_ok: bool = False,
    ) -> tuple[ProjectBackupRecord, ...]:
        index_path = root / _INDEX_NAME
        if not _path_exists(index_path):
            if missing_ok:
                return ()
            raise BackupValidationError("Индекс резервных копий отсутствует")
        try:
            if _regular_file_stat(index_path).st_size > _MAX_INDEX_BYTES:
                raise BackupValidationError("Индекс резервных копий превышает допустимый размер")
            payload_bytes = _read_regular_bytes(index_path)
            payload = json.loads(payload_bytes.decode("utf-8"))
        except Exception as exc:
            raise BackupValidationError("Индекс резервных копий повреждён") from exc
        if not isinstance(payload, dict):
            raise BackupValidationError("Индекс резервных копий должен быть объектом")
        if payload.get("format") != _INDEX_FORMAT or payload.get("version") != _INDEX_VERSION:
            raise BackupValidationError("Версия индекса резервных копий не поддерживается")
        raw_records = payload.get("records")
        if not isinstance(raw_records, list):
            raise BackupValidationError("Индекс резервных копий не содержит records")
        if len(raw_records) > _MAX_BACKUP_RECORDS:
            raise BackupValidationError("Индекс содержит слишком много резервных копий")
        records = tuple(_record_from_payload(root, raw) for raw in raw_records)
        if len({record.record_id for record in records}) != len(records):
            raise BackupValidationError("Индекс содержит повторяющиеся идентификаторы")
        return records

    def _write_index(self, root: Path, records: list[ProjectBackupRecord]) -> None:
        _validate_backup_root(root)
        payload = {
            "format": _INDEX_FORMAT,
            "version": _INDEX_VERSION,
            "records": [_record_to_payload(record) for record in records],
        }
        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{_INDEX_NAME}.", suffix=".tmp", dir=root
        )
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, root / _INDEX_NAME)
            _fsync_directory(root)
        except Exception:
            Path(temporary_name).unlink(missing_ok=True)
            raise


def _storage_kind(path: Path) -> str:
    return "package" if path.suffix.casefold() == ".geologpkg" else "legacy-json"


def _path_id(path: Path) -> str:
    normalized = os.path.normcase(os.path.abspath(os.path.normpath(os.fspath(path))))
    return sha256(os.fsencode(normalized)).hexdigest()


def _disk_state(
    path: Path,
    document: ProjectDocument,
    fingerprint: FileFingerprint,
    bundle_sha256: str,
) -> ProjectDiskState:
    return ProjectDiskState(
        path=path,
        path_id=_path_id(path),
        storage_kind=_storage_kind(path),
        project_id=document.project.project_id,
        save_revision=document.project.save_revision,
        fingerprint=fingerprint,
        bundle_sha256=bundle_sha256,
    )


def _relocate_state(state: ProjectDiskState, destination: Path) -> ProjectDiskState:
    return ProjectDiskState(
        path=destination,
        path_id=_path_id(destination),
        storage_kind=_storage_kind(destination),
        project_id=state.project_id,
        save_revision=state.save_revision,
        fingerprint=state.fingerprint,
        bundle_sha256=state.bundle_sha256,
    )


def _legacy_bundle_sha256(document: ProjectDocument, primary_sha256: str) -> str:
    digest = sha256()
    digest.update(b"geolog-legacy-bundle-v1\0")
    _digest_field(digest, "project", primary_sha256)
    for dataset_id, source in sorted(document.source_documents.items()):
        _digest_field(digest, f"source:{dataset_id}", source.sha256)
    for asset_id, asset in sorted(document.image_assets.items()):
        _digest_field(digest, f"image-id:{asset_id}", sha256(asset.payload).hexdigest())
        _digest_field(digest, f"image-name:{asset_id}", asset.original_name)
        _digest_field(digest, f"image-type:{asset_id}", asset.media_type)
    return digest.hexdigest()


def _digest_field(digest: Any, name: str, value: str) -> None:
    name_bytes = name.encode("utf-8")
    value_bytes = value.encode("utf-8")
    digest.update(len(name_bytes).to_bytes(4, "big"))
    digest.update(name_bytes)
    digest.update(len(value_bytes).to_bytes(8, "big"))
    digest.update(value_bytes)


def _same_payload(first: FileFingerprint, second: FileFingerprint) -> bool:
    return first.size_bytes == second.size_bytes and first.sha256 == second.sha256


def _same_project_state(first: ProjectDiskState, second: ProjectDiskState) -> bool:
    return (
        first.path_id == second.path_id
        and first.storage_kind == second.storage_kind
        and first.project_id == second.project_id
        and first.save_revision == second.save_revision
        and first.bundle_sha256 == second.bundle_sha256
    )


def _assert_round_trip(expected: ProjectDocument, actual: ProjectDocument) -> None:
    if (
        expected.project.project_id != actual.project.project_id
        or expected.project.save_revision != actual.project.save_revision
    ):
        raise ProjectFileSafetyError(
            "Проверка сохранённого проекта вернула другой project_id или save_revision"
        )


def _fingerprint_regular(path: Path) -> FileFingerprint:
    before = _regular_file_stat(path)
    digest = sha256()
    try:
        with path.open("rb") as stream:
            opened_before = os.fstat(stream.fileno())
            if not _same_stat_identity(before, opened_before):
                raise UnsafeProjectPathError("Файл проекта был подменён перед чтением")
            while chunk := stream.read(_HASH_CHUNK_BYTES):
                digest.update(chunk)
            opened_after = os.fstat(stream.fileno())
    except ProjectFileSafetyError:
        raise
    except OSError as exc:
        raise UnsafeProjectPathError(f"Не удалось безопасно прочитать файл проекта: {path}") from exc
    after = _regular_file_stat(path)
    if not _same_stat_identity(before, opened_after) or not _same_stat_identity(before, after):
        raise ProjectChangedExternallyError("Файл проекта изменился во время чтения")
    return FileFingerprint(
        size_bytes=before.st_size,
        mtime_ns=before.st_mtime_ns,
        sha256=digest.hexdigest(),
        device=before.st_dev,
        inode=before.st_ino,
    )


def _read_regular_bytes(path: Path) -> bytes:
    expected = _fingerprint_regular(path)
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise UnsafeProjectPathError(f"Не удалось прочитать файл: {path}") from exc
    actual = _fingerprint_regular(path)
    if not _same_payload(expected, actual) or len(payload) != expected.size_bytes:
        raise ProjectChangedExternallyError("Файл изменился во время чтения")
    return payload


def _regular_file_stat(path: Path) -> os.stat_result:
    try:
        result = path.lstat()
    except OSError as exc:
        raise UnsafeProjectPathError(f"Файл проекта не найден: {path}") from exc
    if not stat.S_ISREG(result.st_mode) or path.is_symlink() or _redirecting_reparse(result):
        raise UnsafeProjectPathError("Проект должен быть обычным файлом, а не ссылкой или каталогом")
    return result


def _same_stat_identity(first: os.stat_result, second: os.stat_result) -> bool:
    return (
        first.st_dev == second.st_dev
        and first.st_ino == second.st_ino
        and first.st_size == second.st_size
        and first.st_mtime_ns == second.st_mtime_ns
    )


def _redirecting_reparse(result: os.stat_result) -> bool:
    tag = int(getattr(result, "st_reparse_tag", 0) or 0)
    return tag in {_SYMLINK_REPARSE_TAG, _MOUNT_POINT_REPARSE_TAG}


def _any_reparse(result: os.stat_result) -> bool:
    file_attributes = int(getattr(result, "st_file_attributes", 0) or 0)
    reparse_attribute = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return bool(file_attributes & reparse_attribute) or bool(
        int(getattr(result, "st_reparse_tag", 0) or 0)
    )


def _path_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise UnsafeProjectPathError(f"Не удалось проверить путь: {path}") from exc
    return True


def _validate_target_entry(path: Path) -> None:
    try:
        result = path.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise UnsafeProjectPathError(f"Не удалось проверить целевой путь: {path}") from exc
    if not stat.S_ISREG(result.st_mode) or path.is_symlink() or _redirecting_reparse(result):
        raise UnsafeProjectPathError(
            "Целевой путь проекта должен быть обычным файлом, а не ссылкой или каталогом"
        )


def _prepare_backup_root(root: Path) -> None:
    if _path_exists(root):
        _validate_backup_root(root)
        return
    root.mkdir(parents=False, exist_ok=False)
    _validate_backup_root(root)


def _validate_backup_root(root: Path) -> None:
    try:
        result = root.lstat()
    except OSError as exc:
        raise BackupValidationError("Каталог резервных копий недоступен") from exc
    if not stat.S_ISDIR(result.st_mode) or root.is_symlink() or _any_reparse(result):
        raise BackupValidationError(
            "Каталог резервных копий не может быть ссылкой или перенаправлением"
        )


@contextmanager
def _backup_index_lock(root: Path) -> Iterator[None]:
    lock_path = root / _INDEX_LOCK_NAME
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except OSError as exc:
        raise BackupValidationError(
            "Индекс резервных копий занят другим процессом или остался незавершённый lock"
        ) from exc
    try:
        os.close(descriptor)
        yield
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _new_stage_path(destination: Path, *, suffix: str) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=f".stage{suffix}", dir=destination.parent
    )
    os.close(descriptor)
    stage = Path(temporary_name)
    stage.unlink()
    return stage


def _install_staged_legacy_assets(stage_project: Path, destination: Path) -> None:
    staged_root = stage_project.parent / f"{stage_project.name}.assets"
    if not _path_exists(staged_root):
        return
    _validate_managed_directory(staged_root, "Staging assets")
    final_root = destination.parent / f"{destination.name}.assets"
    if _path_exists(final_root):
        _validate_managed_directory(final_root, "Project assets")
    else:
        final_root.mkdir()
        _validate_managed_directory(final_root, "Project assets")

    entries = sorted(staged_root.rglob("*"), key=lambda item: item.as_posix().casefold())
    for staged in entries:
        relative = staged.relative_to(staged_root)
        staged_stat = staged.lstat()
        if staged.is_symlink() or _any_reparse(staged_stat):
            raise UnsafeProjectPathError("Staging assets содержат ссылку или reparse entry")
        target = final_root / relative
        if stat.S_ISDIR(staged_stat.st_mode):
            if _path_exists(target):
                _validate_managed_directory(target, "Project assets")
            else:
                target.mkdir()
                _validate_managed_directory(target, "Project assets")
            continue
        if not stat.S_ISREG(staged_stat.st_mode):
            raise UnsafeProjectPathError("Staging assets содержат не обычный файл")
        staged_fingerprint = _fingerprint_regular(staged)
        if _path_exists(target):
            target_stat = _regular_file_stat(target)
            if _any_reparse(target_stat):
                raise UnsafeProjectPathError("Project assets содержат reparse-файл")
            target_fingerprint = _fingerprint_regular(target)
            if not _same_payload(staged_fingerprint, target_fingerprint):
                raise ProjectFileSafetyError(
                    f"Существующий project asset не совпадает: {relative.as_posix()}"
                )
            continue
        _copy_verified_file(staged, target, staged_fingerprint)


def _validate_managed_directory(path: Path, label: str) -> None:
    try:
        result = path.lstat()
    except OSError as exc:
        raise UnsafeProjectPathError(f"{label} недоступен: {path}") from exc
    if not stat.S_ISDIR(result.st_mode) or path.is_symlink() or _any_reparse(result):
        raise UnsafeProjectPathError(f"{label} должен быть обычным каталогом")


def _copy_verified_file(
    source: Path,
    target: Path,
    expected: FileFingerprint,
) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copyfile(source, temporary)
        copied = _fingerprint_regular(temporary)
        if not _same_payload(expected, copied):
            raise ProjectFileSafetyError(f"Не удалось проверить скопированный asset: {target.name}")
        if _path_exists(target) or target.is_symlink():
            existing = _fingerprint_regular(target)
            if not _same_payload(expected, existing):
                raise ProjectFileSafetyError(
                    f"Project asset появился с другим содержимым: {target.name}"
                )
            return
        os.replace(temporary, target)
        _fsync_directory(target.parent)
    finally:
        _unlink_generated_file(temporary)


def _unlink_generated_file(path: Path) -> None:
    try:
        result = path.lstat()
    except FileNotFoundError:
        return
    except OSError:
        return
    if stat.S_ISREG(result.st_mode) or stat.S_ISLNK(result.st_mode):
        try:
            path.unlink()
        except OSError:
            pass


def _fsync_directory(directory: Path) -> None:
    if os.name == "nt":
        return
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _record_sort_key(record: ProjectBackupRecord) -> tuple[str, str]:
    return record.created_at, record.record_id


def _record_to_payload(record: ProjectBackupRecord) -> dict[str, object]:
    return {
        "record_id": record.record_id,
        "filename": record.backup_path.name,
        "source_path_id": record.source_path_id,
        "source_kind": record.source_kind,
        "project_id": record.project_id,
        "save_revision": record.save_revision,
        "created_at": record.created_at,
        "size_bytes": record.size_bytes,
        "sha256": record.sha256,
    }


def _record_from_payload(root: Path, raw: object) -> ProjectBackupRecord:
    if not isinstance(raw, dict):
        raise BackupValidationError("Запись индекса должна быть объектом")
    record_id = _required_string(raw, "record_id")
    filename = _required_string(raw, "filename")
    source_path_id = _required_digest(raw, "source_path_id")
    source_kind = _required_string(raw, "source_kind")
    project_id = _required_string(raw, "project_id")
    created_at = _required_string(raw, "created_at")
    digest = _required_digest(raw, "sha256")
    save_revision = _required_non_negative_int(raw, "save_revision")
    size_bytes = _required_non_negative_int(raw, "size_bytes")
    try:
        datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BackupValidationError("created_at резервной копии некорректен") from exc
    if (
        len(record_id) != 32
        or any(character not in "0123456789abcdef" for character in record_id)
        or Path(filename).name != filename
        or "/" in filename
        or "\\" in filename
        or not filename.casefold().endswith(".geologpkg")
        or source_kind not in {"package", "legacy-json"}
    ):
        raise BackupValidationError("Запись индекса содержит небезопасные метаданные")
    return ProjectBackupRecord(
        record_id=record_id,
        backup_path=root / filename,
        source_path_id=source_path_id,
        source_kind=source_kind,
        project_id=project_id,
        save_revision=save_revision,
        created_at=created_at,
        size_bytes=size_bytes,
        sha256=digest,
    )


def _required_string(raw: dict[str, object], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise BackupValidationError(f"Поле {key} резервной копии некорректно")
    return value


def _required_digest(raw: dict[str, object], key: str) -> str:
    value = _required_string(raw, key)
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise BackupValidationError(f"Поле {key} не является SHA-256")
    return value


def _required_non_negative_int(raw: dict[str, object], key: str) -> int:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise BackupValidationError(f"Поле {key} резервной копии некорректно")
    return value
