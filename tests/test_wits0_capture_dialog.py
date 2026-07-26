from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "geoworkbench" / "ui" / "wits0_capture_dialog.py"
MAIN_WINDOW = ROOT / "src" / "geoworkbench" / "ui" / "main_window.py"


def test_wits0_capture_ui_keeps_socket_work_outside_qt_thread() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert "Wits0CaptureEngine" in source
    assert "QTimer" in source
    assert ".drain_events(" in source
    assert "socket.socket" not in source
    assert ".recv(" not in source
    assert ".accept(" not in source


def test_main_window_exposes_modeless_wits0_capture_action() -> None:
    source = MAIN_WINDOW.read_text(encoding="utf-8")

    assert 'self._localized_action("shell.capture_wits0")' in source
    assert "def open_wits0_capture" in source
    assert "dialog.show()" in source
    assert "dialog.exec()" not in source[source.index("def open_wits0_capture") : source.index("def open_witsml_inventory")]


@pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None,
    reason="PySide6 is not installed in the headless test environment",
)
def test_wits0_capture_dialog_constructs_offscreen(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from geoworkbench.services.localization import AppLanguage
    from geoworkbench.ui.wits0_capture_dialog import Wits0CaptureDialog

    app = QApplication.instance() or QApplication([])
    dialog = Wits0CaptureDialog(language=AppLanguage.RU)
    try:
        assert dialog.windowTitle()
        assert dialog.start_button.isEnabled()
        assert not dialog.stop_button.isEnabled()
    finally:
        dialog.close()
        app.processEvents()
