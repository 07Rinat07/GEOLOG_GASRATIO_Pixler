"""Fail-closed, no-replace publication primitive for a prepared restore directory.

The caller owns the staging directory and must verify all of its contents before
publication. This helper publishes no data itself and provides no crash-durable
staging protocol. Unsupported filesystems/platforms fail without a rename.
"""
from __future__ import annotations

import ctypes
import errno
import os
from pathlib import Path
import stat
import sys


class AtomicDirectoryPublicationUnsupported(OSError):
    """The OS cannot guarantee an atomic, no-replace directory rename."""


def _linux_rename_noreplace(staged: Path, destination: Path) -> None:
    """Use Linux renameat2(RENAME_NOREPLACE); never fall back to os.rename."""
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise AtomicDirectoryPublicationUnsupported("renameat2 is unavailable")
    renameat2.argtypes = (
        ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint
    )
    renameat2.restype = ctypes.c_int
    descriptor = os.open(staged.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        result = renameat2(
            descriptor, os.fsencode(staged.name),
            descriptor, os.fsencode(destination.name), 1,  # RENAME_NOREPLACE
        )
        error = ctypes.get_errno() if result != 0 else 0
    finally:
        os.close(descriptor)
    if result == 0:
        return
    if error in (errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP):
        raise AtomicDirectoryPublicationUnsupported(
            f"No-replace directory rename is unsupported: {os.strerror(error)}"
        )
    raise OSError(error, os.strerror(error), os.fspath(destination))


def publish_new_directory(staged: Path, destination: Path) -> None:
    """Move a prepared sibling directory to an absent destination atomically.

    Publication never replaces an existing file, directory or symlink, even if
    one appears concurrently. On Windows, os.rename refuses any existing target;
    on Linux, renameat2 with RENAME_NOREPLACE enforces this inside the kernel.
    All other platforms fail closed until an equivalent primitive is verified.

    The caller must ensure staging contents are complete, fsynced and safe, and
    must manage cleanup of any un-published staging directory. This helper does
    not protect against another writer modifying staging or the published result.
    """
    staged, destination = Path(staged), Path(destination)
    if staged == destination or staged.parent != destination.parent:
        raise ValueError("Staging and destination must be distinct siblings")
    if not stat.S_ISDIR(staged.lstat().st_mode):
        raise ValueError("Staging path must be a real directory")
    if sys.platform == "win32":
        os.rename(staged, destination)  # Windows refuses existing targets.
    elif sys.platform.startswith("linux"):
        _linux_rename_noreplace(staged, destination)
    else:
        raise AtomicDirectoryPublicationUnsupported(
            f"Atomic no-replace directory publication is not verified on {sys.platform}"
        )
