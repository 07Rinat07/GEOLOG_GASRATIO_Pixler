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
    assert "def _apply_navigation_layout(" in widget
    assert "_COMPACT_NAVIGATION_BREAKPOINT = 820" in widget
    assert 'panel.setObjectName("wits0LiveSidebar")' in widget
    assert 'panel.setObjectName("wits0LivePlotPanel")' in widget
    assert 'self.panel_list.setObjectName("wits0PanelLayoutList")' in widget
    assert 'Qt.ScrollBarPolicy.ScrollBarAlwaysOff' in widget
    assert "def _panel_layout_from_controls(" in widget
    assert "def _move_selected_panel(" in widget
    assert "self.dashboard.set_panel_layout(panel_order, hidden_panel_ids)" in widget
    assert "self.dashboard.set_panel_x_range(" in widget
    assert "self.dashboard.reset_panel_x_range(" in widget
    assert "panel_x_ranges=self.dashboard.panel_x_ranges()" in widget
    assert "Wits0AlarmSettingsEditor" in widget
    assert "alarm_rules=self.alarm_editor.rules()" in widget
    assert "self.alarm_editor.set_rules(saved.alarm_rules)" in widget
    assert "self.alarm_editor.clear_rules()" in widget
    assert "Wits0LiveAlarmController" in widget
    assert "self._alarm_controller.evaluate(" in widget
    assert "view.session," in widget
    assert "snapshot.current_values," in widget
    assert "virtual_curves=self._virtual_curves" in widget
    assert "dataset_row_count=len(view.dataset.depth)" in widget
    assert "self.dashboard.render_alarm_statuses(alarm_statuses)" in widget
    assert "def _acknowledge_active_alarms(" in widget
    assert "self.dashboard.set_panel_x_ranges(saved.panel_x_ranges)" in widget
    assert "self.dashboard.scaleTargetsChanged.connect(" in widget
    assert "panel = QScrollArea(self)" in widget
    assert "Qt.ScrollBarPolicy.ScrollBarAsNeeded" in widget
    assert '"panel_up": "Выше"' in widget
    assert '"panel_down": "Ниже"' in widget
    assert '"panel_up": "Жоғары"' in widget
    assert '"panel_down": "Төмен"' in widget
    assert '"panel_up": "Move up"' in widget
    assert '"panel_down": "Move down"' in widget
    assert '"panel_x_auto": "Авто X"' in widget
    assert '"panel_x_apply": "Применить X-диапазон"' in widget
    assert '"panel_x_auto": "Авто X"' in widget
    assert '"panel_x_apply": "X ауқымын қолдану"' in widget
    assert '"panel_x_auto": "Auto X"' in widget
    assert '"panel_x_apply": "Apply X range"' in widget
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
    navigation_body = widget[
        widget.index("def _is_compact_navigation")
        : widget.index("def _health_tooltip")
    ]
    assert "bind_runtime(" not in navigation_body
    assert ".stop(" not in navigation_body
    assert ".close(" not in navigation_body


@pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None
    or importlib.util.find_spec("pyqtgraph") is None,
    reason="PySide6/pyqtgraph are not installed in the headless test environment",
)
def test_wits0_live_view_constructs_offscreen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QHeaderView, QWidget

    from geoworkbench.services.localization import AppLanguage
    from geoworkbench.ui.wits0_live_view import Wits0LiveViewWidget

    app = QApplication.instance() or QApplication([])
    widget = Wits0LiveViewWidget(language=AppLanguage.RU)
    try:
        widget.resize(600, 420)
        widget.show()
        app.processEvents()

        toolbar = widget.findChild(QWidget, "wits0LiveToolbar")
        assert toolbar is not None
        assert toolbar.width() <= widget.width()
        toolbar_right = toolbar.contentsRect().right()
        for control in (
            widget.form_combo,
            widget.save_form_button,
            widget.reset_form_button,
            widget.axis_combo,
            widget.auto_follow_check,
            widget.pause_button,
            widget.window_spin,
            widget.max_points_spin,
            widget.refresh_button,
            widget.sidebar_button,
            widget.fullscreen_button,
        ):
            assert control.isVisible()
            assert control.geometry().right() <= toolbar_right

        assert not widget.left_panel.isVisible()
        assert widget.plot_panel.isVisible()
        assert widget.sidebar_button.text() == "Показать параметры"

        widget.sidebar_button.click()
        app.processEvents()
        assert widget.left_panel.isVisible()
        assert not widget.plot_panel.isVisible()
        assert widget.sidebar_button.text() == "Назад к монитору"
        assert widget.curve_list.isVisible()
        assert widget.panel_list.isVisible()
        assert widget.panel_list.count() == len(widget.dashboard.panels)
        assert widget.panel_up_button.text() == "Выше"
        assert widget.panel_down_button.text() == "Ниже"
        assert (
            widget.left_panel.horizontalScrollBarPolicy()
            is Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        assert (
            widget.left_panel.verticalScrollBarPolicy()
            is Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        assert widget.panel_scale_combo is not None
        assert widget.panel_x_auto_check.text() == "Авто X"
        assert widget.panel_x_apply_button.text() == "Применить X-диапазон"
        assert widget.alarm_editor.isVisible()
        assert widget.alarm_editor.objectName() == "wits0AlarmSettingsEditor"
        assert widget.alarm_summary_label.isVisible()
        assert widget.acknowledge_alarms_button.isVisible()
        assert not widget.acknowledge_alarms_button.isEnabled()
        assert widget.values_table.isVisible()
        for section in range(widget.values_table.columnCount()):
            assert (
                widget.values_table.horizontalHeader().sectionResizeMode(section)
                == QHeaderView.ResizeMode.Stretch
            )

        widget.sidebar_button.click()
        app.processEvents()
        assert not widget.left_panel.isVisible()
        assert widget.plot_panel.isVisible()

        widget.resize(1200, 700)
        app.processEvents()
        assert widget.left_panel.isVisible()
        assert widget.plot_panel.isVisible()
        assert widget.sidebar_button.text() == "Скрыть параметры"

        widget.sidebar_button.click()
        app.processEvents()
        assert not widget.left_panel.isVisible()
        assert widget.plot_panel.isVisible()

        widget.resize(600, 420)
        app.processEvents()
        assert not widget.left_panel.isVisible()
        assert widget.plot_panel.isVisible()

        widget.resize(1200, 700)
        app.processEvents()
        assert not widget.left_panel.isVisible()
        assert widget.plot_panel.isVisible()

        widget.set_fullscreen_state(True)
        app.processEvents()
        assert not widget.left_panel.isVisible()
        assert widget.plot_panel.isVisible()
        assert widget.fullscreen_button.text() == "Выйти из полного экрана"

        widget.sidebar_button.click()
        app.processEvents()
        assert widget.left_panel.isVisible()
        assert not widget.plot_panel.isVisible()
        assert widget.sidebar_button.text() == "Назад к монитору"

        widget.set_fullscreen_state(False)
        app.processEvents()
        assert not widget.left_panel.isVisible()
        assert widget.plot_panel.isVisible()
        assert widget.fullscreen_button.text() == "На весь экран"

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
def test_wits0_panel_editor_reorders_and_hides_dashboard_panels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from geoworkbench.services.localization import AppLanguage
    from geoworkbench.ui.wits0_live_view import Wits0LiveViewWidget

    app = QApplication.instance() or QApplication([])
    widget = Wits0LiveViewWidget(language=AppLanguage.RU)
    monkeypatch.setattr(widget, "refresh", lambda *args, **kwargs: None)
    widget._view = object()  # type: ignore[assignment] - UI boundary only
    widget.panel_list.setEnabled(True)
    widget._refresh_panel_order_buttons()

    try:
        initial_order, initial_hidden = widget.dashboard.panel_layout()
        listed = tuple(
            str(
                widget.panel_list.item(row).data(
                    Qt.ItemDataRole.UserRole
                )
            )
            for row in range(widget.panel_list.count())
        )

        assert listed == initial_order
        assert initial_hidden == ()
        assert (
            widget.panel_list.horizontalScrollBarPolicy()
            is Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        widget.panel_list.setCurrentRow(0)
        widget._refresh_panel_order_buttons()
        assert not widget.panel_up_button.isEnabled()
        assert widget.panel_down_button.isEnabled()

        widget.panel_list.setCurrentRow(1)
        widget._refresh_panel_order_buttons()
        assert widget.panel_up_button.isEnabled()
        widget.panel_up_button.click()
        app.processEvents()

        moved_order, hidden = widget.dashboard.panel_layout()
        assert moved_order[0] == initial_order[1]
        assert moved_order[1] == initial_order[0]
        assert hidden == ()

        first_item = widget.panel_list.item(0)
        first_id = str(first_item.data(Qt.ItemDataRole.UserRole))
        first_item.setCheckState(Qt.CheckState.Unchecked)
        app.processEvents()

        final_order, final_hidden = widget.dashboard.panel_layout()
        assert final_order == moved_order
        assert final_hidden == (first_id,)
    finally:
        widget.close()
        app.processEvents()


@pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None
    or importlib.util.find_spec("pyqtgraph") is None,
    reason="PySide6/pyqtgraph are not installed in the headless test environment",
)
def test_wits0_scale_editor_applies_manual_and_auto_per_unit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from geoworkbench.services.localization import AppLanguage
    from geoworkbench.ui.wits0_operator_dashboard import Wits0PanelScaleTarget
    from geoworkbench.ui.wits0_live_view import Wits0LiveViewWidget

    app = QApplication.instance() or QApplication([])
    widget = Wits0LiveViewWidget(language=AppLanguage.RU)
    widget._view = object()  # type: ignore[assignment] - UI boundary only

    targets = (
        Wits0PanelScaleTarget(
            scale_key="gas_components|ppm",
            panel_id="gas_components",
            title="Газовые компоненты [ppm]",
            unit="ppm",
            auto_range=True,
            minimum=0.0,
            maximum=100.0,
        ),
        Wits0PanelScaleTarget(
            scale_key="gas_components|%",
            panel_id="gas_components",
            title="Газовые компоненты [%]",
            unit="%",
            auto_range=False,
            minimum=0.0,
            maximum=2.0,
        ),
    )
    applied: list[tuple[str, float, float]] = []
    reset: list[str] = []
    monkeypatch.setattr(
        widget.dashboard,
        "panel_scale_targets",
        lambda panel_id: targets if panel_id == "gas_components" else (),
    )
    monkeypatch.setattr(
        widget.dashboard,
        "set_panel_x_range",
        lambda key, low, high: applied.append((key, low, high)),
    )
    monkeypatch.setattr(
        widget.dashboard,
        "reset_panel_x_range",
        reset.append,
    )

    try:
        gas_row = next(
            row
            for row in range(widget.panel_list.count())
            if widget.panel_list.item(row).data(Qt.ItemDataRole.UserRole)
            == "gas_components"
        )
        widget.panel_list.setEnabled(True)
        widget.panel_list.setCurrentRow(gas_row)
        widget._sync_panel_scale_controls()

        assert widget.panel_scale_combo.count() == 2
        assert widget.panel_scale_combo.currentData() == "gas_components|ppm"
        assert widget.panel_x_auto_check.isChecked()

        widget.panel_x_auto_check.setChecked(False)
        assert widget.panel_x_min_spin.value() == pytest.approx(0.0)
        assert widget.panel_x_max_spin.value() == pytest.approx(100.0)
        widget.panel_x_min_spin.setValue(5.0)
        widget.panel_x_max_spin.setValue(75.0)
        widget.panel_x_apply_button.click()
        assert applied == [("gas_components|ppm", 5.0, 75.0)]

        percent_index = widget.panel_scale_combo.findData(
            "gas_components|%"
        )
        assert percent_index >= 0
        widget.panel_scale_combo.setCurrentIndex(percent_index)
        assert not widget.panel_x_auto_check.isChecked()
        assert widget.panel_x_min_spin.value() == pytest.approx(0.0)
        assert widget.panel_x_max_spin.value() == pytest.approx(2.0)

        widget.panel_x_auto_check.setChecked(True)
        widget.panel_x_apply_button.click()
        assert reset == ["gas_components|%"]
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
