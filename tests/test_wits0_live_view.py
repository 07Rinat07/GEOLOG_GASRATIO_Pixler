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
    assert "Wits0OperatorDashboard" in widget
    assert "self.dashboard.render_snapshot(snapshot)" in widget
    assert "health = snapshot.health" in widget
    assert "wits0_live.state_with_health" in widget
    assert "wits0_live.error_view_only" in widget
    assert "def diagnostic_plotted_points(" in widget
    assert "self._last_plot_rendered_points = snapshot.rendered_point_count" in widget
    assert "Wits0LiveViewWidget" in capture
    assert "self.live_view.bind_runtime(runtime)" in capture
    assert "self.live_view.bind_runtime(preview_runtime, preview=True)" in capture
    assert "wits0_live.state_preview" in widget
    assert "def workspace_state(" in widget
    assert "selected_mnemonics=self._selected_mnemonics()" in widget
    assert "selected_curve_ids=()" in widget
    assert "state.selected_curve_ids" in widget
    assert "def apply_workspace_state(" in widget
    assert "Wits0LiveFormSettings" in widget
    assert "def _save_current_form(" in widget
    assert "def _reset_current_form(" in widget
    assert "fullScreenRequested = Signal(bool)" in widget
    assert "def resizeEvent(" in widget
    selection_body = widget[
        widget.index("def _curve_selection_changed")
        : widget.index("def _dashboard_range_changed")
    ]
    assert "CUSTOM_LIVE_FORM_ID" not in selection_body
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
        assert widget.state_label.toolTip()
        assert widget.form_combo.isEnabled()
        assert widget.fullscreen_button.isEnabled()
        assert not widget.pause_button.isEnabled()
        assert widget.values_table.columnCount() == 4
        assert widget.dashboard.panels
        assert widget.diagnostic_plotted_points() == 0
    finally:
        widget.close()
        app.processEvents()


@pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None
    or importlib.util.find_spec("pyqtgraph") is None,
    reason="PySide6/pyqtgraph are not installed in the headless test environment",
)
def test_preview_to_persistent_handoff_preserves_unsaved_workspace_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from types import SimpleNamespace

    from PySide6.QtWidgets import QApplication

    from geoworkbench.acquisition.wits0_reliability import Wits0WorkspaceState
    from geoworkbench.services.localization import AppLanguage
    import geoworkbench.ui.wits0_live_view as live_module

    class FakeAcquisitionLiveView:
        def __init__(self, dataset: object, session: object, **_kwargs: object) -> None:
            self.dataset = dataset
            self.session = session

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(live_module, "AcquisitionLiveView", FakeAcquisitionLiveView)
    widget = live_module.Wits0LiveViewWidget(language=AppLanguage.RU)
    expected_state = Wits0WorkspaceState(
        axis_mode="depth",
        auto_follow=False,
        paused=True,
        follow_span=240.0,
        max_points=1500,
        selected_mnemonics=("ROP", "TOTAL_GAS"),
    )
    applied: list[Wits0WorkspaceState] = []
    monkeypatch.setattr(widget, "_populate_axes", lambda: None)
    monkeypatch.setattr(widget, "_populate_curves", lambda: None)
    monkeypatch.setattr(widget, "_apply_live_form_selection", lambda: None)
    monkeypatch.setattr(widget, "refresh", lambda *args, **kwargs: None)
    monkeypatch.setattr(widget, "workspace_state", lambda: expected_state)
    monkeypatch.setattr(widget, "apply_workspace_state", applied.append)

    preview_runtime = SimpleNamespace(
        controller=SimpleNamespace(dataset=object()),
        session=SimpleNamespace(session_id="preview-session"),
    )
    persistent_runtime = SimpleNamespace(
        controller=SimpleNamespace(dataset=object()),
        session=SimpleNamespace(session_id="persistent-session"),
    )

    try:
        widget.bind_runtime(preview_runtime, preview=True)
        assert widget._preview_mode is True

        widget.bind_runtime(persistent_runtime, preview=False)

        assert applied == [expected_state]
        assert widget._preview_mode is False
        assert widget._runtime is persistent_runtime
    finally:
        widget.close()
        app.processEvents()
