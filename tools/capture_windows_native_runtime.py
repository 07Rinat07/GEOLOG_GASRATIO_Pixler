"""Record non-sensitive version evidence for Windows Qt native-crash triage.

Runs in a separate CI Python process, without creating a QApplication or
changing any workstation settings.  The JSON contains no paths, environment
variables, user data, or arbitrary diagnostic bundles.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path


NATIVE_PACKAGES = (
    "PySide6",
    "PySide6-Addons",
    "PySide6-Essentials",
    "shiboken6",
    "pyqtgraph",
    "numpy",
)

# Keep this evidence path-free: raw QPA platform settings can contain paths.
_KNOWN_QT_TEST_PLATFORMS = frozenset({"offscreen", "windows", "minimal"})


def _safe_qt_test_platform(setting: str) -> str:
    return setting if setting in _KNOWN_QT_TEST_PLATFORMS else "other"


def runtime_identity(
    commit: str,
    *,
    package_version: Callable[[str], str] = version,
    qt_version: Callable[[], str] | None = None,
    python_version: str | None = None,
    machine: str | None = None,
    system: str | None = None,
    release: str | None = None,
    qt_test_platform: str | None = None,
) -> dict[str, object]:
    """Gather exact dependency/Qt versions without recording private context."""

    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ValueError("commit must be a 40-character lowercase Git SHA")
    if qt_version is None:
        from PySide6.QtCore import qVersion

        qt_version = qVersion
    # scripts/run_tests.py defaults QT_QPA_PLATFORM to offscreen in its children.
    # The capture process runs first, so this records the test-runner setting,
    # not a claim about the plugin loaded inside a later QApplication.
    platform_setting = (
        os.environ.get("QT_QPA_PLATFORM", "offscreen")
        if qt_test_platform is None
        else qt_test_platform
    )
    return {
        "schema_version": 2,
        "source_commit": commit,
        "python_version": python_version if python_version is not None else platform.python_version(),
        "os": system if system is not None else platform.system(),
        "os_release": release if release is not None else platform.release(),
        "machine": machine if machine is not None else platform.machine(),
        "qt_runtime_version": qt_version(),
        "qt_test_platform": _safe_qt_test_platform(platform_setting),
        "packages": {package: package_version(package) for package in NATIVE_PACKAGES},
    }


def write_snapshot(path: Path, snapshot: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Write pinned Windows native Qt runtime versions.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    snapshot = runtime_identity(args.commit)
    write_snapshot(args.output, snapshot)
    print(f"Captured Qt {snapshot['qt_runtime_version']} for {snapshot['source_commit']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
