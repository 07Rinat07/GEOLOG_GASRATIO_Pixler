from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


_COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{7,64}$")
_SCHEMA_VERSION = 1
_DEFAULT_OUTPUT = Path("src/geoworkbench/_build_identity.json")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stamp an immutable source commit into the installable package."
    )
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    commit = str(args.commit).strip().lower()
    if not _COMMIT_PATTERN.fullmatch(commit):
        raise SystemExit("commit must be a 7-64 character hexadecimal SHA")

    target = args.output.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "commit": commit,
    }
    target.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
