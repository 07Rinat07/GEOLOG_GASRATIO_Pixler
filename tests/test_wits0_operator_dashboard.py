from __future__ import annotations

import importlib.util

import pytest


@pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None
    or importlib.util.find_spec("pyqtgraph") is None,
    reason="PySide6/pyqtgraph are not installed in the headless test environment",
)
def test_operator_dashboard_renders_indicators_and_independent_panels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from geoworkbench.domain.models import IndexRole, IndexType
    from geoworkbench.services.acquisition_live_view import (
        AcquisitionCurrentValue,
        AcquisitionLiveAxisMode,
        AcquisitionLiveQuality,
        AcquisitionLiveSeries,
        AcquisitionLiveSnapshot,
    )
    from geoworkbench.services.localization import AppLanguage
    from geoworkbench.ui.wits0_operator_dashboard import (
        Wits0OperatorDashboard,
    )

    app = QApplication.instance() or QApplication([])
    dashboard = Wits0OperatorDashboard(language=AppLanguage.RU)
    snapshot = AcquisitionLiveSnapshot(
        dataset_id="dataset-1",
        session_id="session-1",
        axis_mode=AcquisitionLiveAxisMode.TIME,
        index_id="time",
        index_type=IndexType.DATETIME,
        index_role=IndexRole.TIME,
        index_mnemonic="DATETIME",
        index_unit=None,
        axis_is_datetime=True,
        window_start=1_700_000_000.0,
        window_end=1_700_000_002.0,
        auto_follow=True,
        paused=False,
        visible_row_count=3,
        total_row_count=3,
        source_point_count=6,
        rendered_point_count=6,
        current_values=(
            AcquisitionCurrentValue(
                curve_id="depth",
                mnemonic="HOLE_DEPTH",
                unit="m",
                value=5550.73,
                quality=AcquisitionLiveQuality.GOOD,
                quality_codes=(),
                sample_row_index=2,
                latest_row_index=2,
                axis_value=1_700_000_002.0,
                received_at="2026-09-22T06:00:02Z",
                source_sequence_no=3,
                age_rows=0,
            ),
            AcquisitionCurrentValue(
                curve_id="gas",
                mnemonic="TOTAL_GAS",
                unit="%Gas",
                value=0.012,
                quality=AcquisitionLiveQuality.GOOD,
                quality_codes=(),
                sample_row_index=2,
                latest_row_index=2,
                axis_value=1_700_000_002.0,
                received_at="2026-09-22T06:00:02Z",
                source_sequence_no=3,
                age_rows=0,
            ),
        ),
        series=(
            AcquisitionLiveSeries(
                curve_id="depth",
                mnemonic="HOLE_DEPTH",
                unit="m",
                axis_values=(
                    1_700_000_000.0,
                    1_700_000_001.0,
                    1_700_000_002.0,
                ),
                values=(5550.4, 5550.6, 5550.73),
                source_point_count=3,
                rendered_point_count=3,
            ),
            AcquisitionLiveSeries(
                curve_id="gas",
                mnemonic="TOTAL_GAS",
                unit="%Gas",
                axis_values=(
                    1_700_000_000.0,
                    1_700_000_001.0,
                    1_700_000_002.0,
                ),
                values=(0.01, 0.011, 0.012),
                source_point_count=3,
                rendered_point_count=3,
            ),
        ),
        markers=(),
        revision=(3, 3, False, True, "time"),
    )

    try:
        dashboard.render_snapshot(snapshot)
        app.processEvents()

        assert set(dashboard._indicator_cards) == {"depth", "gas"}
        assert not dashboard.panels["depth"].box.isHidden()
        assert not dashboard.panels["gas_total"].box.isHidden()
        assert dashboard.panels["load"].box.isHidden()
        assert len(
            dashboard.panels["depth"].plot.getPlotItem().listDataItems()
        ) == 1
        assert len(
            dashboard.panels["gas_total"].plot.getPlotItem().listDataItems()
        ) == 1
        depth_plot = dashboard.panels["depth"].plot
        gas_plot = dashboard.panels["gas_total"].plot
        depth_parameter_range = depth_plot.viewRange()[0]
        gas_parameter_range = gas_plot.viewRange()[0]
        depth_history_range = depth_plot.viewRange()[1]
        gas_history_range = gas_plot.viewRange()[1]

        assert depth_parameter_range != gas_parameter_range
        assert depth_plot.getViewBox().state["yInverted"] is True
        assert gas_plot.getViewBox().state["yInverted"] is True
        assert sorted(depth_history_range) == pytest.approx(
            sorted(gas_history_range)
        )
        assert sorted(depth_history_range) == pytest.approx(
            [snapshot.window_start, snapshot.window_end]
        )

        depth_item = depth_plot.getPlotItem().listDataItems()[0]
        gas_item = gas_plot.getPlotItem().listDataItems()[0]
        depth_x, depth_y = depth_item.getData()
        gas_x, gas_y = gas_item.getData()
        assert tuple(depth_x) == pytest.approx((5550.4, 5550.6, 5550.73))
        assert tuple(depth_y) == pytest.approx(
            (1_700_000_000.0, 1_700_000_001.0, 1_700_000_002.0)
        )
        assert tuple(gas_x) == pytest.approx((0.01, 0.011, 0.012))
        assert tuple(gas_y) == pytest.approx(
            (1_700_000_000.0, 1_700_000_001.0, 1_700_000_002.0)
        )
    finally:
        dashboard.close()
        app.processEvents()



@pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None
    or importlib.util.find_spec("pyqtgraph") is None,
    reason="PySide6/pyqtgraph are not installed in the headless test environment",
)
def test_operator_dashboard_splits_semantic_panel_when_units_differ(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from geoworkbench.domain.models import IndexRole, IndexType
    from geoworkbench.services.acquisition_live_view import (
        AcquisitionCurrentValue,
        AcquisitionLiveAxisMode,
        AcquisitionLiveQuality,
        AcquisitionLiveSeries,
        AcquisitionLiveSnapshot,
    )
    from geoworkbench.services.localization import AppLanguage
    from geoworkbench.ui.wits0_operator_dashboard import Wits0OperatorDashboard

    app = QApplication.instance() or QApplication([])
    dashboard = Wits0OperatorDashboard(language=AppLanguage.RU)
    snapshot = AcquisitionLiveSnapshot(
        dataset_id="dataset-1",
        session_id="session-1",
        axis_mode=AcquisitionLiveAxisMode.TIME,
        index_id="time",
        index_type=IndexType.DATETIME,
        index_role=IndexRole.TIME,
        index_mnemonic="DATETIME",
        index_unit=None,
        axis_is_datetime=True,
        window_start=1_700_000_000.0,
        window_end=1_700_000_002.0,
        auto_follow=True,
        paused=False,
        visible_row_count=3,
        total_row_count=3,
        source_point_count=6,
        rendered_point_count=6,
        current_values=(
            AcquisitionCurrentValue(
                curve_id="c1",
                mnemonic="C1",
                unit="ppm",
                value=21.0,
                quality=AcquisitionLiveQuality.GOOD,
                quality_codes=(),
                sample_row_index=2,
                latest_row_index=2,
                axis_value=1_700_000_002.0,
                received_at="2026-09-24T08:00:02Z",
                source_sequence_no=3,
                age_rows=0,
            ),
            AcquisitionCurrentValue(
                curve_id="co2",
                mnemonic="CO2",
                unit="%",
                value=0.8,
                quality=AcquisitionLiveQuality.GOOD,
                quality_codes=(),
                sample_row_index=2,
                latest_row_index=2,
                axis_value=1_700_000_002.0,
                received_at="2026-09-24T08:00:02Z",
                source_sequence_no=3,
                age_rows=0,
            ),
        ),
        series=(
            AcquisitionLiveSeries(
                curve_id="c1",
                mnemonic="C1",
                unit="ppm",
                axis_values=(1_700_000_000.0, 1_700_000_001.0, 1_700_000_002.0),
                values=(10.0, 15.0, 21.0),
                source_point_count=3,
                rendered_point_count=3,
            ),
            AcquisitionLiveSeries(
                curve_id="co2",
                mnemonic="CO2",
                unit="%",
                axis_values=(1_700_000_000.0, 1_700_000_001.0, 1_700_000_002.0),
                values=(0.5, 0.6, 0.8),
                source_point_count=3,
                rendered_point_count=3,
            ),
        ),
        markers=(),
        revision=(3, 3, False, True, "time"),
    )

    try:
        dashboard.render_snapshot(snapshot)
        app.processEvents()

        base = dashboard.panels["gas_components"]
        assert not base.box.isHidden()
        assert len(dashboard._unit_panels) == 1
        extra = next(iter(dashboard._unit_panels.values()))
        assert not extra.box.isHidden()
        assert "[ppm]" in base.box.title()
        assert "[%]" in extra.box.title()

        base_items = base.plot.getPlotItem().listDataItems()
        extra_items = extra.plot.getPlotItem().listDataItems()
        assert len(base_items) == 1
        assert len(extra_items) == 1
        assert base_items[0].name().startswith("C1")
        assert extra_items[0].name().startswith("CO2")

        base_range = base.plot.viewRange()[0]
        extra_range = extra.plot.viewRange()[0]
        assert base_range != extra_range
    finally:
        dashboard.close()
        app.processEvents()
