"""Read-only candidate inventory must not infer ownership or remove data."""
from __future__ import annotations

import os
from pathlib import Path
import stat
from types import SimpleNamespace

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


def _as_windows_reparse_point(info):
    """Simulate lstat() for a Windows junction with directory st_mode."""
    return SimpleNamespace(
        st_mode=info.st_mode,
        st_dev=info.st_dev,
        st_ino=info.st_ino,
        st_mtime_ns=info.st_mtime_ns,
        st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT,
    )


def test_inventory_excludes_windows_reparse_directory_without_reading_it(tmp_path, monkeypatch):
    stage = tmp_path / ".geolog-restore-junction"
    stage.mkdir()
    foreign = stage / "foreign.bin"
    foreign.write_bytes(b"keep")
    original_lstat = Path.lstat

    def reparse_child(path):
        info = original_lstat(path)
        return _as_windows_reparse_point(info) if path == stage else info

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", reparse_child)
        assert list_staging_candidates(tmp_path) == ()
    assert foreign.read_bytes() == b"keep"


def test_inventory_rejects_windows_reparse_parent(tmp_path, monkeypatch):
    stage = tmp_path / ".geolog-restore-a"
    stage.mkdir()
    original_lstat = Path.lstat

    def reparse_parent(path):
        info = original_lstat(path)
        return _as_windows_reparse_point(info) if path == tmp_path else info

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", reparse_parent)
        with pytest.raises(BackupError, match="real directory"):
            list_staging_candidates(tmp_path)
    assert stage.is_dir()


@pytest.mark.parametrize("target", ["parent", "candidate"])
def test_recheck_rejects_windows_reparse_directory(tmp_path, monkeypatch, target):
    stage = tmp_path / ".geolog-restore-a"
    stage.mkdir()
    snapshot = list_staging_candidates(tmp_path)[0]
    original_lstat = Path.lstat
    replaced = tmp_path if target == "parent" else stage

    def reparse_path(path):
        info = original_lstat(path)
        return _as_windows_reparse_point(info) if path == replaced else info

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", reparse_path)
        assert not recheck_staging_candidate(snapshot)
    assert stage.is_dir()



def test_inventory_rejects_candidate_replaced_after_first_observation(tmp_path, monkeypatch):
    stage = tmp_path / ".geolog-restore-a"
    stage.mkdir()
    (stage / "foreign.bin").write_bytes(b"preserve")
    original_lstat = Path.lstat
    reads = 0

    def replace_before_recheck(path):
        nonlocal reads
        if path == stage:
            reads += 1
            if reads == 2:
                stage.rename(tmp_path / "old-stage")
                stage.mkdir()
        return original_lstat(path)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", replace_before_recheck)
        with pytest.raises(BackupError, match="candidate changed during inventory"):
            list_staging_candidates(tmp_path)
    assert reads == 2
    assert (tmp_path / "old-stage" / "foreign.bin").read_bytes() == b"preserve"
    assert stage.is_dir()


def test_inventory_rejects_candidate_mtime_change_after_first_observation(
    tmp_path, monkeypatch
):
    stage = tmp_path / ".geolog-restore-a"
    stage.mkdir()
    original_lstat = Path.lstat
    reads = 0

    def change_mtime_before_recheck(path):
        nonlocal reads
        if path == stage:
            reads += 1
            if reads == 2:
                old = original_lstat(stage)
                updated_ns = old.st_mtime_ns + 10_000_000_000
                os.utime(stage, ns=(updated_ns, updated_ns))
        return original_lstat(path)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", change_mtime_before_recheck)
        with pytest.raises(BackupError, match="candidate changed during inventory"):
            list_staging_candidates(tmp_path)
    assert reads == 2
    assert stage.is_dir()


def test_inventory_rejects_candidate_removed_during_final_recheck(
    tmp_path, monkeypatch
):
    stage = tmp_path / ".geolog-restore-a"
    stage.mkdir()
    original_lstat = Path.lstat
    reads = 0

    def remove_before_recheck(path):
        nonlocal reads
        if path == stage:
            reads += 1
            if reads == 2:
                stage.rmdir()
        return original_lstat(path)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", remove_before_recheck)
        with pytest.raises(BackupError, match="candidate changed during inventory"):
            list_staging_candidates(tmp_path)
    assert reads == 2
    assert not stage.exists()

def test_inventory_rejects_symlinked_grandparent(tmp_path):
    actual = tmp_path / "actual"
    parent = actual / "child"
    parent.mkdir(parents=True)
    stage = parent / ".geolog-restore-a"
    stage.mkdir()
    link = tmp_path / "ancestor-link"
    try:
        link.symlink_to(actual, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Symlinks unavailable on this platform: {exc}")
    with pytest.raises(BackupError, match="ancestor must be a real directory"):
        list_staging_candidates(link / "child")
    assert stage.is_dir()


def test_inventory_rejects_windows_reparse_grandparent(tmp_path, monkeypatch):
    grandparent = tmp_path / "outer"
    parent = grandparent / "child"
    parent.mkdir(parents=True)
    stage = parent / ".geolog-restore-a"
    stage.mkdir()
    original = Path.lstat

    def fake_grandparent(path):
        info = original(path)
        return _as_windows_reparse_point(info) if path == grandparent else info

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", fake_grandparent)
        with pytest.raises(BackupError, match="ancestor must be a real directory"):
            list_staging_candidates(parent)
    assert stage.is_dir()


def test_recheck_rejects_ancestor_turned_into_reparse_point(tmp_path, monkeypatch):
    grandparent = tmp_path / "outer"
    parent = grandparent / "child"
    parent.mkdir(parents=True)
    stage = parent / ".geolog-restore-a"
    stage.mkdir()
    snapshot = list_staging_candidates(parent)[0]
    assert snapshot.ancestor_identities
    original = Path.lstat

    def fake_grandparent(path):
        info = original(path)
        return _as_windows_reparse_point(info) if path == grandparent else info

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", fake_grandparent)
        assert not recheck_staging_candidate(snapshot)
    assert stage.is_dir()


def test_inventory_rejects_ancestor_replacement_during_scan(tmp_path, monkeypatch):
    grandparent = tmp_path / "outer"
    parent = grandparent / "child"
    parent.mkdir(parents=True)
    (parent / ".geolog-restore-a").mkdir()
    original = Path.lstat
    seen = 0

    def changed_identity(path):
        nonlocal seen
        info = original(path)
        if path == grandparent:
            seen += 1
            if seen == 2:
                return SimpleNamespace(
                    st_mode=info.st_mode,
                    st_dev=info.st_dev,
                    st_ino=info.st_ino + 1,
                    st_mtime_ns=info.st_mtime_ns,
                    st_file_attributes=getattr(info, "st_file_attributes", 0),
                )
        return info

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", changed_identity)
        with pytest.raises(BackupError, match="changed during inventory"):
            list_staging_candidates(parent)
    assert (parent / ".geolog-restore-a").is_dir()


def test_recheck_rejects_ancestor_replacement_after_initial_check(tmp_path, monkeypatch):
    grandparent = tmp_path / "outer"
    parent = grandparent / "child"
    parent.mkdir(parents=True)
    stage = parent / ".geolog-restore-a"
    stage.mkdir()
    snapshot = list_staging_candidates(parent)[0]
    original = Path.lstat
    seen = 0

    def changed_second_identity(path):
        nonlocal seen
        info = original(path)
        if path == grandparent:
            seen += 1
            if seen == 2:
                return SimpleNamespace(
                    st_mode=info.st_mode,
                    st_dev=info.st_dev,
                    st_ino=info.st_ino + 1,
                    st_mtime_ns=info.st_mtime_ns,
                    st_file_attributes=getattr(info, "st_file_attributes", 0),
                )
        return info

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", changed_second_identity)
        assert not recheck_staging_candidate(snapshot)
    assert stage.is_dir()


def test_inventory_rejects_parent_dotdot_path(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    (base / ".geolog-restore-a").mkdir()
    with pytest.raises(BackupError, match="cannot contain"):
        list_staging_candidates(base / ".." / "base")
    assert (base / ".geolog-restore-a").is_dir()
