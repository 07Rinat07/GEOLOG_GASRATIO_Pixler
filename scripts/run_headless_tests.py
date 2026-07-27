#!/usr/bin/env python3
"""Run every test collectable with the dependencies available in this environment.

This is a reduced-environment diagnostic runner, not the Windows release gate. It first
collects the suite in an isolated pytest process. Test modules are ignored only when their
collection failed because a known desktop dependency is genuinely not installed. Any other
collection error remains fatal.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys

OPTIONAL_DESKTOP_MODULES = frozenset({"PySide6", "pyqtgraph", "lasio"})
COLLECTION_HEADER = re.compile(r"ERROR collecting (tests[/\\][^\s]+\.py)")
MISSING_MODULE = re.compile(r"ModuleNotFoundError: No module named '([^']+)'")


def _pytest_command(*args: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "pytest_asyncio.plugin",
        *args,
    ]


def _isolated_environment() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("QT_OPENGL", "software")
    env.setdefault("QT_QUICK_BACKEND", "software")
    env.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
    return env


def _collection_failures(output: str) -> dict[str, str]:
    failures: dict[str, str] = {}
    current: str | None = None
    for line in output.splitlines():
        header = COLLECTION_HEADER.search(line)
        if header is not None:
            current = header.group(1).replace("\\", "/")
            continue
        missing = MISSING_MODULE.search(line)
        if current is not None and missing is not None:
            failures[current] = missing.group(1).split(".", 1)[0]
            current = None
    return failures


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    env = _isolated_environment()
    collection = subprocess.run(
        _pytest_command("--collect-only", "-p", "no:cacheprovider"),
        cwd=root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    failures = _collection_failures(collection.stdout)
    if collection.returncode not in {0, 2}:
        sys.stdout.write(collection.stdout)
        return collection.returncode
    if collection.returncode == 2 and not failures:
        sys.stdout.write(collection.stdout)
        return 2

    unexpected: dict[str, str] = {}
    ignored: list[str] = []
    for test_path, module in sorted(failures.items()):
        unavailable = importlib.util.find_spec(module) is None
        if module not in OPTIONAL_DESKTOP_MODULES or not unavailable:
            unexpected[test_path] = module
        else:
            ignored.append(test_path)

    if unexpected:
        sys.stdout.write(collection.stdout)
        print("Unexpected collection failures:")
        for test_path, module in unexpected.items():
            print(f"  {test_path}: missing {module}")
        return 2

    if ignored:
        print(
            "Reduced environment: ignoring collection-blocked desktop tests for missing "
            + ", ".join(
                sorted(
                    module
                    for module in OPTIONAL_DESKTOP_MODULES
                    if importlib.util.find_spec(module) is None
                )
            )
            + f" ({len(ignored)} files).",
            flush=True,
        )

    command = _pytest_command(
        "-p",
        "no:cacheprovider",
        *(f"--ignore={path}" for path in ignored),
    )
    return subprocess.call(command, cwd=root, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
