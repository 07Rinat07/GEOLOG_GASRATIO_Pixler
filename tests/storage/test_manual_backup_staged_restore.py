"""Opt-in staged backup restore integrates existing verified primitives safely."""
from __future__ import annotations

import shutil

import pytest

from geoworkbench.storage.manual_backup import (
    BackupError,
    BackupPlan,
    ManualBackupService,
)
from geoworkbench.storage import staged_restore_prepare as preparation
from geoworkbench.storage import staged_restore_publish as publication


@pytest.fixture
def saved_backup(tmp_path):
    project = tmp_path / "well.geologpkg"
    project.write_bytes(b"raw project" * 128)
    settings = tmp_path / "settings.ini"
    settings.write_bytes(b"[General]\\nlanguage=kk\\n")
    service = ManualBackupService()
    archive = service.create(
        BackupPlan.build((project,), settings), tmp_path / "backup.zip"
    )
    return service, archive, project, settings


def _stages(tmp_path):
    return list(tmp_path.glob(".geolog-restore-*"))


def test_staged_restore_roundtrip_without_exposed_partial_destination(
    saved_backup, tmp_path, monkeypatch
):
    service, archive, project, settings = saved_backup
    destination = tmp_path / "restored"
    original_prepare = preparation.prepare_staged_restore

    def confirm_not_published(plan, *, max_total_bytes):
        stage = original_prepare(plan, max_total_bytes=max_total_bytes)
        assert not destination.exists()
        assert stage.is_dir()
        return stage

    monkeypatch.setattr(preparation, "prepare_staged_restore", confirm_not_published)
    original_bytes = archive.read_bytes()
    assert service.restore_staged(archive, destination) == destination
    assert (destination / "projects" / "well.geologpkg").read_bytes() == (
        project.read_bytes()
    )
    assert (destination / "settings" / "preferences.ini").read_bytes() == (
        settings.read_bytes()
    )
    assert archive.read_bytes() == original_bytes
    assert _stages(tmp_path) == []


def test_staged_restore_settings_only(tmp_path):
    settings = tmp_path / "settings.ini"
    settings.write_bytes(b"language=ru")
    service = ManualBackupService()
    archive = service.create(BackupPlan.build((), settings), tmp_path / "backup.zip")
    destination = tmp_path / "new"
    assert service.restore_staged(archive, destination) == destination
    assert (destination / "settings" / "preferences.ini").read_bytes() == b"language=ru"
    assert not (destination / "projects").exists()
    assert _stages(tmp_path) == []


def test_staged_restore_refuses_preexisting_destination(saved_backup, tmp_path):
    service, archive, _, _ = saved_backup
    destination = tmp_path / "new"
    destination.mkdir()
    (destination / "keep").write_bytes(b"foreign")
    with pytest.raises(BackupError, match="already exists"):
        service.restore_staged(archive, destination)
    assert (destination / "keep").read_bytes() == b"foreign"
    assert _stages(tmp_path) == []


def test_staged_restore_rejects_too_small_budget_before_stage(
    saved_backup, tmp_path
):
    service, archive, _, _ = saved_backup
    destination = tmp_path / "new"
    with pytest.raises(BackupError, match="byte limit"):
        service.restore_staged(archive, destination, max_total_bytes=1)
    assert not destination.exists()
    assert _stages(tmp_path) == []


def test_staged_restore_destination_appears_after_preparation(
    saved_backup, tmp_path, monkeypatch
):
    service, archive, _, _ = saved_backup
    destination = tmp_path / "new"
    original = preparation.prepare_staged_restore

    def competing_destination(plan, *, max_total_bytes):
        stage = original(plan, max_total_bytes=max_total_bytes)
        destination.mkdir()
        (destination / "keep").write_bytes(b"foreign")
        return stage

    monkeypatch.setattr(preparation, "prepare_staged_restore", competing_destination)
    with pytest.raises(BackupError):
        service.restore_staged(archive, destination)
    assert (destination / "keep").read_bytes() == b"foreign"
    assert _stages(tmp_path) == []


def test_staged_restore_destination_appears_during_atomic_publish(
    saved_backup, tmp_path, monkeypatch
):
    service, archive, _, _ = saved_backup
    destination = tmp_path / "new"
    original = publication.publish_new_directory

    def competing_writer(stage, target):
        target.mkdir()
        (target / "keep").write_bytes(b"foreign")
        return original(stage, target)

    monkeypatch.setattr(publication, "publish_new_directory", competing_writer)
    with pytest.raises(BackupError, match="Cannot publish"):
        service.restore_staged(archive, destination)
    assert (destination / "keep").read_bytes() == b"foreign"
    assert _stages(tmp_path) == []


def test_staged_restore_rejects_modified_archive_after_preparation(
    saved_backup, tmp_path, monkeypatch
):
    service, archive, _, _ = saved_backup
    destination = tmp_path / "new"
    original = preparation.prepare_staged_restore

    def modify_archive(plan, *, max_total_bytes):
        stage = original(plan, max_total_bytes=max_total_bytes)
        archive.write_bytes(b"not a zip")
        return stage

    monkeypatch.setattr(preparation, "prepare_staged_restore", modify_archive)
    with pytest.raises(BackupError):
        service.restore_staged(archive, destination)
    assert not destination.exists()
    assert _stages(tmp_path) == []


def test_staged_restore_rejects_changed_stage_at_receipt_and_preserves_it(
    saved_backup, tmp_path, monkeypatch
):
    service, archive, _, _ = saved_backup
    destination = tmp_path / "new"
    original = preparation.prepare_staged_restore

    def add_foreign_file(plan, *, max_total_bytes):
        stage = original(plan, max_total_bytes=max_total_bytes)
        (stage / "projects" / "foreign.txt").write_bytes(b"foreign")
        return stage

    monkeypatch.setattr(preparation, "prepare_staged_restore", add_foreign_file)
    try:
        with pytest.raises(BackupError, match="Unexpected or missing"):
            service.restore_staged(archive, destination)
        stages = _stages(tmp_path)
        assert len(stages) == 1
        assert (stages[0] / "projects" / "foreign.txt").read_bytes() == b"foreign"
        assert not destination.exists()
    finally:
        for stage in _stages(tmp_path):
            shutil.rmtree(stage)


def test_staged_restore_preserves_foreign_replacement_after_receipt(
    saved_backup, tmp_path, monkeypatch
):
    service, archive, _, _ = saved_backup
    destination = tmp_path / "new"

    def foreign_replacement(_plan, stage, *, max_total_bytes):
        path = stage / "projects" / "well.geologpkg"
        path.unlink()
        path.write_bytes(b"foreign replacement")
        raise BackupError("staged content changed before publication")

    monkeypatch.setattr(
        publication, "publish_verified_staged_restore", foreign_replacement
    )
    try:
        with pytest.raises(BackupError, match="staged content changed"):
            service.restore_staged(archive, destination)
        stages = _stages(tmp_path)
        assert len(stages) == 1
        assert (stages[0] / "projects" / "well.geologpkg").read_bytes() == (
            b"foreign replacement"
        )
        assert not destination.exists()
    finally:
        for stage in _stages(tmp_path):
            shutil.rmtree(stage)


def test_staged_restore_cleans_owned_stage_after_failed_publisher(
    saved_backup, tmp_path, monkeypatch
):
    service, archive, _, _ = saved_backup
    destination = tmp_path / "new"

    def no_publish(_plan, _stage, *, max_total_bytes):
        raise BackupError("simulated publisher failure")

    monkeypatch.setattr(publication, "publish_verified_staged_restore", no_publish)
    with pytest.raises(BackupError, match="simulated publisher failure"):
        service.restore_staged(archive, destination)
    assert not destination.exists()
    assert _stages(tmp_path) == []
