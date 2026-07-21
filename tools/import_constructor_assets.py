#!/usr/bin/env python3
"""Validate the factory constructor assets included in slice23.

The first slice ships already-normalized manifests.  This command is intentionally
conservative: it validates IDs, files and dimensions and prints a compact report.
User-asset mutation is postponed until project persistence and Undo/Redo contracts are
connected to the Constructor UI.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from geoworkbench.form_constructor.asset_registry import ConstructorAssetRegistry  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=PROJECT_ROOT / "resources" / "constructor_assets",
        help="constructor asset root",
    )
    args = parser.parse_args()
    registry = ConstructorAssetRegistry.from_root(args.root)
    errors = registry.validate_files()
    lithology = registry.all(kind="lithology_pattern")
    symbols = registry.all(kind="depth_symbol")
    print(f"Lithology patterns: {len(lithology)}")
    print(f"Depth symbols: {len(symbols)}")
    if errors:
        print("Validation errors:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Constructor asset catalog: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
