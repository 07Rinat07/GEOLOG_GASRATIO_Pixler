from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import shutil

import numpy as np
import pytest

from geoworkbench.data.lossless_las import parse_lossless_las
from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, Project, Well
from geoworkbench.storage.package_project_repository import PackageProjectRepository
from geoworkbench.storage.project_codec import ProjectDocument
from geoworkbench.storage.project_file_safety import (
    BackupPolicy,
    BackupValidationError,
    LegacyAutosaveRequiresPackageError,
    ProjectChangedExternallyError,
    ProjectFileSafetyService,
    RecoveryValidationError,
    SaveMode,
    UnsafeProjectPathError,
)
from geoworkbench.storage.project_repository_router import ProjectRepositoryRouter


def _document(
    name: str,
    *,
    project_id: str = "project-1",
    save_revision: int = 1,
    raw_las: bytes | None = None,
) -> ProjectDocument:
    dataset = Dataset(
        dataset_id="dataset-1",
        name="Dataset",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.asarray([1000.0, 1000.5], dtype=float),
    )
    well = Well("well-1", "Well", datasets={dataset.dataset_id: dataset})
    document = ProjectDocument(
        Project(
            project_id,
            name,
            wells={well.well_id: well},
            save_revision=save_revision,
        )
    )
    if raw_las is not None:
        document.source_documents[dataset.dataset_id] = parse_lossless_las(raw_las)
    return document


class _FailingStageRepository:
    """ProjectRepository test double that simulates an interrupted stage write."""

    def __init__(self) -> None:
        self.delegate = ProjectRepositoryRouter()

    def load(self, source: Path) -> ProjectDocument:
        return self.delegate.load(source)

    def save(self, document: ProjectDocument, target: Path) -> None:
        target.write_bytes(b"partial staging payload")
        raise OSError("simulated staging failure")


class _MutatingLoadRepository:
    def __init__(self, watched: Path) -> None:
        self.delegate = ProjectRepositoryRouter()
        self.watched = watched
        self.mutated = False

    def load(self, source: Path) -> ProjectDocument:
        document = self.delegate.load(source)
        if source == self.watched and not self.mutated:
            self.watched.write_bytes(self.watched.read_bytes() + b"external")
            self.mutated = True
        return document

    def save(self, document: ProjectDocument, target: Path) -> None:
        self.delegate.save(document, target)


class _RotationFailureService(ProjectFileSafetyService):
    def _rotate_backups(self, source: Path) -> tuple[tuple[Path, ...], tuple[str, ...]]:
        raise OSError(f"rotation unavailable: {source.name}")


def test_first_package_save_is_verified_and_can_be_opened(tmp_path: Path) -> None:
    service = ProjectFileSafetyService()
    target = tmp_path / "well.geologpkg"
    original = _document("Initial project")

    result = service.save(original, target, expected=None)
    restored, state = service.open_verified(target)

    assert result.path == target
    assert result.backup is None
    assert result.warnings == ()
    assert result.disk_state == state
    assert state.storage_kind == "package"
    assert state.project_id == "project-1"
    assert state.save_revision == 1
    assert state.fingerprint.sha256 == sha256(target.read_bytes()).hexdigest()
    assert restored.project.name == "Initial project"
    assert service.recovery_candidates(target) == ()


def test_verified_open_rejects_file_changed_during_repository_load(tmp_path: Path) -> None:
    target = tmp_path / "well.geologpkg"
    ProjectFileSafetyService().save(_document("Stable"), target, expected=None)
    service = ProjectFileSafetyService(repository=_MutatingLoadRepository(target))

    with pytest.raises(ProjectChangedExternallyError, match="во время открытия"):
        service.open_verified(target)


def test_rotation_failure_after_commit_is_reported_as_warning_not_save_failure(
    tmp_path: Path,
) -> None:
    service = _RotationFailureService()
    target = tmp_path / "well.geologpkg"

    result = service.save(_document("Committed"), target, expected=None)
    restored, state = ProjectFileSafetyService().open_verified(target)

    assert restored.project.name == "Committed"
    assert state.bundle_sha256 == result.disk_state.bundle_sha256
    assert result.warnings and "rotation unavailable" in result.warnings[0]


def test_overwrite_creates_candidate_that_can_be_restored_as_copy(tmp_path: Path) -> None:
    service = ProjectFileSafetyService()
    target = tmp_path / "well.geologpkg"
    first = service.save(_document("Revision one", save_revision=1), target, expected=None)

    second = service.save(
        _document("Revision two", save_revision=2),
        target,
        expected=first.disk_state,
    )

    assert second.backup is not None
    assert second.backup.source_kind == "package"
    assert second.backup.save_revision == 1
    assert service.recovery_candidates(target) == (second.backup,)

    restored_path = tmp_path / "well-recovered.geologpkg"
    restored_state = service.restore_as_copy(second.backup, restored_path)
    restored, verified_state = service.open_verified(restored_path)
    canonical, _canonical_state = service.open_verified(target)

    assert restored_state == verified_state
    assert restored.project.name == "Revision one"
    assert restored.project.save_revision == 1
    assert canonical.project.name == "Revision two"
    assert canonical.project.save_revision == 2


def test_external_same_size_same_mtime_change_blocks_save_and_preserves_bytes(
    tmp_path: Path,
) -> None:
    service = ProjectFileSafetyService()
    target = tmp_path / "well.geolog.json"
    first = service.save(_document("Alpha", save_revision=1), target, expected=None)
    initial_stat = target.stat()
    external = target.read_bytes().replace(b'"Alpha"', b'"Bravo"', 1)
    assert len(external) == initial_stat.st_size
    target.write_bytes(external)
    os.utime(target, ns=(initial_stat.st_atime_ns, initial_stat.st_mtime_ns))
    assert target.stat().st_size == initial_stat.st_size
    assert target.stat().st_mtime_ns == initial_stat.st_mtime_ns

    with pytest.raises(ProjectChangedExternallyError):
        service.save(
            _document("Local edit", save_revision=2),
            target,
            expected=first.disk_state,
        )

    assert target.read_bytes() == external
    assert service.inspect(target).bundle_sha256 != first.disk_state.bundle_sha256
    assert service.recovery_candidates(target) == ()


def test_staging_failure_preserves_canonical_package(tmp_path: Path) -> None:
    target = tmp_path / "well.geologpkg"
    initial_service = ProjectFileSafetyService()
    first = initial_service.save(_document("Stable", save_revision=1), target, expected=None)
    canonical_bytes = target.read_bytes()
    failing_service = ProjectFileSafetyService(repository=_FailingStageRepository())

    with pytest.raises(OSError, match="simulated staging failure"):
        failing_service.save(
            _document("Uncommitted", save_revision=2),
            target,
            expected=first.disk_state,
        )

    assert target.read_bytes() == canonical_bytes
    assert not [path for path in tmp_path.iterdir() if ".stage.geologpkg" in path.name]
    restored, state = initial_service.open_verified(target)
    assert restored.project.name == "Stable"
    assert state == first.disk_state
    assert initial_service.recovery_candidates(target) == ()


def test_rotation_is_scoped_to_source_and_keeps_unrelated_files(tmp_path: Path) -> None:
    service = ProjectFileSafetyService(policy=BackupPolicy(keep_last=1))
    first_path = tmp_path / "first.geologpkg"
    second_path = tmp_path / "second.geologpkg"
    first_state = service.save(
        _document("First A", project_id="project-a", save_revision=1),
        first_path,
        expected=None,
    ).disk_state
    old_first_backup = service.save(
        _document("First B", project_id="project-a", save_revision=2),
        first_path,
        expected=first_state,
    ).backup
    assert old_first_backup is not None

    second_state = service.save(
        _document("Second A", project_id="project-b", save_revision=1),
        second_path,
        expected=None,
    ).disk_state
    second_backup = service.save(
        _document("Second B", project_id="project-b", save_revision=2),
        second_path,
        expected=second_state,
    ).backup
    assert second_backup is not None

    backup_root = old_first_backup.backup_path.parent
    notes = backup_root / "operator-notes.txt"
    unmanaged_package = backup_root / "unmanaged.geologpkg"
    notes.write_text("do not rotate", encoding="utf-8")
    unmanaged_package.write_bytes(b"not an indexed backup")

    current_first_state = service.inspect(first_path)
    rotated = service.save(
        _document("First C", project_id="project-a", save_revision=3),
        first_path,
        expected=current_first_state,
    )

    assert rotated.backup is not None
    assert rotated.pruned == (old_first_backup.backup_path,)
    assert not old_first_backup.backup_path.exists()
    assert service.recovery_candidates(first_path) == (rotated.backup,)
    assert service.recovery_candidates(second_path) == (second_backup,)
    assert second_backup.backup_path.exists()
    assert notes.read_text(encoding="utf-8") == "do not rotate"
    assert unmanaged_package.read_bytes() == b"not an indexed backup"


def test_legacy_backup_is_self_contained_with_raw_las(tmp_path: Path) -> None:
    raw_las = b"~V\nVERS. 2.0\n~A\n1000 1\n1000.5 2\n"
    service = ProjectFileSafetyService()
    target = tmp_path / "legacy.geolog.json"
    first = service.save(
        _document("Legacy one", save_revision=1, raw_las=raw_las),
        target,
        expected=None,
    )
    second = service.save(
        _document("Legacy two", save_revision=2, raw_las=raw_las),
        target,
        expected=first.disk_state,
    )
    assert second.backup is not None
    assert second.backup.source_kind == "legacy-json"

    target.unlink()
    shutil.rmtree(tmp_path / f"{target.name}.assets")
    restored = PackageProjectRepository().load(second.backup.backup_path)

    assert restored.project.name == "Legacy one"
    assert restored.project.save_revision == 1
    assert restored.source_documents["dataset-1"].to_bytes() == raw_las


def test_material_autosave_rejects_legacy_without_mutating_it(tmp_path: Path) -> None:
    service = ProjectFileSafetyService()
    target = tmp_path / "legacy.geolog.json"
    first = service.save(_document("Legacy", save_revision=1), target, expected=None)
    canonical_bytes = target.read_bytes()

    with pytest.raises(LegacyAutosaveRequiresPackageError, match=r"\.geologpkg"):
        service.save(
            _document("Autosave", save_revision=2),
            target,
            expected=first.disk_state,
            mode=SaveMode.MATERIAL_AUTOSAVE,
        )

    assert target.read_bytes() == canonical_bytes
    assert service.recovery_candidates(target) == ()


def test_save_rejects_directory_target(tmp_path: Path) -> None:
    service = ProjectFileSafetyService()
    directory_target = tmp_path / "directory.geologpkg"
    directory_target.mkdir()

    with pytest.raises(UnsafeProjectPathError):
        service.save(_document("Unsafe"), directory_target, expected=None)


def test_save_rejects_symlink_target(tmp_path: Path, symlink_or_skip) -> None:
    service = ProjectFileSafetyService()
    outside = tmp_path / "outside.geologpkg"
    outside.write_bytes(b"outside")
    symlink_target = tmp_path / "symlink.geologpkg"
    symlink_or_skip(symlink_target, outside)

    with pytest.raises(UnsafeProjectPathError):
        service.save(_document("Unsafe"), symlink_target, expected=None)
    assert outside.read_bytes() == b"outside"


def test_restore_as_copy_refuses_existing_target_without_overwrite(tmp_path: Path) -> None:
    service = ProjectFileSafetyService()
    source = tmp_path / "source.geologpkg"
    first = service.save(_document("First", save_revision=1), source, expected=None)
    second = service.save(
        _document("Second", save_revision=2),
        source,
        expected=first.disk_state,
    )
    assert second.backup is not None
    existing = tmp_path / "existing.geologpkg"
    existing.write_bytes(b"operator-owned bytes")

    with pytest.raises(RecoveryValidationError, match="не перезаписывает"):
        service.restore_as_copy(second.backup, existing)

    assert existing.read_bytes() == b"operator-owned bytes"


def test_tampered_backup_is_never_offered_or_restored(tmp_path: Path) -> None:
    service = ProjectFileSafetyService()
    source = tmp_path / "source.geologpkg"
    first = service.save(_document("First", save_revision=1), source, expected=None)
    second = service.save(
        _document("Second", save_revision=2),
        source,
        expected=first.disk_state,
    )
    assert second.backup is not None
    payload = bytearray(second.backup.backup_path.read_bytes())
    payload[len(payload) // 2] ^= 0x01
    second.backup.backup_path.write_bytes(payload)

    with pytest.raises(RecoveryValidationError, match="Контрольная сумма"):
        service.recovery_candidates(source)
    with pytest.raises(RecoveryValidationError):
        service.restore_as_copy(second.backup, tmp_path / "restored.geologpkg")


def test_backup_index_path_escape_is_rejected_without_touching_canonical(tmp_path: Path) -> None:
    service = ProjectFileSafetyService()
    source = tmp_path / "source.geologpkg"
    first = service.save(_document("First", save_revision=1), source, expected=None)
    second = service.save(
        _document("Second", save_revision=2),
        source,
        expected=first.disk_state,
    )
    assert second.backup is not None
    canonical = source.read_bytes()
    index = second.backup.backup_path.parent / "index.v1.json"
    payload = json.loads(index.read_text(encoding="utf-8"))
    payload["records"][0]["filename"] = "../outside.geologpkg"
    index.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(BackupValidationError, match="небезопасные метаданные"):
        service.recovery_candidates(source)

    assert source.read_bytes() == canonical


def test_symlinked_backup_root_blocks_overwrite_before_canonical_mutation(
    tmp_path: Path,
    symlink_or_skip,
) -> None:
    service = ProjectFileSafetyService()
    source = tmp_path / "source.geologpkg"
    first = service.save(_document("First", save_revision=1), source, expected=None)
    canonical = source.read_bytes()
    outside = tmp_path / "outside"
    outside.mkdir()
    symlink_or_skip(tmp_path / ".geolog-backups", outside, target_is_directory=True)

    with pytest.raises(BackupValidationError):
        service.save(
            _document("Second", save_revision=2),
            source,
            expected=first.disk_state,
        )

    assert source.read_bytes() == canonical


def test_backup_policy_rejects_non_integer_retention() -> None:
    with pytest.raises(ValueError, match="положительным целым"):
        BackupPolicy(keep_last=1.5)  # type: ignore[arg-type]
