"""Temporary diagnostic replay of the observed Windows CI Qt failure."""

from pathlib import Path
import subprocess
import sys

from scripts.run_tests import _test_file_shards


def main() -> int:
    output = Path("build/ci-artifacts/qt-replay")
    output.mkdir(parents=True, exist_ok=True)
    target = "tests/test_masterlog_columns_dialog.py"
    shard = next(items for items in _test_file_shards(16) if target in items)
    scenarios = (
        ("masterlog-only", (target,)),
        ("original-shard", shard),
    )
    failed = False
    for name, selectors in scenarios:
        command = [
            sys.executable, "scripts/run_tests.py", "--geolog-single-shard", "-p", "no:cacheprovider", *selectors,
        ]
        print(f"Running {name}: {len(selectors)} selectors", flush=True)
        result = subprocess.run(command, check=False, timeout=1200)
        print(f"{name}: exit {result.returncode} (0x{result.returncode & 0xffffffff:08X})", flush=True)
        failed |= result.returncode != 0
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
