"""Read-only candidate inventory must not infer ownership or remove data."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from geoworkbench.storage.manual_backup import BackupError
from geoworkbench.storage.staging_candidate_audit import (
    StagingCandidate,
    list_staging_candidates,
    recheck_staging_candidate,
)


def test_lists_only_immediate_real_staging_directories_without_writing(tmp_path):
    b = tmp_path / ".geolog-restore-b"
    a = tmp_path / ".geolog-restore-a"
    a.mkdir()
    b.mkdir()
    (a / "project.geologpkg").write_bytes(b"keep")
    unrelated = tmp_path / "other"
    unrelated.mkdir()
    before = (a / "project.geologpkg").read_bytes()

    candidates = list_staging_candidates(tmp_path)

    assert [candidate.path for candidate in candidates] == [a, b]
    assert candidates[0].device == a.lstat().st_dev
    assert candidates[0].inode == a.lstat().st_ino
    assert candidates[0].modified_ns == a.lstat().st_mtime_ns
    assert (a / "project.geologpkg").read_bytes() == before
    assert unrelated.is_dir()


def test_rejects_file_and_empty_prefix_candidates(tmp_path):
    (tmp_path / ".geolog-restore-").mkdir()
    (tmp_path / ".geolog-restore-file").write_bytes(b"do not touch")
    (tmp_path / "geolog-restore-other").mkdir()
    assert list_staging_candidates(tmp_path) == ()
    assert (tmp_path / ".geolog-restore-file").read_bytes() == b"do not touch"


def test_ignores_nested_candidates(tmp_path):
    outer = tmp_path / "other"
    outer.mkdir()
    nested = outer / ".geolog-restore-nested"
    nested.mkdir()
    assert list_staging_candidates(tmp_path) == ()
    assert nested.is_dir()


def test_does_not_follow_candidate_symlinks(tmp_path):
    real = tmp_path / "elsewhere"
    real.mkdir()
    marker = real / "keep"
    marker.write_bytes(b"external")
    link = tmp_path / ".geolog-restore-link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Symlinks unavailable on this platform: {exc}")
    assert list_staging_candidates(tmp_path) == ()
    assert link.is_symlink()
    assert marker.read_bytes() == b"external"


def test_rejects_symlinked_parent(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / ".geolog-restore-a").mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Symlinks unavailable on this platform: {exc}")
    with pytest.raises(BackupError, match="real directory"):
        list_staging_candidates(link)
    assert (real / ".geolog-restore-a").is_dir()


def test_rejects_nonexistent_or_regular_file_parent(tmp_path):
    file = tmp_path / "file"
    file.write_bytes(b"unchanged")
    with pytest.raises(BackupError):
        list_staging_candidates(file)
    with pytest.raises(BackupError, match="Cannot inspect"):
        list_staging_candidates(tmp_path / "missing")
    assert file.read_bytes() == b"unchanged"


def test_reports_candidate_metadata_without_claiming_ownership(tmp_path):
    candidate = tmp_path / ".geolog-restore-untrusted"
    candidate.mkdir()
    (candidate / "foreign.txt").write_bytes(b"other process")
    inventory = list_staging_candidates(tmp_path)
    assert len(inventory) == 1
    assert inventory[0].path == candidate
    assert (candidate / "foreign.txt").read_bytes() == b"other process"


def test_parent_replacement_during_scan_fails_closed(tmp_path, monkeypatch):
    candidate = tmp_path / ".geolog-restore-a"
    candidate.mkdir()
    original_scandir = os.scandir

    def replace_root(path):
        root = tmp_path.with_name(tmp_path.name + "-moved")
        tmp_path.rename(root)
        tmp_path.mkdir()
        return original_scandir(root)

    monkeypatch.setattr(
        "geoworkbench.storage.staging_candidate_audit.os.scandir", replace_root
    )
    try:
        with pytest.raises(BackupError, match="changed during inventory"):
            list_staging_candidates(tmp_path)
    finally:
        monkeypatch.undo()


def test_recheck_matches_unchanged_candidate_without_reading_contents(tmp_path, monkeypatch):
    stage = tmp_path / ".geolog-restore-a"
    stage.mkdir()
    (stage / "foreign.bin").write_bytes(b"preserve")
    snapshot = list_staging_candidates(tmp_path)[0]
    assert (snapshot.parent_device, snapshot.parent_inode) == (
        tmp_path.lstat().st_dev, tmp_path.lstat().st_ino
    )

    def forbid_scan(_path):
        raise AssertionError("Recheck must not enumerate directory contents")

    with monkeypatch.context() as patch:
        patch.setattr(os, "scandir", forbid_scan)
        assert recheck_staging_candidate(snapshot)
    assert (stage / "foreign.bin").read_bytes() == b"preserve"


def test_recheck_rejects_changed_directory_mtime(tmp_path):
    stage = tmp_path / ".geolog-restore-a"
    stage.mkdir()
    snapshot = list_staging_candidates(tmp_path)[0]
    new_time = snapshot.modified_ns + 10_000_000_000
    os.utime(stage, ns=(new_time, new_time))
    assert not recheck_staging_candidate(snapshot)
    assert stage.is_dir()


def test_recheck_rejects_replaced_candidate_even_with_same_name(tmp_path):
    stage = tmp_path / ".geolog-restore-a"
    stage.mkdir()
    snapshot = list_staging_candidates(tmp_path)[0]
    original = tmp_path / "original-stage"
    stage.rename(original)
    stage.mkdir()
    assert not recheck_staging_candidate(snapshot)
    assert original.is_dir() and stage.is_dir()


def test_recheck_rejects_replaced_parent_even_if_child_inode_survives(tmp_path):
    parent = tmp_path / "parent"
    parent.mkdir()
    stage = parent / ".geolog-restore-a"
    stage.mkdir()
    snapshot = list_staging_candidates(parent)[0]
    old_parent = tmp_path / "original-parent"
    parent.rename(old_parent)
    parent.mkdir()
    (parent / stage.name).mkdir()
    assert not recheck_staging_candidate(snapshot)
    assert (old_parent / stage.name).is_dir()


def test_recheck_rejects_symlink_replacements(tmp_path):
    parent = tmp_path / "parent"
    parent.mkdir()
    stage = parent / ".geolog-restore-a"
    stage.mkdir()
    snapshot = list_staging_candidates(parent)[0]
    old = tmp_path / "old"
    try:
        stage.rename(old)
        stage.symlink_to(old, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Symlinks unavailable on this platform: {exc}")
    assert not recheck_staging_candidate(snapshot)
    stage.unlink()
    parent.rename(tmp_path / "old-parent")
    parent.symlink_to(tmp_path / "old-parent", target_is_directory=True)
    assert not recheck_staging_candidate(snapshot)
    assert old.is_dir()


def test_recheck_rejects_missing_and_invalid_snapshots(tmp_path):
    stage = tmp_path / ".geolog-restore-a"
    stage.mkdir()
    snapshot = list_staging_candidates(tmp_path)[0]
    stage.rmdir()
    assert not recheck_staging_candidate(snapshot)
    assert not recheck_staging_candidate(
        StagingCandidate(tmp_path / "unrelated", 1, 2, 3, 4, 5)
    )
    assert not recheck_staging_candidate(
        StagingCandidate(tmp_path / ".." / ".geolog-restore-a", 1, 2, 3, 4, 5)
    )
    with pytest.raises(TypeError, match="staging candidate"):
        recheck_staging_candidate(None)  # type: ignore[arg-type]


def test_recheck_rejects_replacement_between_identity_reads(tmp_path, monkeypatch):
    stage = tmp_path / ".geolog-restore-a"
    stage.mkdir()
    snapshot = list_staging_candidates(tmp_path)[0]
    original_lstat = Path.lstat
    seen = 0

    def swap_on_second_read(path):
        nonlocal seen
        if path == stage:
            seen += 1
            if seen == 2:
                stage.rename(tmp_path / "original")
                stage.mkdir()
        return original_lstat(path)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", swap_on_second_read)
        assert not recheck_staging_candidate(snapshot)
    assert (tmp_path / "original").is_dir()
    assert stage.is_dir()
