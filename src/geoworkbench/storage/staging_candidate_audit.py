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
                info = candidate_path.lstat()
                if not stat.S_ISDIR(info.st_mode):
                    continue
                found.append(
                    StagingCandidate(
                        candidate_path,
                        info.st_dev,
                        info.st_ino,
                        info.st_mtime_ns,
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
