"""Cleanup receipts preserve replaced and unknown files in restore stages."""
from __future__ import annotations

import shutil

import pytest

from geoworkbench.storage.manual_backup import BackupError, BackupPlan, ManualBackupService
from geoworkbench.storage.staged_restore_prepare import prepare_staged_restore
from geoworkbench.storage.staged_restore_cleanup import (
    capture_owned_staging_receipt, cleanup_owned_staging,
)


@pytest.fixture
def owned_stage(tmp_path):
    project = tmp_path / "well.geologpkg"
    project.write_bytes(b"well content")
    settings = tmp_path / "prefs.ini"
    settings.write_bytes(b"language=ru")
    service = ManualBackupService()
    archive = service.create(
        BackupPlan.build((project,), settings), tmp_path / "backup.zip"
    )
    plan = service.plan_restore(archive, tmp_path / "restored")
    stage = prepare_staged_restore(plan)
    receipt = capture_owned_staging_receipt(plan, stage)
    yield plan, stage, receipt
    if stage.is_dir() and not stage.is_symlink():
        shutil.rmtree(stage)


def test_cleanup_removes_only_owned_complete_staging(owned_stage):
    plan, stage, receipt = owned_stage
    assert cleanup_owned_staging(receipt) is True
    assert not stage.exists()
    assert not plan.destination.exists()


def test_cleanup_preserves_foreign_added_file(owned_stage):
    plan, stage, receipt = owned_stage
    foreign = stage / "projects" / "keep.txt"
    foreign.write_bytes(b"other writer")
    assert cleanup_owned_staging(receipt) is False
    assert foreign.read_bytes() == b"other writer"
    assert not plan.destination.exists()


def test_cleanup_preserves_replaced_file_even_if_bytes_match(owned_stage):
    plan, stage, receipt = owned_stage
    output = stage / "projects" / "well.geologpkg"
    before = output.read_bytes()
    output.unlink()
    output.write_bytes(before)
    assert cleanup_owned_staging(receipt) is False
    assert output.read_bytes() == before
    assert not plan.destination.exists()


def test_cleanup_preserves_modified_file(owned_stage):
    _, stage, receipt = owned_stage
    output = stage / "projects" / "well.geologpkg"
    output.write_bytes(b"foreign changes to staged bytes")
    assert cleanup_owned_staging(receipt) is False
    assert output.read_bytes() == b"foreign changes to staged bytes"


def test_cleanup_preserves_replaced_subdirectory(owned_stage):
    _, stage, receipt = owned_stage
    folder = stage / "projects"
    shutil.rmtree(folder)
    folder.mkdir()
    (folder / "keep.txt").write_bytes(b"foreign")
    assert cleanup_owned_staging(receipt) is False
    assert (folder / "keep.txt").read_bytes() == b"foreign"


def test_cleanup_preserves_replaced_root_symlink(owned_stage, tmp_path):
    _, stage, receipt = owned_stage
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "keep").write_bytes(b"foreign")
    original = tmp_path / "old_stage"
    stage.rename(original)
    try:
        try:
            stage.symlink_to(elsewhere, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            pytest.skip(f"Cannot create symlink on this runner: {exc}")
        assert cleanup_owned_staging(receipt) is False
        assert (elsewhere / "keep").read_bytes() == b"foreign"
        assert (original / "projects" / "well.geologpkg").is_file()
    finally:
        if stage.is_symlink():
            stage.unlink()
        if original.is_dir():
            shutil.rmtree(original)


def test_capture_rejects_unverified_stage(owned_stage):
    plan, stage, _ = owned_stage
    (stage / "projects" / "extra.txt").write_bytes(b"unexpected")
    with pytest.raises(BackupError, match="Unexpected or missing"):
        capture_owned_staging_receipt(plan, stage)


def test_cleanup_does_not_delete_replaced_path_symlink(owned_stage, tmp_path):
    _, stage, receipt = owned_stage
    target = tmp_path / "untouched.txt"
    target.write_bytes(b"external")
    path = stage / "projects" / "well.geologpkg"
    path.unlink()
    try:
        path.symlink_to(target)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Cannot create symlink on this runner: {exc}")
    assert cleanup_owned_staging(receipt) is False
    assert target.read_bytes() == b"external"
    assert path.is_symlink()
