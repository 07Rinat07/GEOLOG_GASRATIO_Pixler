"""Read-only inventory of possible leftover restore staging directories.

An exact-name prefix is not evidence that a directory belongs to this app.
This module NEVER removes or opens candidate contents, claims ownership, or
authorizes cleanup. A caller must review any candidate separately.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import stat

from geoworkbench.storage.manual_backup import BackupError


_STAGE_PREFIX = ".geolog-restore-"


@dataclass(frozen=True, slots=True)
class StagingCandidate:
    """An observed directory, not an authenticated or deletable staging tree."""

    path: Path
    device: int
    inode: int
    modified_ns: int
    parent_device: int
    parent_inode: int


def list_staging_candidates(parent: Path) -> tuple[StagingCandidate, ...]:
    """List possible staging leftovers without following links or writing data.

    Only inspect immediate children with the staging prefix and a real
    directory type. Reject a symlinked/non-directory parent. No recursive
    reads, automatic deletion, or ownership assumptions. A filesystem writer
    can still change an entry immediately after this read-only snapshot.
    """
    root = Path(parent)
    try:
        before = root.lstat()
        if not stat.S_ISDIR(before.st_mode):
            raise BackupError("Staging parent must be a real directory")
        found: list[StagingCandidate] = []
        with os.scandir(root) as directory:
            for entry in directory:
                if (
                    not entry.name.startswith(_STAGE_PREFIX)
                    or len(entry.name) <= len(_STAGE_PREFIX)
                ):
                    continue
                # Windows DirEntry.stat may return zero st_dev/st_ino from
                # cached directory enumeration data; lstat gets real identity.
                candidate_path = root / entry.name
                try:
                    info = candidate_path.lstat()
                except FileNotFoundError:
                    # Windows can invalidate an enumerated child's old path
                    # when another process replaces the parent mid-scan.
                    # Distinguish a replaced parent from a vanished child.
                    current_parent = root.lstat()
                    if (
                        not stat.S_ISDIR(current_parent.st_mode)
                        or (before.st_dev, before.st_ino)
                        != (current_parent.st_dev, current_parent.st_ino)
                    ):
                        raise BackupError(
                            "Staging parent changed during inventory"
                        ) from None
                    raise
                if not stat.S_ISDIR(info.st_mode):
                    continue
                found.append(
                    StagingCandidate(
                        candidate_path,
                        info.st_dev,
                        info.st_ino,
                        info.st_mtime_ns,
                        before.st_dev,
                        before.st_ino,
                    )
                )
        after = root.lstat()
        if (
            not stat.S_ISDIR(after.st_mode)
            or (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
        ):
            raise BackupError("Staging parent changed during inventory")
    except OSError as exc:
        raise BackupError(f"Cannot inspect staging candidates: {exc}") from exc
    return tuple(sorted(found, key=lambda item: item.path.name))


def recheck_staging_candidate(candidate: StagingCandidate) -> bool:
    """Check whether a prior read-only observation still matches the path.

    Return False if the parent or child was replaced, changed, removed, or
    became a symlink. Never inspect the candidate's contents or mutate it.
    A matching snapshot is NOT ownership proof or permission to delete; a
    concurrent writer can change the filesystem immediately after this call.
    """
    if not isinstance(candidate, StagingCandidate):
        raise TypeError("Expected a staging candidate")
    path = candidate.path
    if (
        not isinstance(path, Path)
        or ".." in path.parts
        or not path.name.startswith(_STAGE_PREFIX)
        or len(path.name) <= len(_STAGE_PREFIX)
    ):
        return False

    expected_parent = (candidate.parent_device, candidate.parent_inode)
    expected_child = (candidate.device, candidate.inode, candidate.modified_ns)
    try:
        parent_before = path.parent.lstat()
        if (
            not stat.S_ISDIR(parent_before.st_mode)
            or (parent_before.st_dev, parent_before.st_ino) != expected_parent
        ):
            return False
        child_before = path.lstat()
        if (
            not stat.S_ISDIR(child_before.st_mode)
            or (child_before.st_dev, child_before.st_ino, child_before.st_mtime_ns)
            != expected_child
        ):
            return False
        child_after = path.lstat()
        parent_after = path.parent.lstat()
    except OSError:
        return False
    return (
        stat.S_ISDIR(child_after.st_mode)
        and (child_after.st_dev, child_after.st_ino, child_after.st_mtime_ns)
        == expected_child
        and stat.S_ISDIR(parent_after.st_mode)
        and (parent_after.st_dev, parent_after.st_ino) == expected_parent
    )
