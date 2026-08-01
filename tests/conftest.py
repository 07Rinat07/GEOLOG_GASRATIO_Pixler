import os
from pathlib import Path
from collections.abc import Callable
import sys

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
os.environ.setdefault("GEOLOG_DISABLE_UNSAVED_PROMPT", "1")

_SESSION_QAPP: object | None = None


@pytest.fixture(scope="session")
def qapp():
    qt_widgets = pytest.importorskip("PySide6.QtWidgets")
    QApplication = qt_widgets.QApplication

    global _SESSION_QAPP
    app = QApplication.instance() or QApplication([])
    _SESSION_QAPP = app
    # The release test runner exits immediately with pytest's verified result.
    # Keep the Python wrapper alive until that exit: destroying QApplication
    # during fixture teardown can abort in the Windows offscreen backend after
    # every test has already passed.
    yield app


@pytest.fixture(autouse=True)
def close_qt_windows_after_test():
    """Dispose Qt windows without invoking application ``closeEvent`` hooks.

    The suite contains windows whose close handlers own optional services.  One
    partially constructed window can therefore raise during ``widget.close()``
    and remain in QApplication, poisoning every later non-GUI test at teardown.
    Test cases that need close semantics call ``close()`` explicitly; the global
    safety net only hides and schedules valid top-level roots for deletion.
    """

    yield
    if "PySide6.QtWidgets" not in sys.modules:
        return
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication, QWidget
    from shiboken6 import isValid

    app = QApplication.instance()
    if app is None:
        return

    widgets = tuple(
        widget
        for widget in tuple(app.topLevelWidgets())
        if isinstance(widget, QWidget) and isValid(widget)
    )
    for widget in widgets:
        try:
            widget.hide()
        except RuntimeError:
            pass

    for widget in widgets:
        if not isValid(widget):
            continue
        try:
            parent = widget.parentWidget()
        except RuntimeError:
            parent = None
        if parent is not None and isValid(parent):
            continue
        try:
            widget.deleteLater()
        except RuntimeError:
            pass

    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
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
