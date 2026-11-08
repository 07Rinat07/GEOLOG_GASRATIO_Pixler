"""Temporary replay of the release-test shard prefix ending at Masterlog."""

import os
from pathlib import Path
import subprocess
import sys

from scripts.run_tests import _configure_environment, _run_child, _test_file_shards


def main() -> int:
    shards = _test_file_shards(16)
    target = "tests/test_masterlog_columns_dialog.py"
    last = next(index for index, selectors in enumerate(shards) if target in selectors)
    _configure_environment()
    environment = os.environ.copy()
    mode = os.environ.get("GEOLOG_REPLAY_MODE")
    if mode == "isolated":
        prefix = ((*shards[4][29:32], *shards[4][33:35], shards[4][42], *shards[last]),)
    elif mode == "sequence":
        prefix = ((*shards[4][29:32], *shards[4][33:35], shards[4][42]), shards[last])
    else:
        raise ValueError("Select one diagnostic prefix")
    selected = prefix
    for index, selectors in enumerate(selected, start=1):
        print(f"Diagnostic shard {index}/{len(selected)}: {len(selectors)} files", flush=True)
        if mode == "sequence" and index == len(selected):
            debugger = Path(os.environ["ProgramFiles(x86)"]) / "Windows Kits/10/Debuggers/x64/cdb.exe"
            dump_path = Path(os.environ["RUNNER_TEMP"]) / "geolog-replay-dumps/qt-native.dmp"
            if not debugger.is_file() or " " in str(dump_path):
                raise RuntimeError("Debugger or safe dump path unavailable")
            capture = f".exr -1; r; kb; lm; .dump /m {dump_path}; q"
            commands = (
                f'sxe -c "{capture}" 0xc0000005; sxe -c "{capture}" 0xc0000374; '
                f'sxe -c "{capture}" 0xc0000409; g'
            )
            command = [
                str(debugger), "-o", "-G", "-c", commands,
                sys.executable, "scripts/run_tests.py", "--geolog-single-shard", "-p", "no:cacheprovider", *selectors,
            ]
            result = subprocess.run(command, env=environment, check=False, timeout=1200).returncode
        else:
            result = _run_child(("-p", "no:cacheprovider"), selectors, environment)
        if result:
            return result
    return 0


if __name__ == "__main__":
    sys.exit(main())
