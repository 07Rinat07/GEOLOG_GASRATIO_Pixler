"""Temporary replay of the release-test shard prefix ending at Masterlog."""

import os
import sys

from scripts.run_tests import _configure_environment, _run_child, _test_file_shards


def main() -> int:
    shards = _test_file_shards(16)
    target = "tests/test_masterlog_columns_dialog.py"
    last = next(index for index, selectors in enumerate(shards) if target in selectors)
    _configure_environment()
    environment = os.environ.copy()
    for index, selectors in enumerate(shards[: last + 1], start=1):
        print(f"Diagnostic shard {index}/{last + 1}: {len(selectors)} files", flush=True)
        result = _run_child(("-p", "no:cacheprovider"), selectors, environment)
        if result:
            return result
    return 0


if __name__ == "__main__":
    sys.exit(main())
