"""Independent backup staging preparation; never publishes the restore."""
from __future__ import annotations

import shutil

import pytest

from geoworkbench.storage.manual_backup import (
    BackupError,
    BackupPlan,
    BackupRestorePlan,
    ManualBackupService,
)
from geoworkbench.storage import staged_restore_prepare as preparation
from geoworkbench.storage.staged_restore_verify import verify_staged_restore


@pytest.fixture
def restore_plan(tmp_path):
    project = tmp_path / "well.geologpkg"
    project.write_bytes(b"geology" * 128)
    settings = tmp_path / "prefs.ini"
    settings.write_bytes(b"language=ru")
    service = ManualBackupService()
    archive = service.create(
        BackupPlan.build((project,), settings), tmp_path / "backup.zip"
    )
    return service.plan_restore(archive, tmp_path / "restored")


def test_prepare_staging_verifies_both_members_without_publishing(restore_plan):
    stage = preparation.prepare_staged_restore(restore_plan)
    try:
        assert stage.name.startswith(".geolog-restore-")
        assert stage.parent == restore_plan.destination.parent
        assert not restore_plan.destination.exists()
        assert (stage / "projects" / "well.geologpkg").read_bytes() == (
            b"geology" * 128
        )
        assert (stage / "settings" / "preferences.ini").read_bytes() == (
            b"language=ru"
        )
        verify_staged_restore(restore_plan, stage)
    finally:
        shutil.rmtree(stage)


def test_prepare_settings_only_staging(tmp_path):
    settings = tmp_path / "prefs.ini"
    settings.write_bytes(b"language=kk")
    service = ManualBackupService()
    archive = service.create(BackupPlan.build((), settings), tmp_path / "one.zip")
    plan = service.plan_restore(archive, tmp_path / "restored")
    stage = preparation.prepare_staged_restore(plan)
    try:
        assert sorted(path.name for path in stage.iterdir()) == ["settings"]
        verify_staged_restore(plan, stage)
        assert not plan.destination.exists()
    finally:
        shutil.rmtree(stage)


def test_prepare_rejects_stale_plan_without_creating_staging(restore_plan):
    stale = BackupRestorePlan(
        restore_plan.archive,
        restore_plan.destination,
        restore_plan.items,
        restore_plan.total_bytes + 1,
    )
    with pytest.raises(BackupError, match="changed since preflight"):
        preparation.prepare_staged_restore(stale)
    assert not list(restore_plan.destination.parent.glob(".geolog-restore-*"))


def test_prepare_rejects_existing_destination_without_staging(restore_plan):
    restore_plan.destination.mkdir()
    with pytest.raises(BackupError, match="already exists"):
        preparation.prepare_staged_restore(restore_plan)
    assert restore_plan.destination.is_dir()
    assert not list(restore_plan.destination.parent.glob(".geolog-restore-*"))


def test_prepare_rejects_corrupted_archive_before_writing(restore_plan):
    restore_plan.archive.write_bytes(b"not a ZIP")
    with pytest.raises(BackupError):
        preparation.prepare_staged_restore(restore_plan)
    assert not list(restore_plan.destination.parent.glob(".geolog-restore-*"))


def test_prepare_cleans_only_its_own_partial_files_on_write_error(
    restore_plan, monkeypatch
):
    original = ManualBackupService._copy

    def fail_during_staging(self, source, target):
        if target is not None:
            target.write(b"partial")
            raise OSError("simulated write error")
        return original(self, source, target)

    monkeypatch.setattr(ManualBackupService, "_copy", fail_during_staging)
    with pytest.raises(BackupError, match="simulated write error"):
        preparation.prepare_staged_restore(restore_plan)
    assert not restore_plan.destination.exists()
    assert not list(restore_plan.destination.parent.glob(".geolog-restore-*"))


def test_prepare_preserves_foreign_replacement_during_cleanup(
    restore_plan, monkeypatch
):
    def replace_and_fail(plan, stage):
        path = stage / "projects" / "well.geologpkg"
        path.unlink()
        path.write_bytes(b"foreign replacement")
        raise BackupError("staging replaced after write")

    monkeypatch.setattr(preparation, "verify_staged_restore", replace_and_fail)
    with pytest.raises(BackupError, match="replaced after write"):
        preparation.prepare_staged_restore(restore_plan)
    stages = list(restore_plan.destination.parent.glob(".geolog-restore-*"))
    assert len(stages) == 1
    try:
        assert (stages[0] / "projects" / "well.geologpkg").read_bytes() == (
            b"foreign replacement"
        )
        assert not restore_plan.destination.exists()
    finally:
        shutil.rmtree(stages[0])


def test_prepare_rejects_concurrent_destination_without_publishing(
    restore_plan, monkeypatch
):
    original = ManualBackupService._copy
    appeared = False

    def claim_destination(self, source, target):
        nonlocal appeared
        if target is not None and not appeared:
            appeared = True
            restore_plan.destination.mkdir()
        return original(self, source, target)

    monkeypatch.setattr(ManualBackupService, "_copy", claim_destination)
    with pytest.raises(BackupError, match="occupied"):
        preparation.prepare_staged_restore(restore_plan)
    assert appeared
    assert restore_plan.destination.is_dir()
    assert not list(restore_plan.destination.parent.glob(".geolog-restore-*"))
