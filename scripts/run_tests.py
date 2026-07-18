#!/usr/bin/env python3
"""Run the project test suite in an isolated, headless Qt environment.

Third-party pytest plugins installed globally are intentionally disabled. In
particular, tracing/async plugins from the host environment can own native
threads during Qt teardown and make a successful PySide6 suite exit with a
segmentation fault. The project tests do not require those plugins.
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_OPENGL", "software")
    os.environ.setdefault("QT_QUICK_BACKEND", "software")
    os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

    import pytest

    return int(pytest.main(["-q", *sys.argv[1:]]))


if __name__ == "__main__":
    raise SystemExit(main())
