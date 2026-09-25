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
    assert "Wits0LiveDerivedChannelService" in widget
    assert "virtual_curves=self._virtual_curves" in widget
    assert "for curve in self._all_curves()" in widget
    assert "def _set_view_source_selection(" in widget
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
        assert not widget.dexp_correction_check.isChecked()
        assert not widget.normal_mud_density_spin.isEnabled()
        assert not widget.normal_mud_density_unit_combo.isEnabled()
        assert widget._dexp_correction_config() is None

        unit_index = widget.normal_mud_density_unit_combo.findData("ppg")
        assert unit_index >= 0
        widget.normal_mud_density_unit_combo.setCurrentIndex(unit_index)
        widget.normal_mud_density_spin.setValue(9.0)
        widget.dexp_correction_check.setChecked(True)

        config = widget._dexp_correction_config()
        assert config is not None
        assert config.normal_mud_density == 9.0
        assert config.unit == "ppg"
        assert widget.normal_mud_density_spin.isEnabled()
        assert widget.normal_mud_density_unit_combo.isEnabled()
    finally:
        widget.close()
        app.processEvents()


@pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None
    or importlib.util.find_spec("pyqtgraph") is None,
    reason="PySide6/pyqtgraph are not installed in the headless test environment",
)
def test_operator_workspace_exposes_virtual_channels_by_mnemonic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from types import SimpleNamespace

    import numpy as np
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from geoworkbench.domain.models import (
        CurveData,
        CurveMetadata,
        Dataset,
        DatasetKind,
        DepthDomain,
    )
    from geoworkbench.services.acquisition_live_view import AcquisitionLiveAxisMode
    from geoworkbench.services.localization import AppLanguage
    import geoworkbench.ui.wits0_live_view as live_module

    dataset = Dataset(
        dataset_id="operator-derived",
        name="Operator derived",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.asarray([1000.0, 1000.5], dtype=np.float64),
    )
    source = dataset.upsert_curve(
        "C1",
        np.asarray([80.0, 81.0], dtype=np.float64),
        unit="% abs",
        description="Methane",
        provenance="wits0:0801",
    )
    virtual_id = "wits-derived:haworth.wetness:1.0.0"
    virtual_curve = CurveData(
        CurveMetadata(
            curve_id=virtual_id,
            original_mnemonic="WH",
            canonical_mnemonic="WH",
            unit="%",
            description="Haworth Wetness",
            source_dataset_id=dataset.dataset_id,
            provenance="formula:haworth.wetness:1.0.0;source-records=08",
        ),
        np.asarray([20.0, 21.0], dtype=np.float64),
    )

    class FakeDerivedService:
        def virtual_curves(self, _dataset: Dataset) -> dict[str, CurveData]:
            return {virtual_id: virtual_curve}

    class FakeAcquisitionLiveView:
        def __init__(self, bound_dataset: Dataset, session: object, **_kwargs: object) -> None:
            self.dataset = bound_dataset
            self.session = session
            self.axis_mode = AcquisitionLiveAxisMode.AUTO
            self.auto_follow = True
            self.paused = False
            self.history_window = None
            self.selected: tuple[str, ...] = ()
            self.config = SimpleNamespace(
                time_window_seconds=600.0,
                depth_window=100.0,
            )

        def snapshot(
            self,
            *,
            curve_ids: tuple[str, ...] = (),
            max_points_per_curve: int = 100,
            **_kwargs: object,
        ) -> object:
            del curve_ids, max_points_per_curve
            return SimpleNamespace(axis_mode=self.axis_mode)

        def available_axis_modes(self) -> tuple[AcquisitionLiveAxisMode, ...]:
            return (AcquisitionLiveAxisMode.AUTO,)

        def set_selected_curves(self, curve_ids: tuple[str, ...]) -> None:
            self.selected = tuple(curve_ids)

        def set_axis_mode(self, mode: AcquisitionLiveAxisMode) -> None:
            self.axis_mode = mode

        def set_auto_follow(self, enabled: bool) -> None:
            self.auto_follow = bool(enabled)

        def set_follow_span(self, _span: float) -> None:
            return

    monkeypatch.setattr(live_module, "Wits0LiveDerivedChannelService", FakeDerivedService)
    monkeypatch.setattr(live_module, "AcquisitionLiveView", FakeAcquisitionLiveView)

    app = QApplication.instance() or QApplication([])
    widget = live_module.Wits0LiveViewWidget(language=AppLanguage.RU)
    monkeypatch.setattr(widget, "refresh", lambda *args, **kwargs: None)
    runtime = SimpleNamespace(
        controller=SimpleNamespace(dataset=dataset),
        session=SimpleNamespace(session_id="session-derived"),
    )

    try:
        widget.bind_runtime(runtime)
        item_by_id = {
            widget.curve_list.item(row).data(Qt.ItemDataRole.UserRole):
            widget.curve_list.item(row)
            for row in range(widget.curve_list.count())
        }
        assert source.metadata.curve_id in item_by_id
        assert virtual_id in item_by_id
        item_by_id[source.metadata.curve_id].setCheckState(Qt.CheckState.Unchecked)
        item_by_id[virtual_id].setCheckState(Qt.CheckState.Checked)

        assert widget._selected_mnemonics() == ("WH",)
        assert widget._curve_ids_for_mnemonics(("WH",)) == (virtual_id,)
        widget._set_view_source_selection(widget._selected_curve_ids())
        assert widget._view is not None
        assert widget._view.selected == ()
        assert widget.workspace_state().selected_mnemonics == ("WH",)
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
