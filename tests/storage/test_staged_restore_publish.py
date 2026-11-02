"""Revalidated, no-replace staging publication does not touch existing data."""
from __future__ import annotations

from dataclasses import replace
import shutil
import sys

import pytest

from geoworkbench.storage.atomic_directory_publish import (
    AtomicDirectoryPublicationUnsupported,
)
from geoworkbench.storage.manual_backup import (
    BackupError,
    BackupPlan,
    ManualBackupService,
)
from geoworkbench.storage.staged_restore_prepare import prepare_staged_restore
from geoworkbench.storage import staged_restore_publish as publishing


@pytest.fixture
def prepared(tmp_path):
    project = tmp_path / "well.geologpkg"
    project.write_bytes(b"well data" * 20)
    settings = tmp_path / "prefs.ini"
    settings.write_bytes(b"language=ru")
    service = ManualBackupService()
    archive = service.create(
        BackupPlan.build((project,), settings), tmp_path / "backup.zip"
    )
    plan = service.plan_restore(archive, tmp_path / "recovered")
    stage = prepare_staged_restore(plan)
    yield plan, stage
    if stage.exists():
        shutil.rmtree(stage)


@pytest.mark.skipif(
    not (sys.platform == "win32" or sys.platform.startswith("linux")),
    reason="No verified OS-level no-replace directory operation",
)
def test_publish_verified_stage_to_new_destination(prepared):
    plan, stage = prepared
    result = publishing.publish_verified_staged_restore(plan, stage)
    assert result == plan.destination
    assert not stage.exists()
    assert (result / "projects" / "well.geologpkg").read_bytes() == b"well data" * 20
    assert (result / "settings" / "preferences.ini").read_bytes() == b"language=ru"


@pytest.mark.skipif(
    not (sys.platform == "win32" or sys.platform.startswith("linux")),
    reason="No verified OS-level no-replace directory operation",
)
def test_publish_settings_only(tmp_path):
    settings = tmp_path / "preferences.ini"
    settings.write_bytes(b"language=kk")
    service = ManualBackupService()
    archive = service.create(BackupPlan.build((), settings), tmp_path / "settings.zip")
    plan = service.plan_restore(archive, tmp_path / "restored")
    stage = prepare_staged_restore(plan)
    try:
        assert publishing.publish_verified_staged_restore(plan, stage) == plan.destination
        assert (plan.destination / "settings" / "preferences.ini").read_bytes() == (
            b"language=kk"
        )
        assert not (plan.destination / "projects").exists()
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def test_rejects_stale_plan_without_publication(prepared):
    plan, stage = prepared
    stale = replace(plan, total_bytes=plan.total_bytes + 1)
    with pytest.raises(BackupError, match="changed before staging publication"):
        publishing.publish_verified_staged_restore(stale, stage)
    assert stage.is_dir()
    assert not plan.destination.exists()


def test_rejects_modified_archive_without_publication(prepared):
    plan, stage = prepared
    plan.archive.write_bytes(b"invalid ZIP")
    with pytest.raises(BackupError):
        publishing.publish_verified_staged_restore(plan, stage)
    assert stage.is_dir()
    assert not plan.destination.exists()


def test_rejects_corrupted_stage_without_publication(prepared):
    plan, stage = prepared
    (stage / "projects" / "well.geologpkg").write_bytes(b"tampered")
    with pytest.raises(BackupError, match="checksum|size"):
        publishing.publish_verified_staged_restore(plan, stage)
    assert stage.is_dir()
    assert not plan.destination.exists()


def test_rejects_extra_staged_entry_without_publication(prepared):
    plan, stage = prepared
    (stage / "projects" / "foreign.geologpkg").write_bytes(b"foreign")
    with pytest.raises(BackupError, match="Unexpected or missing staged file"):
        publishing.publish_verified_staged_restore(plan, stage)
    assert stage.is_dir()
    assert not plan.destination.exists()


def test_rejects_occupied_destination_and_preserves_foreign_files(prepared):
    plan, stage = prepared
    plan.destination.mkdir()
    (plan.destination / "keep").write_bytes(b"foreign")
    with pytest.raises(BackupError):
        publishing.publish_verified_staged_restore(plan, stage)
    assert (plan.destination / "keep").read_bytes() == b"foreign"
    assert stage.is_dir()


@pytest.mark.skipif(
    not (sys.platform == "win32" or sys.platform.startswith("linux")),
    reason="No verified OS-level no-replace directory operation",
)
def test_destination_created_after_verification_cannot_be_replaced(prepared, monkeypatch):
    plan, stage = prepared
    original = publishing.publish_new_directory

    def competing_writer(source, destination):
        destination.mkdir()
        (destination / "keep").write_bytes(b"foreign")
        return original(source, destination)

    monkeypatch.setattr(publishing, "publish_new_directory", competing_writer)
    with pytest.raises(BackupError, match="Cannot publish"):
        publishing.publish_verified_staged_restore(plan, stage)
    assert (plan.destination / "keep").read_bytes() == b"foreign"
    assert stage.is_dir()


def test_unsupported_publication_keeps_complete_stage(prepared, monkeypatch):
    plan, stage = prepared

    def unsupported(_source, _destination):
        raise AtomicDirectoryPublicationUnsupported("no OS guarantee")

    monkeypatch.setattr(publishing, "publish_new_directory", unsupported)
    with pytest.raises(BackupError, match="no OS guarantee"):
        publishing.publish_verified_staged_restore(plan, stage)
    assert stage.is_dir()
    assert not plan.destination.exists()


def test_rejects_wrong_stage_path_without_publication(prepared, tmp_path):
    plan, stage = prepared
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(BackupError):
        publishing.publish_verified_staged_restore(plan, other)
    assert stage.is_dir()
    assert not plan.destination.exists()
