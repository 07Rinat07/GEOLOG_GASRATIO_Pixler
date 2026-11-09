"""Temporary Windows Qt/Masterlog native-heap replay (not a release gate)."""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys

from scripts.run_tests import _configure_environment, _run_child, _test_file_shards


# Recovered from the six-file seed in Windows replay 42526104945. Explicit file
# names prevent unrelated test-suite changes from silently changing this prefix.
SEED_FILES = (
    "tests/test_gas_curve_rendering_continuity.py",
    "tests/test_gas_interval_gis_review_ui.py",
    "tests/test_gas_interval_gis_source_review_ui.py",
    "tests/test_gas_mixture_line_patterns.py",
    "tests/test_gas_mixture_output_language.py",
    "tests/test_gas_update_coverage.py",
)
TARGET_FILE = "tests/test_masterlog_columns_dialog.py"

_NATIVE_EXCEPTION = re.compile(
    r"ExceptionCode:\s*(?:0x)?c000(?:0005|0374|0409)\b"
    r"|Windows fatal exception:\s*code\s*0xc000(?:0005|0374|0409)\b"
    r"|second chance !!!",
    re.IGNORECASE,
)
_PYTEST_COMPLETE = re.compile(
    r"=+\s*\d+ passed\b[^\r\n]*\bin\s+\d+(?:\.\d+)?s\s*=+",
    re.IGNORECASE,
)
_PYTEST_FAILURES = re.compile(
    r"=+\s*[^\r\n]*\b\d+\s+failed\b",
    re.IGNORECASE,
)


def debugger_replay_passed(returncode: int, output: str) -> bool:
    """Never mistake a CDB capture/quit for completed successful pytest."""
    return (
        returncode == 0
        and _NATIVE_EXCEPTION.search(output) is None
        and _PYTEST_FAILURES.search(output) is None
        and _PYTEST_COMPLETE.search(output) is not None
    )


def _run_debugged_target(selectors: tuple[str, ...], environment: dict[str, str]) -> int:
    debugger = (
        Path(os.environ["ProgramFiles(x86)"]) / "Windows Kits/10/Debuggers/x64/cdb.exe"
    )
    dump_path = Path(os.environ["RUNNER_TEMP"]) / "geolog-replay-dumps/qt-native.dmp"
    if not debugger.is_file() or " " in str(dump_path):
        raise RuntimeError("Debugger or safe dump path unavailable")
    dump_path.parent.mkdir(parents=True, exist_ok=True)
    capture = (
        ".exr -1; r; u @rip-20 @rip+20; dq @rbx L4; "
        "da poi(poi(@rbx+8)+0x18); kb; lm; "
        f".dump /m {dump_path}; q"
    )
    command = [
        str(debugger), "-o", "-g", "-G",
        "-xd", "0xc0000005", "-xd", "0xc0000374", "-xd", "0xc0000409",
        "-c", capture,
        sys.executable, "scripts/run_tests.py", "--geolog-single-shard",
        "-s", "-p", "no:cacheprovider", *selectors,
    ]
    completed = subprocess.run(
        command,
        env=environment,
        check=False,
        timeout=1200,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    print(completed.stdout, end="", flush=True)
    if not debugger_replay_passed(completed.returncode, completed.stdout):
        print(
            "Diagnostic replay FAILED or INCOMPLETE: CDB exit alone is not "
            "proof that pytest finished successfully.",
            file=sys.stderr,
            flush=True,
        )
        return 1
    return 0


def main() -> int:
    shards = _test_file_shards(16)
    target_shard = next(
        (selectors for selectors in shards if TARGET_FILE in selectors), None
    )
    if target_shard is None or any(
        not Path(name).is_file() for name in (*SEED_FILES, *target_shard)
    ):
        raise RuntimeError("Expected replay selectors are missing")

    mode = os.environ.get("GEOLOG_REPLAY_MODE", "sequence")
    if mode not in {"isolated", "sequence", "both"}:
        raise ValueError("Select isolated, sequence, or both")
    try:
        repetitions = int(os.environ.get("GEOLOG_REPLAY_REPETITIONS", "1"))
    except ValueError as exc:
        raise ValueError("Invalid replay repetitions") from exc
    if not 1 <= repetitions <= 4:
        raise ValueError("Replay repetitions must be between 1 and 4")

    _configure_environment()
    environment = os.environ.copy()
    for repetition in range(1, repetitions + 1):
        if mode in {"isolated", "both"}:
            print(f"Diagnostic {repetition}/{repetitions}: combined shard", flush=True)
            result = _run_child(
                ("-p", "no:cacheprovider"), (*SEED_FILES, *target_shard), environment
            )
            if result:
                return 1
        if mode in {"sequence", "both"}:
            print(f"Diagnostic {repetition}/{repetitions}: seed shard", flush=True)
            result = _run_child(
                ("-p", "no:cacheprovider"), SEED_FILES, environment
            )
            if result:
                return 1
            print(f"Diagnostic {repetition}/{repetitions}: CDB target", flush=True)
            if _run_debugged_target(target_shard, environment):
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
