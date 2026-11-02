"""Explicit, checked publication of a prepared backup restore staging tree.

This is an opt-in headless API. ManualBackupService.restore and the restore
dialog still use their existing implementation.
"""
from __future__ import annotations

from pathlib import Path

from geoworkbench.storage.atomic_directory_publish import publish_new_directory
from geoworkbench.storage.manual_backup import (
    BackupError,
    BackupRestorePlan,
    ManualBackupService,
)
from geoworkbench.storage.staged_restore_verify import verify_staged_restore


def publish_verified_staged_restore(
    plan: BackupRestorePlan,
    staging: Path,
    *,
    max_total_bytes: int = 64 * 1024**3,
) -> Path:
    """Revalidate the ZIP, plan and staging, then publish without replacement.

    Recheck the archive and exact plan before verifying each staged file against
    its expected size and digest. Only then attempt an OS-level no-replace rename
    to the *absent* target. The staging tree remains caller-owned on a handled
    failure; this function never tries to remove potentially foreign contents.

    This does not apply saved settings, load a project, change the current
    restore() path, or guarantee crash durability. Another process can modify
    staging between verification and rename; no external-writer lock is held.
    """
    if not isinstance(plan, BackupRestorePlan):
        raise BackupError("Expected a verified restore plan")
    current = ManualBackupService().plan_restore(
        plan.archive,
        plan.destination,
        max_total_bytes=max_total_bytes,
    )
    if current != plan:
        raise BackupError("Restore plan changed before staging publication")

    staged = Path(staging)
    verify_staged_restore(plan, staged)
    try:
        publish_new_directory(staged, plan.destination)
    except (OSError, ValueError) as exc:
        raise BackupError(f"Cannot publish verified restore staging: {exc}") from exc
    return plan.destination
