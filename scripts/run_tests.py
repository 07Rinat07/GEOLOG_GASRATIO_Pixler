#!/usr/bin/env python3
"""Run the project test suite in isolated, headless Qt processes.

Unrelated pytest plugins installed globally are intentionally disabled because
tracing or async plugins from the host environment can own native threads during
Qt teardown. The project-owned pytest-asyncio plugin is loaded explicitly so ETP
coroutine tests remain part of the isolated suite.

On Windows the complete suite is split into small contiguous file shards. Test
files with many Qt scenarios are additionally split into batches of test
functions. Every test is still executed, while each batch receives a fresh
QApplication and fresh native Qt resources. This prevents an unrelated
Windows offscreen-backend access violation after hundreds of GUI objects have
already been created and disposed.
"""

from __future__ import annotations

import ast
from collections.abc import Sequence
import os
from pathlib import Path
import subprocess
import sys


_CHILD_FLAG = "--geolog-single-shard"
_DEFAULT_WINDOWS_SHARDS = 8
_NATIVE_HEAVY_TEST_THRESHOLD = 24
_NATIVE_TEST_BATCH_SIZE = 8


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


def _all_test_files() -> tuple[Path, ...]:
    return tuple(
        sorted(
            (path for path in Path("tests").rglob("test*.py") if path.is_file()),
            key=lambda path: path.as_posix().casefold(),
        )
    )


def _top_level_test_nodes(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    prefix = path.as_posix()
    nodes: list[str] = []
    for item in tree.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if item.name.startswith("test_"):
                nodes.append(f"{prefix}::{item.name}")
            continue
        if not isinstance(item, ast.ClassDef) or not item.name.startswith("Test"):
            continue
        for child in item.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if child.name.startswith("test_"):
                    nodes.append(f"{prefix}::{item.name}::{child.name}")
    return tuple(nodes)


def _heavy_test_batches(
    files: Sequence[Path],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    batches: list[tuple[str, tuple[str, ...]]] = []
    for path in files:
        nodes = _top_level_test_nodes(path)
        if len(nodes) < _NATIVE_HEAVY_TEST_THRESHOLD:
            continue
        for offset in range(0, len(nodes), _NATIVE_TEST_BATCH_SIZE):
            batch = nodes[offset : offset + _NATIVE_TEST_BATCH_SIZE]
            batches.append((path.as_posix(), batch))
    return tuple(batches)


def _test_file_shards(
    shard_count: int,
    files: Sequence[Path] | None = None,
) -> tuple[tuple[str, ...], ...]:
    selected = tuple(files) if files is not None else _all_test_files()
    regular_files = tuple(
        path
        for path in selected
        if len(_top_level_test_nodes(path)) < _NATIVE_HEAVY_TEST_THRESHOLD
    )
    if not regular_files:
        return ()
    shard_count = max(1, min(shard_count, len(regular_files)))
    total_weight = sum(max(1, path.stat().st_size) for path in regular_files)
    target_weight = max(1, total_weight // shard_count)

    shards: list[list[str]] = [[]]
    current_weight = 0
    for path in regular_files:
        remaining_files = len(regular_files) - sum(len(shard) for shard in shards)
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


def _run_child(
    args: Sequence[str],
    selectors: Sequence[str],
    environment: dict[str, str],
) -> int:
    completed = subprocess.run(
        [sys.executable, __file__, _CHILD_FLAG, *args, *selectors],
        env=environment,
        check=False,
    )
    return int(completed.returncode)


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

    files = _all_test_files()
    shards = _test_file_shards(shard_count, files)
    heavy_batches = _heavy_test_batches(files)
    if not shards and not heavy_batches:
        print("No test files found under tests/", file=sys.stderr)
        return 5

    environment = os.environ.copy()
    _configure_environment()
    environment.update(os.environ)
    for index, selectors in enumerate(shards, start=1):
        print(
            f"\n=== pytest isolated shard {index}/{len(shards)}: "
            f"{len(selectors)} files ===",
            flush=True,
        )
        if result := _run_child(args, selectors, environment):
            return result

    for index, (path, selectors) in enumerate(heavy_batches, start=1):
        print(
            f"\n=== pytest native-heavy batch {index}/{len(heavy_batches)}: "
            f"{path}, {len(selectors)} test functions ===",
            flush=True,
        )
        if result := _run_child(args, selectors, environment):
            return result
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
