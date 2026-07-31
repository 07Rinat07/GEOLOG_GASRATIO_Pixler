#!/usr/bin/env python3
"""Run the project test suite in isolated, headless Qt processes.

Unrelated pytest plugins installed globally are intentionally disabled because
tracing or async plugins from the host environment can own native threads during
Qt teardown. The project-owned pytest-asyncio plugin is loaded explicitly so ETP
coroutine tests remain part of the isolated suite.

The complete suite is split into contiguous file shards on Windows. Every test
is still executed, but each shard receives a fresh QApplication and fresh native
Qt resources. This prevents long release runs from being replaced by an
unrelated offscreen-backend abort after hundreds of GUI windows were already
created and disposed.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from collections.abc import Sequence


_CHILD_FLAG = "--geolog-single-shard"
_DEFAULT_WINDOWS_SHARDS = 4


def _exit_immediately(result: int) -> None:
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.TerminateProcess.argtypes = (ctypes.c_void_p, ctypes.c_uint)
        kernel32.TerminateProcess.restype = ctypes.c_int
        process = kernel32.GetCurrentProcess()
        if kernel32.TerminateProcess(process, result) == 0:
            raise ctypes.WinError(ctypes.get_last_error())
        raise RuntimeError("TerminateProcess returned before the process stopped")
    os._exit(result)


def _configure_environment() -> None:
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_OPENGL", "software")
    os.environ.setdefault("QT_QUICK_BACKEND", "software")
    os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
    os.environ.setdefault("PYTHONUNBUFFERED", "1")


def _run_single_pytest(args: Sequence[str]) -> int:
    _configure_environment()
    import pytest

    return int(
        pytest.main(
            [
                "-vv",
                "--tb=short",
                "-p",
                "pytest_asyncio.plugin",
                *args,
            ]
        )
    )


def _explicit_test_selection(args: Sequence[str]) -> bool:
    return any(
        "::" in value
        or value.endswith(".py")
        or value.startswith("tests/")
        or value.startswith("tests\\")
        for value in args
    )


def _test_file_shards(shard_count: int) -> tuple[tuple[str, ...], ...]:
    files = sorted(
        (path for path in Path("tests").rglob("test*.py") if path.is_file()),
        key=lambda path: path.as_posix().casefold(),
    )
    if not files:
        return ()
    shard_count = max(1, min(shard_count, len(files)))
    total_weight = sum(max(1, path.stat().st_size) for path in files)
    target_weight = max(1, total_weight // shard_count)

    shards: list[list[str]] = [[]]
    current_weight = 0
    for path in files:
        remaining_files = len(files) - sum(len(shard) for shard in shards)
        remaining_shards = shard_count - len(shards)
        weight = max(1, path.stat().st_size)
        should_split = (
            len(shards) < shard_count
            and bool(shards[-1])
            and current_weight >= target_weight
            and remaining_files >= remaining_shards
        )
        if should_split:
            shards.append([])
            current_weight = 0
        shards[-1].append(path.as_posix())
        current_weight += weight

    return tuple(tuple(shard) for shard in shards if shard)


def _run_isolated_shards(args: Sequence[str]) -> int:
    requested = os.environ.get("GEOLOG_TEST_SHARDS", str(_DEFAULT_WINDOWS_SHARDS))
    try:
        shard_count = int(requested)
    except ValueError:
        print(f"Invalid GEOLOG_TEST_SHARDS value: {requested!r}", file=sys.stderr)
        return 2
    if shard_count < 1:
        print("GEOLOG_TEST_SHARDS must be at least 1", file=sys.stderr)
        return 2

    shards = _test_file_shards(shard_count)
    if not shards:
        print("No test files found under tests/", file=sys.stderr)
        return 5

    environment = os.environ.copy()
    _configure_environment()
    environment.update(os.environ)
    for index, files in enumerate(shards, start=1):
        print(
            f"\n=== pytest isolated shard {index}/{len(shards)}: "
            f"{len(files)} files ===",
            flush=True,
        )
        completed = subprocess.run(
            [sys.executable, __file__, _CHILD_FLAG, *args, *files],
            env=environment,
            check=False,
        )
        if completed.returncode != 0:
            return int(completed.returncode)
    return 0


def main() -> int:
    arguments = [value for value in sys.argv[1:] if value != _CHILD_FLAG]
    if _CHILD_FLAG in sys.argv:
        return _run_single_pytest(arguments)
    if sys.platform == "win32" and not _explicit_test_selection(arguments):
        return _run_isolated_shards(arguments)
    return _run_single_pytest(arguments)


if __name__ == "__main__":
    result = main()
    # PySide/Qt may crash in the host container while the Python interpreter is
    # tearing down native GUI singletons, after pytest has already completed.
    # Exit directly after flushing the verified pytest result; this does not skip
    # tests and prevents an unrelated native shutdown fault from replacing it.
    sys.stdout.flush()
    sys.stderr.flush()
    _exit_immediately(result)
