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
    ancestor_identities: tuple[tuple[Path, int, int], ...] = ()


def _is_real_directory(info: os.stat_result) -> bool:
    """Reject symlinks and Windows junctions/reparse-point directories.

    On Windows, lstat() may report a junction as a directory; the reparse
    attribute is required to avoid treating it as an ordinary directory.
    """
    return stat.S_ISDIR(info.st_mode) and not (
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def _snapshot_ancestors(parent: Path) -> tuple[tuple[Path, int, int], ...]:
    """Observe each directory above parent without following its own link."""
    observed: list[tuple[Path, int, int]] = []
    for ancestor in parent.parents:
        info = ancestor.lstat()
        if not _is_real_directory(info):
            raise BackupError("Staging ancestor must be a real directory")
        observed.append((ancestor, info.st_dev, info.st_ino))
    return tuple(observed)


def list_staging_candidates(parent: Path) -> tuple[StagingCandidate, ...]:
    """List possible staging leftovers without following links or writing data.

    Only inspect immediate children with the staging prefix and a real
    directory type. Reject a symlinked/non-directory parent. No recursive
    reads, automatic deletion, or ownership assumptions. A filesystem writer
    can still change an entry immediately after this read-only snapshot.
    """
    requested = Path(parent)
    if ".." in requested.parts:
        raise BackupError("Staging parent cannot contain '..'")
    root = Path(os.path.abspath(requested))
    try:
        ancestors_before = _snapshot_ancestors(root)
        before = root.lstat()
        if not _is_real_directory(before):
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
                        not _is_real_directory(current_parent)
                        or (before.st_dev, before.st_ino)
                        != (current_parent.st_dev, current_parent.st_ino)
                    ):
                        raise BackupError(
                            "Staging parent changed during inventory"
                        ) from None
                    raise
                if not _is_real_directory(info):
                    continue
                found.append(
                    StagingCandidate(
                        candidate_path,
                        info.st_dev,
                        info.st_ino,
                        info.st_mtime_ns,
                        before.st_dev,
                        before.st_ino,
                        ancestors_before,
                    )
                )
        after = root.lstat()
        if (
            not _is_real_directory(after)
            or (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
            or _snapshot_ancestors(root) != ancestors_before
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

    if not path.is_absolute() or not candidate.ancestor_identities and path.parent.parents:
        return False

    expected_parent = (candidate.parent_device, candidate.parent_inode)
    expected_child = (candidate.device, candidate.inode, candidate.modified_ns)
    try:
        if _snapshot_ancestors(path.parent) != candidate.ancestor_identities:
            return False
        parent_before = path.parent.lstat()
        if (
            not _is_real_directory(parent_before)
            or (parent_before.st_dev, parent_before.st_ino) != expected_parent
        ):
            return False
        child_before = path.lstat()
        if (
            not _is_real_directory(child_before)
            or (child_before.st_dev, child_before.st_ino, child_before.st_mtime_ns)
            != expected_child
        ):
            return False
        child_after = path.lstat()
        parent_after = path.parent.lstat()
        if _snapshot_ancestors(path.parent) != candidate.ancestor_identities:
            return False
    except OSError:
        return False
    return (
        _is_real_directory(child_after)
        and (child_after.st_dev, child_after.st_ino, child_after.st_mtime_ns)
        == expected_child
        and _is_real_directory(parent_after)
        and (parent_after.st_dev, parent_after.st_ino) == expected_parent
    )
