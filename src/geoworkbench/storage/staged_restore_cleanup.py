"""Explicit, identity-guarded cleanup for an in-process prepared restore stage.

The caller must capture the receipt for its own stage immediately after
prepare_staged_restore(). Never use this to discover or delete orphaned stages:
a path/prefix alone does not prove ownership. No external-writer lock is held.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import stat

from geoworkbench.storage.manual_backup import BackupError, BackupRestorePlan
from geoworkbench.storage.staged_restore_verify import verify_staged_restore


DirectoryIdentity = tuple[int, int, int]
FileIdentity = tuple[int, int, int, int, int, int]


def _identity(path: Path) -> FileIdentity | None:
    try:
        info = path.lstat()
    except OSError:
        return None
    return (
        info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode),
        info.st_size, info.st_mtime_ns, info.st_ctime_ns,
    )


def _same_directory(path: Path, expected: DirectoryIdentity) -> bool:
    info = _identity(path)
    return info is not None and info[:3] == expected


@dataclass(frozen=True, slots=True)
class OwnedStagingReceipt:
    """In-process snapshot; NOT proof of provenance after a process restart."""

    staging: Path
    root: DirectoryIdentity
    directories: tuple[tuple[Path, DirectoryIdentity], ...]
    files: tuple[tuple[Path, FileIdentity], ...]


def capture_owned_staging_receipt(
    plan: BackupRestorePlan, staging: Path
) -> OwnedStagingReceipt:
    """Record identities for a stage that this caller has just prepared.

    A separate process must not treat this receipt as proof of ownership. The
    stage is fully checked immediately before and after identity collection.
    """
    stage = Path(staging)
    verify_staged_restore(plan, stage)
    root = _identity(stage)
    if root is None or root[2] != stat.S_IFDIR:
        raise BackupError("Cannot identify staging root")

    directories: list[tuple[Path, DirectoryIdentity]] = []
    files: list[tuple[Path, FileIdentity]] = []
    for group in sorted({item.relative_path.split("/")[0] for item in plan.items}):
        folder = stage / group
        identity = _identity(folder)
        if identity is None or identity[2] != stat.S_IFDIR:
            raise BackupError("Cannot identify staging directory")
        directories.append((folder, identity[:3]))

    for item in plan.items:
        path = stage.joinpath(*item.relative_path.split("/"))
        identity = _identity(path)
        if identity is None or identity[2] != stat.S_IFREG:
            raise BackupError("Cannot identify staged file")
        files.append((path, identity))

    verify_staged_restore(plan, stage)
    if not _same_directory(stage, root[:3]):
        raise BackupError("Staging root changed during identity capture")
    if any(not _same_directory(path, identity) for path, identity in directories):
        raise BackupError("Staging directory changed during identity capture")
    if any(_identity(path) != identity for path, identity in files):
        raise BackupError("Staged file changed during identity capture")
    return OwnedStagingReceipt(stage, root[:3], tuple(directories), tuple(files))


def cleanup_owned_staging(receipt: OwnedStagingReceipt) -> bool:
    """Remove only still-identical receipt objects; return True if root removed.

    Never follow changed symlinks or delete unknown entries. If an object is
    replaced or an unexpected file appears, preserve it and its containing
    directory. Partial cleanup is possible; the caller must inspect False.
    There is an unavoidable race between identity checking and unlink/rmdir.
    """
    if not isinstance(receipt, OwnedStagingReceipt):
        raise TypeError("Expected an owned staging receipt")
    stage = receipt.staging
    if not _same_directory(stage, receipt.root):
        return False

    owned_dirs = dict(receipt.directories)
    for path, identity in reversed(receipt.files):
        if (
            not _same_directory(stage, receipt.root)
            or not _same_directory(path.parent, owned_dirs.get(path.parent, (-1, -1, -1)))
        ):
            continue
        if _identity(path) == identity:
            try:
                path.unlink()
            except OSError:
                pass

    for folder, identity in reversed(receipt.directories):
        if not _same_directory(stage, receipt.root):
            return False
        if _same_directory(folder, identity):
            try:
                folder.rmdir()  # Fails if a foreign entry is present.
            except OSError:
                pass

    if not _same_directory(stage, receipt.root):
        return False
    try:
        stage.rmdir()  # Fails if any foreign object or replacement remains.
    except OSError:
        return False
    return True
