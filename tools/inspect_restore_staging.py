"""Read-only CLI inspection of possible leftover restore staging directories.

An observed .geolog-restore-* directory is NOT proof of application ownership.
Never list the directory's contents, remove files or authorize cleanup here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from geoworkbench.storage.manual_backup import BackupError
from geoworkbench.storage.staging_candidate_audit import (
    list_staging_candidates,
    recheck_staging_candidate,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect possible restore staging directories (read-only; never delete)."
    )
    parser.add_argument(
        "parent",
        type=Path,
        help="Existing parent directory containing possible .geolog-restore-* entries",
    )
    args = parser.parse_args(argv)

    try:
        candidates = list_staging_candidates(args.parent)
        # Fail closed before displaying any snapshot if an entry changed
        # between inventory and the final independent recheck.
        if not all(recheck_staging_candidate(item) for item in candidates):
            raise BackupError("Staging candidate changed before report")
    except BackupError as exc:
        print(f"Staging inspection failed: {exc}", file=sys.stderr)
        return 2

    report = {
        "read_only": True,
        "ownership_verified": False,
        "deletion_authorized": False,
        "candidates": [
            {
                "path": str(item.path),
                "device": item.device,
                "inode": item.inode,
                "modified_ns": item.modified_ns,
                "parent_device": item.parent_device,
                "parent_inode": item.parent_inode,
            }
            for item in candidates
        ],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
