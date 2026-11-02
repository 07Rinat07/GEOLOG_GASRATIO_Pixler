"""Prepare a verified restore staging tree without publishing it.

The returned private sibling directory is owned by the caller. This helper
never calls restore() or publishes to the destination. A crash can leave
staging behind; successful staging is not a crash-durability guarantee.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat
import tempfile
from zipfile import BadZipFile, ZIP_STORED, ZipFile

from geoworkbench.storage.manual_backup import (
    BackupError,
    BackupRestorePlan,
    ManualBackupService,
)
from geoworkbench.storage.staged_restore_verify import verify_staged_restore


def prepare_staged_restore(
    plan: BackupRestorePlan, *, max_total_bytes: int = 64 * 1024**3
) -> Path:
    """Stream a freshly rechecked ZIP into an exclusive hidden sibling folder.

    Verify bytes, archive identity and the finished staging tree. On handled
    errors, remove only still-identical objects created by this invocation.
    No destination is created, overwritten or published. External writers are
    not locked out; cleanup and identity checks have unavoidable TOCTOU gaps.
    """
    if not isinstance(plan, BackupRestorePlan):
        raise BackupError("Expected a verified restore plan")
    service = ManualBackupService()
    current = service.plan_restore(
        plan.archive, plan.destination, max_total_bytes=max_total_bytes
    )
    if current != plan:
        raise BackupError("Restore plan changed since preflight")

    stage: Path | None = None
    root_identity: tuple[int, int, int] | None = None
    directories: dict[Path, tuple[int, int, int]] = {}
    files: list[tuple[Path, tuple[int, int, int]]] = []
    completed = False
    try:
        stage = Path(tempfile.mkdtemp(
            prefix=".geolog-restore-", dir=plan.destination.parent
        ))
        root_identity = service._restore_path_identity(stage)
        if root_identity is None:
            raise BackupError("Staging root disappeared after creation")

        with plan.archive.open("rb") as stream:
            before = os.fstat(stream.fileno())
            with ZipFile(stream, "r") as archive:
                expected = {item.archive_path for item in plan.items}
                expected.add("manifest.json")
                names = [info.filename for info in archive.infolist()]
                if len(names) != len(expected) or set(names) != expected:
                    raise BackupError("Backup inventory changed before staging")

                written = 0
                for item in plan.items:
                    group, name = item.relative_path.split("/")
                    folder = stage / group
                    if folder not in directories:
                        if not service._same_restore_path(stage, root_identity):
                            raise BackupError("Staging root replaced")
                        folder.mkdir()
                        identity = service._restore_path_identity(folder)
                        if identity is None:
                            raise BackupError("Staging folder disappeared")
                        directories[folder] = identity
                    if (
                        not service._same_restore_path(stage, root_identity)
                        or not service._same_restore_path(folder, directories[folder])
                    ):
                        raise BackupError("Staging directory changed during write")

                    info = archive.getinfo(item.archive_path)
                    if (
                        info.compress_type != ZIP_STORED
                        or info.flag_bits & 1
                        or info.is_dir()
                        or stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK
                        or info.file_size != item.size
                        or item.size > max_total_bytes - written
                    ):
                        raise BackupError("Unsafe or changed backup member")

                    output_path = folder / name
                    with archive.open(info, "r") as original:
                        with output_path.open("xb") as output:
                            info_written = os.fstat(output.fileno())
                            identity = (
                                info_written.st_dev,
                                info_written.st_ino,
                                stat.S_IFMT(info_written.st_mode),
                            )
                            files.append((output_path, identity))
                            digest, size = service._copy(original, output)
                            output.flush()
                            os.fsync(output.fileno())
                    if size != item.size or digest != item.sha256:
                        raise BackupError("Staged member checksum mismatch")
                    written += size
                if written != plan.total_bytes:
                    raise BackupError("Staged byte total differs from preflight")
            after = os.fstat(stream.fileno())
        if (
            service._identity(before) != service._identity(after)
            or service._identity(before) != service._identity(plan.archive.stat())
        ):
            raise BackupError("Backup changed during staging")
        if (
            not service._same_restore_path(stage, root_identity)
            or any(
                not service._same_restore_path(path, identity)
                for path, identity in (*directories.items(), *files)
            )
        ):
            raise BackupError("Staging path changed during write")
        verify_staged_restore(plan, stage)
        completed = True
        return stage
    except (OSError, BadZipFile, ValueError, KeyError) as exc:
        raise BackupError(f"Cannot prepare restore staging: {exc}") from exc
    finally:
        if (
            stage is not None
            and not completed
            and service._same_restore_path(stage, root_identity)
        ):
            for path, identity in reversed(files):
                try:
                    if service._same_restore_path(path, identity):
                        path.unlink()
                except OSError:
                    pass
            for path, identity in reversed(list(directories.items())):
                try:
                    if service._same_restore_path(path, identity):
                        path.rmdir()
                except OSError:
                    pass
            try:
                if service._same_restore_path(stage, root_identity):
                    stage.rmdir()
            except OSError:
                pass
