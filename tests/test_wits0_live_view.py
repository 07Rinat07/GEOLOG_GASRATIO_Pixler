from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SERVICE_SOURCE = ROOT / "src" / "geoworkbench" / "services" / "acquisition_live_view.py"
WIDGET_SOURCE = ROOT / "src" / "geoworkbench" / "ui" / "wits0_live_view.py"
CAPTURE_SOURCE = ROOT / "src" / "geoworkbench" / "ui" / "wits0_capture_dialog.py"


def test_live_view_uses_read_only_projection_and_shared_downsampling() -> None:
    service = SERVICE_SOURCE.read_text(encoding="utf-8")
    widget = WIDGET_SOURCE.read_text(encoding="utf-8")
    capture = CAPTURE_SOURCE.read_text(encoding="utf-8")

    assert "select_visible_samples" in service
    assert "class AcquisitionLiveView" in service
    assert "def pause(" in service
    assert "def resume(" in service
    assert "def set_history_window(" in service
    assert "class Wits0LiveViewWidget" in widget
    assert "AcquisitionLiveMarkerKind" in widget
    assert "Wits0LiveViewWidget" in capture
    assert "self.live_view.bind_runtime(runtime)" in capture
    assert "def workspace_state(" in widget
    assert "def apply_workspace_state(" in widget
    pause_body = widget[
        widget.index("def _pause_changed") : widget.index("def _follow_span_changed")
    ]
    assert ".stop(" not in pause_body
    assert ".close(" not in pause_body


@pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None
    or importlib.util.find_spec("pyqtgraph") is None,
    reason="PySide6/pyqtgraph are not installed in the headless test environment",
)
def test_wits0_live_view_constructs_offscreen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from geoworkbench.services.localization import AppLanguage
    from geoworkbench.ui.wits0_live_view import Wits0LiveViewWidget

    app = QApplication.instance() or QApplication([])
    widget = Wits0LiveViewWidget(language=AppLanguage.RU)
    try:
        assert widget.state_label.text()
        assert not widget.pause_button.isEnabled()
        assert widget.values_table.columnCount() == 4
    finally:
        widget.close()
        app.processEvents()
