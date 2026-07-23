import os
from pathlib import Path
from collections.abc import Callable
import sys

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    try:
        yield app
    finally:
        app.closeAllWindows()
        app.quit()


@pytest.fixture(autouse=True)
def close_qt_windows_after_test():
    """Close leaked test windows before their local Python owners disappear."""

    yield
    if "PySide6.QtWidgets" not in sys.modules:
        return
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    for widget in tuple(app.topLevelWidgets()):
        widget.close()
    app.processEvents()


@pytest.fixture
def symlink_or_skip() -> Callable[..., None]:
    """Create a symlink or skip when Windows has not granted that privilege."""

    def create(
        link: Path,
        target: Path,
        *,
        target_is_directory: bool = False,
    ) -> None:
        try:
            link.symlink_to(target, target_is_directory=target_is_directory)
        except OSError as exc:
            if getattr(exc, "winerror", None) == 1314:
                pytest.skip("Windows symlink privilege is unavailable")
            raise

    return create
