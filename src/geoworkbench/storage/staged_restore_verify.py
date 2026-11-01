"""Read-only, fail-closed verification of a separately prepared restore staging tree.

This does not create staging, authorize publication, or change restore().
"""
from __future__ import annotations

import os
from pathlib import Path
import stat

from geoworkbench.storage.manual_backup import (
    BackupError,
    BackupRestorePlan,
    ManualBackupService,
)


def _snapshot(path: Path, *, directory: bool) -> tuple[int, int, int, int, int, int]:
    info = path.lstat()
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise BackupError(f"Unsafe staging object type: {path}")
    return (
        info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode),
        info.st_size, info.st_mtime_ns, info.st_ctime_ns,
    )


def _names(path: Path) -> set[str]:
    return {entry.name for entry in path.iterdir()}


def verify_staged_restore(plan: BackupRestorePlan, staging: Path) -> None:
    """Check exact planned files, SHA-256, sizes and filesystem identities.

    No writes or publication. Revalidation is mandatory immediately before
    any future publish; checks cannot atomically exclude external writers.
    """
    stage = Path(staging)
    service = ManualBackupService()
    try:
        if (
            not stage.name.startswith(".geolog-restore-")
            or stage.name in {".", ".."}
            or stage.parent.resolve(strict=True) != plan.destination.parent.resolve(strict=True)
            or os.path.lexists(plan.destination)
        ):
            raise BackupError("Unsafe staging location or occupied restore destination")
        expected: dict[str, dict[str, tuple[int, str]]] = {}
        total = 0
        for item in plan.items:
            parts = item.relative_path.split("/")
            if (
                len(parts) != 2
                or parts[0] not in {"projects", "settings"}
                or (parts[0] == "settings" and parts[1] != "preferences.ini")
                or (parts[0] == "projects" and not parts[1].casefold().endswith(".geologpkg"))
                or type(item.size) is not int or item.size < 0
                or not isinstance(item.sha256, str) or len(item.sha256) != 64
                or any(char not in "0123456789abcdef" for char in item.sha256)
            ):
                raise BackupError("Invalid staged restore plan")
            service._check_restore_component(parts[1])
            group = expected.setdefault(parts[0], {})
            if parts[1] in group:
                raise BackupError("Duplicate staged restore output")
            group[parts[1]] = (item.size, item.sha256)
            total += item.size
        if not expected or total != plan.total_bytes:
            raise BackupError("Staged restore byte total differs from plan")

        root_identity = _snapshot(stage, directory=True)
        if _names(stage) != set(expected):
            raise BackupError("Unexpected or missing staging subdirectory")
        directory_identities = {
            name: _snapshot(stage / name, directory=True) for name in expected
        }
        for dirname, files in expected.items():
            folder = stage / dirname
            if _names(folder) != set(files):
                raise BackupError("Unexpected or missing staged file")
            for name, (size, digest) in files.items():
                if (
                    _snapshot(stage, directory=True) != root_identity
                    or _snapshot(folder, directory=True) != directory_identities[dirname]
                ):
                    raise BackupError("Staging directory changed during verification")
                path = folder / name
                identity = _snapshot(path, directory=False)
                if identity[3] != size:
                    raise BackupError("Staged file size differs from plan")
                flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
                descriptor = os.open(path, flags)
                with os.fdopen(descriptor, "rb") as stream:
                    opened = os.fstat(stream.fileno())
                    if (
                        not stat.S_ISREG(opened.st_mode)
                        or (opened.st_dev, opened.st_ino) != identity[:2]
                    ):
                        raise BackupError("Staged file replaced before read")
                    actual_digest, actual_size = service._copy(stream, None)
                    after = os.fstat(stream.fileno())
                    if (
                        (after.st_dev, after.st_ino, stat.S_IFMT(after.st_mode),
                         after.st_size, after.st_mtime_ns, after.st_ctime_ns) != identity
                    ):
                        raise BackupError("Staged file changed during read")
                if _snapshot(path, directory=False) != identity:
                    raise BackupError("Staged file replaced after read")
                if actual_size != size or actual_digest != digest:
                    raise BackupError("Staged file checksum or size mismatch")
            if (
                _snapshot(folder, directory=True) != directory_identities[dirname]
                or _names(folder) != set(files)
            ):
                raise BackupError("Staging directory changed during verification")
        if (
            _snapshot(stage, directory=True) != root_identity
            or _names(stage) != set(expected)
            or any(
                _snapshot(stage / name, directory=True) != identity
                for name, identity in directory_identities.items()
            )
        ):
            raise BackupError("Staging root changed during verification")
    except (OSError, ValueError) as exc:
        raise BackupError(f"Cannot verify staged restore: {exc}") from exc
