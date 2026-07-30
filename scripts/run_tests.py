#!/usr/bin/env python3
"""Run the project test suite in an isolated, headless Qt environment.

Unrelated pytest plugins installed globally are intentionally disabled because
tracing or async plugins from the host environment can own native threads during
Qt teardown. The project-owned pytest-asyncio plugin is loaded explicitly so ETP
coroutine tests remain part of the isolated suite.
"""

from __future__ import annotations

import os
import sys


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


def main() -> int:
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_OPENGL", "software")
    os.environ.setdefault("QT_QUICK_BACKEND", "software")
    os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

    import pytest

    return int(
        pytest.main(
            [
                "-vv",
                "--tb=short",
                "-p",
                "pytest_asyncio.plugin",
                *sys.argv[1:],
            ]
        )
    )


if __name__ == "__main__":
    result = main()
    # PySide/Qt may crash in the host container while the Python interpreter is
    # tearing down native GUI singletons, after pytest has already completed.
    # Exit directly after flushing the verified pytest result; this does not skip
    # tests and prevents an unrelated native shutdown fault from replacing it.
    sys.stdout.flush()
    sys.stderr.flush()
    _exit_immediately(result)
