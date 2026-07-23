from datetime import datetime, timezone

import numpy as np
import pyqtgraph as pg
import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent
from PySide6.QtTest import QTest

from geoworkbench.domain.models import (
    CanvasObject,
    CurveData,
    CurveMetadata,
    CuttingsComponent,
    CuttingsSample,
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
    LithologyInterval,
    StratigraphyInterval,
)
from geoworkbench.project.lithotype_catalog_controller import CatalogLithotype
from geoworkbench.tablet.models import (
    CurveDisplaySettings,
    CurveLineStyle,
    CurveStyle,
    TabletLayout,
    TrackDefinition,
    TrackKind,
    XScale,
)
from geoworkbench.tablet.tablet_view import TabletTrackWidget, TabletView, curve_legend_label
from geoworkbench.project.annotation_schema import AnnotationKind


def make_curve(dataset_id: str, mnemonic: str, unit: str | None) -> CurveData:
    return CurveData(
        CurveMetadata(
            f"curve-{mnemonic}",
            mnemonic,
            mnemonic,
            unit,
            None,
            dataset_id,
        ),
        np.array([1.0, 2.0]),
    )


def test_curve_legend_label_includes_unit_only_when_present() -> None:
    assert curve_legend_label(make_curve("dataset", "C1", "%")) == "C1 [%]"
    assert curve_legend_label(make_curve("dataset", "ROP", None)) == "ROP"
    assert curve_legend_label(make_curve("dataset", "GR", "  API  ")) == "GR [API]"


def test_callout_request_has_visible_leader_and_editable_box(qapp) -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0]),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout([TrackDefinition("curve", "Curve", TrackKind.CURVE, width=220)])
    )
    view.set_dataset(dataset)

    payload = view.annotation_request_at_view_center(AnnotationKind.CALLOUT)

    assert payload is not None
    assert payload["track_id"] == "curve"
    assert payload["offset_x"] == pytest.approx(54.0)
    assert payload["offset_y"] == pytest.approx(-68.0)
    assert payload["width"] == pytest.approx(240.0)
    assert payload["height"] == pytest.approx(86.0)
    view.close()


def test_tablet_view_exposes_rendered_legend_labels(qapp) -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0]),
    )
    c1 = make_curve(dataset.dataset_id, "C1", "%")
    rop = make_curve(dataset.dataset_id, "ROP", None)
    dataset.curves = {c1.metadata.curve_id: c1, rop.metadata.curve_id: rop}
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition(
                    "curves",
                    "Curves",
                    TrackKind.CURVE,
                    curve_mnemonics=["C1", "ROP"],
                )
            ]
        )
    )

    view.set_dataset(dataset)
    qapp.processEvents()

    assert view.legend_labels("curves") == (
        "Содержание метана",
        "Скорость бурения (по глубине)",
    )
    view.close()


def test_tablet_uses_single_unscaled_depth_axis(qapp) -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([950.0, 1100.0, 1250.0]),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120),
                TrackDefinition("curve", "Curve", TrackKind.CURVE, width=220),
            ]
        )
    )

    view.set_dataset(dataset)

    depth_axis = view._rendered["depth"].plot.getAxis("left")
    curve_axis = view._rendered["curve"].plot.getAxis("left")
    assert depth_axis.isVisible()
    assert depth_axis.autoSIPrefix is False
    assert not curve_axis.isVisible()
    assert view._rendered["depth"].plot.toolTip().startswith("Колесо — прокрутка")
    view.close()


def test_tablet_cursor_line_is_synchronized_and_reports_all_curve_values(qapp) -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 150.0, 200.0]),
    )
    c1 = CurveData(
        CurveMetadata("c1", "C1", "C1", "%", "Methane", dataset.dataset_id),
        np.array([1.0, 2.0, 3.0]),
    )
    rop = CurveData(
        CurveMetadata("rop", "ROP", "ROP", "m/h", "ROP", dataset.dataset_id),
        np.array([10.0, 20.0, 30.0]),
    )
    dataset.curves = {"c1": c1, "rop": rop}
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("gas", "Gas", TrackKind.GAS, curve_mnemonics=["C1"]),
                TrackDefinition("rop", "ROP", TrackKind.CURVE, curve_mnemonics=["ROP"]),
            ]
        )
    )
    view.set_dataset(dataset)

    view.set_cursor_enabled(True)
    view.set_cursor_depth(151.0)

    assert view.cursor_depth == 150.0
    assert all(item.cursor_line is not None for item in view._rendered.values())
    assert all(item.cursor_line.value() == 150.0 for item in view._rendered.values())
    assert view.cursor_summary(151.0) == (
        "Глубина: 150 m | Содержание метана [C1]: 2 % | Скорость бурения (по глубине) [ROP]: 20 m/h"
    )
    view.set_cursor_style("#123456", 3.5)
    assert all(
        item.cursor_line.pen.color().name() == "#123456" and item.cursor_line.pen.widthF() == 3.5
        for item in view._rendered.values()
        if item.cursor_line is not None
    )
    view.close()


def test_tablet_renders_percentage_cuttings_track_and_cursor_summary(qapp) -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 105.0, 110.0]),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout([TrackDefinition("cuttings", "Cuttings", TrackKind.CUTTINGS, width=240)])
    )
    view.set_lithology(
        [],
        (
            CatalogLithotype(
                "sand",
                "S",
                "Песчаник",
                "Sandstone",
                "sedimentary",
                "#ffee00",
                "solid",
                True,
                "Құмтас",
            ),
            CatalogLithotype(
                "clay", "C", "Глина", "Clay", "sedimentary", "#00aa00", "solid", True, "Саз"
            ),
        ),
    )
    view.set_cuttings(
        [
            CuttingsSample(
                "sample",
                100.0,
                110.0,
                [CuttingsComponent("sand", 70.0), CuttingsComponent("clay", 30.0)],
            )
        ]
    )
    view.set_dataset(dataset)

    items = view._rendered["cuttings"].cuttings_items
    assert items is not None and len(items["sample"]) == 2
    assert "Шлам 100–110 m: Песчаник: 70%; Глина: 30%" in view.cursor_summary(105.0)
    view.close()


def test_tablet_renders_calcimetry_lba_and_cursor_summary(qapp) -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 105.0, 110.0]),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("calc", "Calcimetry", TrackKind.CALCIMETRY, width=220),
                TrackDefinition("lba", "LBA", TrackKind.LBA, width=260),
            ]
        )
    )
    view.set_cuttings(
        [
            CuttingsSample(
                "sample",
                100.0,
                110.0,
                calcite_percent=65.0,
                dolomite_percent=20.0,
                lba_type_id="Oil show",
                lba_intensity=3,
                lba_color="yellow",
                lba_cut="Streaming",
                analysis_interpretation="Manual show interpretation",
            )
        ]
    )
    view.set_dataset(dataset)

    calc_items = view._rendered["calc"].analysis_items
    lba_items = view._rendered["lba"].analysis_items
    summary = view.cursor_summary(105.0)

    assert calc_items is not None and len(calc_items["sample"]) >= 4
    assert lba_items is not None and len(lba_items["sample"]) >= 6
    assert view._rendered["lba"].plot.viewRange()[0][1] >= 2.9
    assert ("Кальциметрия: CaCO₃ 65%; CaMg(CO₃)₂ 20%; нерастворимый остаток 15%") in summary
    assert "ЛБА: Oil show; I=3; yellow; Streaming" in summary
    assert "Интерпретация геолога: Manual show interpretation" in summary
    view.close()


def test_tablet_renders_nested_stratigraphy_lanes_and_cursor_summary(qapp) -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 150.0, 200.0]),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout([TrackDefinition("strat", "Stratigraphy", TrackKind.STRATIGRAPHY, width=220)])
    )
    view.set_stratigraphy(
        [
            StratigraphyInterval(
                "period", 100.0, 200.0, "K", "Cretaceous", "System / Period", "#7fc64e"
            ),
            StratigraphyInterval(
                "stage",
                125.0,
                175.0,
                "K1a",
                "Albian",
                "Stage / Age",
                "#a6d96a",
                "Reservoir",
            ),
        ]
    )
    view.set_dataset(dataset)

    items = view._rendered["strat"].stratigraphy_items
    summary = view.cursor_summary(150.0)

    assert items is not None and set(items) == {"period", "stage"}
    assert all(len(value) == 2 for value in items.values())
    assert "System / Period / K / Cretaceous" in summary
    assert "Stage / Age / K1a / Albian" in summary
    assert "Reservoir" in summary
    view.close()


def test_tablet_view_applies_saved_curve_pen_style(qapp) -> None:
    dataset = Dataset(
        "dataset-1", "Dataset", DatasetKind.GTI, DepthDomain.MD, np.array([100.0, 101.0])
    )
    curve = make_curve(dataset.dataset_id, "C1", "%")
    dataset.curves[curve.metadata.curve_id] = curve
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition(
                    "gas",
                    "Gas",
                    TrackKind.GAS,
                    curve_mnemonics=["C1"],
                    curve_styles={"C1": CurveStyle("#123456", 3.5, CurveLineStyle.DASH_DOT)},
                )
            ]
        )
    )
    view.set_dataset(dataset)

    pen = view._rendered["gas"].curve_items["C1"].opts["pen"]
    assert pen.color().name() == "#123456"
    assert pen.widthF() == 3.5
    assert pen.style() == Qt.PenStyle.DashDotLine
    view.close()


def test_track_widget_applies_saved_grid_settings(qapp) -> None:
    widget = TabletTrackWidget(
        TrackDefinition(
            "curve",
            "Curve",
            TrackKind.CURVE,
            grid_x=True,
            grid_y=False,
            grid_major_divisions=4,
            grid_minor_divisions=10,
            grid_alpha=0.4,
            grid_print=False,
        )
    )

    assert widget.plot.getAxis("bottom").grid == pytest.approx(102.0)
    assert widget.plot.getAxis("left").grid is False
    assert widget.plot.getAxis("bottom").tickSpacing(0.0, 100.0, 400.0) == [
        (25.0, 0.0),
        (2.5, 0.0),
    ]
    assert widget.plot.getAxis("left").tickSpacing(1000.0, 1100.0, 400.0) == [
        (25.0, 1000.0),
        (2.5, 1000.0),
    ]
    widget.close()


def test_track_widget_applies_saved_x_axis_label(qapp) -> None:
    widget = TabletTrackWidget(
        TrackDefinition("curve", "Curve", TrackKind.CURVE, x_axis_label="ROP, m/h")
    )

    assert widget.plot.getAxis("bottom").labelText == "ROP, m/h"
    widget.close()


def test_logarithmic_track_omits_curve_without_positive_values(qapp) -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0]),
    )
    curve = make_curve(dataset.dataset_id, "ZERO", None)
    curve.values = np.array([0.0, -1.0])
    dataset.curves[curve.metadata.curve_id] = curve
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition(
                    "log",
                    "Log",
                    TrackKind.CURVE,
                    curve_mnemonics=["ZERO"],
                    x_scale=XScale.LOGARITHMIC,
                )
            ]
        )
    )

    view.set_dataset(dataset)
    qapp.processEvents()

    assert view.legend_labels("log") == ()
    view.close()


def test_tablet_view_restores_saved_visible_depth_without_emitting_change(qapp) -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 150.0, 200.0]),
    )
    view = TabletView()
    emitted: list[tuple[float, float]] = []
    view.visible_depth_changed.connect(lambda top, bottom: emitted.append((top, bottom)))
    view.set_layout_model(
        TabletLayout(
            [TrackDefinition("depth", "Глубина", TrackKind.DEPTH)],
            visible_depth_top=120.0,
            visible_depth_bottom=160.0,
        )
    )

    view.set_dataset(dataset)
    qapp.processEvents()

    assert view.visible_depth_range == pytest.approx((120.0, 160.0))
    assert emitted == []
    view.close()


def test_tablet_clamps_saved_depth_window_to_loaded_las(qapp) -> None:
    dataset = Dataset(
        "dataset-1",
        "Loaded LAS",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([1000.0, 1100.0, 1220.0]),
    )
    layout = TabletLayout(
        [TrackDefinition("depth", "Глубина", TrackKind.DEPTH)],
        visible_depth_top=943.0,
        visible_depth_bottom=1268.0,
    )
    view = TabletView()
    emitted: list[tuple[float, float]] = []
    view.visible_depth_changed.connect(lambda top, bottom: emitted.append((top, bottom)))
    view.set_layout_model(layout)

    view.set_dataset(dataset)
    qapp.processEvents()

    assert view.visible_depth_range == pytest.approx((1000.0, 1220.0))
    assert (layout.visible_depth_top, layout.visible_depth_bottom) == (1000.0, 1220.0)
    assert emitted == []
    view.close()


def test_tablet_zoom_and_wheel_style_scroll_stay_inside_las_and_sync_tracks(qapp) -> None:
    dataset = Dataset(
        "dataset-1",
        "Loaded LAS",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([1000.0, 1100.0, 1220.0]),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("depth", "Глубина", TrackKind.DEPTH),
                TrackDefinition("curve", "Curve", TrackKind.CURVE),
            ]
        )
    )
    emitted: list[tuple[float, float]] = []
    view.visible_depth_changed.connect(lambda top, bottom: emitted.append((top, bottom)))
    view.set_dataset(dataset)

    # A new depth form opens at the application default of 50 m. Zooming by
    # 0.5 therefore produces a 25 m window and scrolling by ten 10% steps moves
    # it by exactly one visible window.
    assert view.visible_depth_range == pytest.approx((1000.0, 1050.0))
    assert view.zoom_depth(0.5)
    assert view.visible_depth_range == pytest.approx((1012.5, 1037.5))
    assert view.scroll_depth(10.0)

    assert view.visible_depth_range == pytest.approx((1037.5, 1062.5))
    assert view.track_depth_range("depth") == pytest.approx((1037.5, 1062.5))
    assert view.track_depth_range("curve") == pytest.approx((1037.5, 1062.5))
    assert emitted == pytest.approx([(1012.5, 1037.5), (1037.5, 1062.5)])
    view.close()


def test_tablet_mouse_wheel_scrolls_and_control_wheel_zooms_depth(qapp) -> None:
    dataset = Dataset(
        "dataset-1",
        "Loaded LAS",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([1000.0, 1100.0, 1220.0]),
    )
    view = TabletView()
    view.set_layout_model(TabletLayout([TrackDefinition("depth", "Глубина", TrackKind.DEPTH)]))
    view.resize(500, 500)
    view.show()
    view.set_dataset(dataset)
    qapp.processEvents()
    plot = view._rendered["depth"].plot
    assert plot is not None
    viewport = plot.viewport()

    zoom_event = QWheelEvent(
        QPointF(10.0, 10.0),
        QPointF(10.0, 10.0),
        QPoint(),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ControlModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    anchor_before = float(plot.getViewBox().mapSceneToView(plot.mapToScene(QPoint(10, 10))).y())
    qapp.sendEvent(viewport, zoom_event)

    zoomed = view.visible_depth_range
    assert zoomed is not None
    assert zoomed[1] - zoomed[0] == pytest.approx(40.0)
    anchor_after = float(plot.getViewBox().mapSceneToView(plot.mapToScene(QPoint(10, 10))).y())
    assert anchor_after == pytest.approx(anchor_before)

    scroll_event = QWheelEvent(
        QPointF(10.0, 10.0),
        QPointF(10.0, 10.0),
        QPoint(),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    qapp.sendEvent(viewport, scroll_event)

    scrolled = view.visible_depth_range
    assert scrolled is not None
    assert scrolled[1] - scrolled[0] == pytest.approx(40.0)
    assert scrolled[0] == pytest.approx(zoomed[0] + 4.0)
    view.close()


def test_tablet_view_limits_points_and_updates_them_for_visible_depth(qapp) -> None:
    depth = np.arange(20_000, dtype=np.float64)
    dataset = Dataset(
        "dataset-1",
        "Large Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    curve = make_curve(dataset.dataset_id, "ROP", "m/h")
    curve.values = depth * 0.1
    dataset.curves[curve.metadata.curve_id] = curve
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition(
                    "curve",
                    "ROP",
                    TrackKind.CURVE,
                    curve_mnemonics=["ROP"],
                )
            ]
        )
    )

    view.set_dataset(dataset)
    qapp.processEvents()
    full_count = view.rendered_curve_point_count("curve", "ROP")
    emitted: list[tuple[float, float]] = []
    view.visible_depth_changed.connect(lambda top, bottom: emitted.append((top, bottom)))
    view.set_visible_depth(100.0, 200.0)
    qapp.processEvents()

    assert full_count == 51
    assert view.rendered_curve_point_count("curve", "ROP") == 101
    assert emitted == []
    view.close()


def test_user_depth_change_updates_samples_and_linked_tracks(qapp) -> None:
    depth = np.arange(1000, dtype=np.float64)
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    curve = make_curve(dataset.dataset_id, "ROP", "m/h")
    curve.values = depth
    dataset.curves[curve.metadata.curve_id] = curve
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("depth", "Глубина", TrackKind.DEPTH),
                TrackDefinition(
                    "curve",
                    "ROP",
                    TrackKind.CURVE,
                    curve_mnemonics=["ROP"],
                ),
            ]
        )
    )
    emitted: list[tuple[float, float]] = []
    view.visible_depth_changed.connect(lambda top, bottom: emitted.append((top, bottom)))
    view.resize(800, 600)
    view.show()
    view.set_dataset(dataset)
    qapp.processEvents()
    depth_widget = view.findChild(TabletTrackWidget, "track-depth")
    assert depth_widget is not None
    master_plot = depth_widget.findChild(pg.PlotWidget)
    assert master_plot is not None

    master_plot.setYRange(100.0, 200.0, padding=0)
    qapp.processEvents()

    assert emitted[-1] == pytest.approx((100.0, 200.0))
    assert view.track_depth_range("depth") == pytest.approx((100.0, 200.0))
    assert view.track_depth_range("curve") == pytest.approx((100.0, 200.0))
    assert view.rendered_curve_point_count("curve", "ROP") == 101
    view.close()


def test_tablet_view_renders_legacy_annotation_once_on_preferred_track(qapp) -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 150.0, 200.0]),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("depth", "Глубина", TrackKind.DEPTH),
                TrackDefinition("curve", "Curve", TrackKind.CURVE),
            ]
        )
    )
    view.set_canvas_objects(
        [
            CanvasObject(
                "note-1",
                "depth_annotation",
                "depth",
                0.0,
                150.0,
                1.0,
                0.0,
                top_depth=150.0,
                bottom_depth=150.0,
                properties={"text": "Газопроявление"},
            )
        ]
    )

    view.set_dataset(dataset)
    qapp.processEvents()

    assert view.rendered_annotation_ids("depth") == ()
    assert view.rendered_annotation_ids("curve") == ("note-1",)
    view.close()


def test_tablet_view_renders_lithology_intervals(qapp) -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 150.0, 200.0]),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition(
                    "lithology",
                    "Литология",
                    TrackKind.LITHOLOGY,
                    show_interval_labels=True,
                )
            ]
        )
    )
    view.set_lithology(
        [LithologyInterval("layer-1", 110.0, 160.0, "sandstone", "Песчаник")],
        (
            CatalogLithotype(
                "sandstone",
                "SS",
                "Песчаник",
                "Sandstone",
                "sedimentary",
                "#e7cf8b",
                "sandstone_bricks",
                True,
            ),
        ),
    )

    view.set_dataset(dataset)
    qapp.processEvents()

    assert view.rendered_lithology_ids("lithology") == ("layer-1",)
    assert view.rendered_lithology_codes("lithology") == ("SS",)
    view.close()


def test_tablet_view_renders_safe_lithology_descriptions(qapp) -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 150.0, 200.0]),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout([TrackDefinition("description", "Описание", TrackKind.TEXT)])
    )
    view.set_lithology(
        [LithologyInterval("layer-1", 110.0, 160.0, "sandstone", "Песчаник <b>средний</b>")],
        (),
    )

    view.set_dataset(dataset)
    qapp.processEvents()

    assert view.rendered_lithology_descriptions("description") == ("Песчаник <b>средний</b>",)
    view.close()


def test_lithology_text_appears_when_thin_interval_is_zoomed(qapp) -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([0.0, 500.0, 1000.0]),
    )
    view = TabletView()
    view.resize(800, 600)
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition(
                    "lithology",
                    "Литология",
                    TrackKind.LITHOLOGY,
                    show_interval_labels=True,
                )
            ]
        )
    )
    view.set_lithology(
        [LithologyInterval("thin", 100.0, 101.0, "sandstone", None)],
        (
            CatalogLithotype(
                "sandstone", "SS", "Песчаник", "Sandstone", "rock", "#e7cf8b", "dots", True
            ),
        ),
    )
    view.show()
    view.set_dataset(dataset)
    qapp.processEvents()

    assert view.visible_lithology_text_ids("lithology") == ()

    view.set_visible_depth(99.0, 102.0)
    qapp.processEvents()

    assert view.visible_lithology_text_ids("lithology") == ("thin",)
    view.close()


def test_tablet_renders_interpretation_track_and_hit_tests_lanes(qapp) -> None:
    from geoworkbench.domain.models import InterpretationInterval, WellInterpretation

    dataset = Dataset(
        "dataset-interpretation",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 150.0, 200.0]),
    )
    interpretation = WellInterpretation(
        "primary",
        "Primary",
        intervals=[
            InterpretationInterval(
                "fluid",
                120.0,
                160.0,
                "Fluid",
                "Gas",
                "#bfdbfe",
                "Confirmed by gas response",
            ),
            InterpretationInterval(
                "reservoir",
                130.0,
                180.0,
                "Reservoir",
                "Sand A",
                "#fde68a",
            ),
        ],
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition(
                    "interpretation-track",
                    "Interpretation",
                    TrackKind.INTERPRETATION,
                    width=280,
                )
            ]
        )
    )
    view.set_interpretations([interpretation], interpretation.interpretation_id)
    view.set_dataset(dataset)
    qapp.processEvents()

    assert view.rendered_interpretation_ids("interpretation-track") == (
        "fluid",
        "reservoir",
    )
    assert view.hit_test_interpretation("interpretation-track", 0.5, 140.0) == "fluid"
    assert view.hit_test_interpretation("interpretation-track", 1.5, 140.0) == "reservoir"
    assert view.hit_test_interpretation("interpretation-track", 1.5, 190.0) is None
    assert "Интерпретация «Primary»: Fluid / Gas (120–160 m)" in view.cursor_summary(150.0)
    track_widget = view._rendered["interpretation-track"].widget
    assert isinstance(track_widget, TabletTrackWidget)
    assert track_widget.title.text() == "Interpretation: Primary"
    view.close()


def test_tablet_interpretation_selection_updates_style_and_signal(qapp) -> None:
    from geoworkbench.domain.models import InterpretationInterval, WellInterpretation

    dataset = Dataset(
        "dataset-selection",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 200.0]),
    )
    interval = InterpretationInterval(
        "interval",
        110.0,
        150.0,
        "Reservoir",
        "Sand A",
        "#fde68a",
    )
    interpretation = WellInterpretation("primary", "Primary", intervals=[interval])
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [TrackDefinition("interpretation", "Interpretation", TrackKind.INTERPRETATION)]
        )
    )
    view.set_interpretations([interpretation], interpretation.interpretation_id)
    view.set_dataset(dataset)
    selected: list[tuple[str, str]] = []
    cleared: list[bool] = []
    view.interval_selected.connect(lambda first, second: selected.append((first, second)))
    view.interval_selection_cleared.connect(lambda: cleared.append(True))

    assert view.set_selected_interval("primary", "interval", emit_signal=True) is True
    bar = view._rendered["interpretation"].interpretation_items["interval"][0]
    assert isinstance(bar, pg.BarGraphItem)
    assert bar.opts["pen"].widthF() == 3.0
    assert selected == [("primary", "interval")]

    assert view.clear_interval_selection(emit_signal=True) is True
    assert bar.opts["pen"].widthF() == 0.8
    assert cleared == [True]
    view.close()


def _dataset_with_depth_and_datetime() -> Dataset:
    depth = np.array([1000.0, 1010.0, 1020.0, 1030.0, 1040.0])
    dataset = Dataset(
        "dataset-time",
        "Time dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    time_values = np.array(
        [
            "2026-07-18T10:00:00",
            "2026-07-18T10:10:00",
            "2026-07-18T10:20:00",
            "2026-07-18T10:30:00",
            "2026-07-18T10:40:00",
        ],
        dtype="datetime64[ns]",
    )
    dataset.add_index(
        DatasetIndex(
            "time-index",
            "DATETIME",
            IndexType.DATETIME,
            IndexRole.TIME,
            None,
            time_values,
            datetime_format="ISO 8601",
            timezone="UTC",
        )
    )
    curve = CurveData(
        CurveMetadata("curve-rop", "ROP", "ROP", "m/h", None, dataset.dataset_id),
        np.array([10.0, 12.0, 15.0, 11.0, 9.0]),
    )
    dataset.curves[curve.metadata.curve_id] = curve
    return dataset


def test_tablet_can_switch_vertical_axis_from_depth_to_datetime(qapp) -> None:
    dataset = _dataset_with_depth_and_datetime()
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("depth", "Depth", TrackKind.DEPTH),
                TrackDefinition("rop", "ROP", TrackKind.CURVE, curve_mnemonics=["ROP"]),
            ]
        )
    )
    view.set_dataset(dataset)
    qapp.processEvents()

    assert set(view.available_vertical_indexes()) == {
        dataset.active_index.index_id,
        "time-index",
    }
    assert view.set_vertical_index("time-index")
    qapp.processEvents()

    assert view.vertical_axis_is_time is True
    assert view.vertical_index_id == "time-index"
    top, bottom = view.visible_depth_range or (0.0, 0.0)
    assert view.format_vertical_value(top).startswith("18.07.2026 10:00")
    assert view.format_vertical_value(bottom).startswith("18.07.2026 10:30")
    _, rendered_y = view._rendered["rop"].curve_items["ROP"].getData()
    assert rendered_y is not None
    assert np.diff(rendered_y).tolist() == pytest.approx([600.0, 600.0, 600.0])
    axis = view._rendered["depth"].plot.getAxis("left")
    assert "10:00" in axis.tickStrings([float(rendered_y[0])], 1.0, 60.0)[0]
    view.close()


def test_vertical_scrollbar_moves_all_tracks_in_same_time_window(qapp) -> None:
    dataset = _dataset_with_depth_and_datetime()
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("depth", "Depth", TrackKind.DEPTH),
                TrackDefinition("rop", "ROP", TrackKind.CURVE, curve_mnemonics=["ROP"]),
            ],
            vertical_index_id="time-index",
        )
    )
    view.resize(700, 500)
    view.show()
    view.set_dataset(dataset)
    qapp.processEvents()

    assert view.zoom_depth(0.5)
    qapp.processEvents()
    before = view.visible_depth_range
    assert before is not None
    assert view._vertical_scrollbar.maximum() == 1_000_000
    view._vertical_scrollbar.setValue(view._vertical_scrollbar.maximum())
    qapp.processEvents()

    after = view.visible_depth_range
    assert after is not None
    assert after[0] > before[0]
    assert view.track_depth_range("depth") == pytest.approx(after)
    assert view.track_depth_range("rop") == pytest.approx(after)
    assert view._range_label.text().startswith("Показано:")
    view.close()


def test_go_to_datetime_centers_visible_time_window(qapp) -> None:
    dataset = _dataset_with_depth_and_datetime()
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [TrackDefinition("depth", "Depth", TrackKind.DEPTH)],
            vertical_index_id="time-index",
        )
    )
    view.set_dataset(dataset)
    assert view.zoom_depth(0.5)

    target = datetime(2026, 7, 18, 10, 30, tzinfo=timezone.utc).timestamp()
    assert view.go_to_vertical_value(target)
    visible = view.visible_depth_range
    assert visible is not None
    assert sum(visible) / 2.0 == pytest.approx(target)
    view.close()


def test_tablet_keyboard_navigation_moves_camera(qapp) -> None:
    dataset = Dataset(
        "dataset-keyboard",
        "Keyboard navigation",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.linspace(0.0, 1000.0, 101),
    )
    view = TabletView()
    view.set_layout_model(TabletLayout([TrackDefinition("depth", "Глубина", TrackKind.DEPTH)]))
    view.resize(500, 500)
    view.show()
    view.set_dataset(dataset)
    view.set_visible_depth(100.0, 300.0)
    qapp.processEvents()
    plot = view._rendered["depth"].plot
    assert plot is not None
    viewport = plot.viewport()

    qapp.sendEvent(
        viewport,
        QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_PageDown, Qt.KeyboardModifier.NoModifier),
    )
    assert view.visible_depth_range == pytest.approx((280.0, 480.0))

    qapp.sendEvent(
        viewport,
        QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Home, Qt.KeyboardModifier.NoModifier),
    )
    assert view.visible_depth_range == pytest.approx((0.0, 200.0))

    qapp.sendEvent(
        viewport,
        QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_End, Qt.KeyboardModifier.NoModifier),
    )
    assert view.visible_depth_range == pytest.approx((800.0, 1000.0))
    view.close()


def test_tablet_view_keeps_depth_in_form_order_and_scrolls_wide_canvas(qapp):
    dataset = Dataset(
        "dataset-scroll",
        "Scroll",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.linspace(0.0, 100.0, 100),
    )
    curve = CurveData(
        CurveMetadata("curve-1", "ROP", "ROP", "m/h", None, dataset.dataset_id),
        np.linspace(1.0, 10.0, 100),
    )
    dataset.curves[curve.metadata.curve_id] = curve
    view = TabletView()
    view.resize(640, 480)
    tracks = [TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120)]
    tracks.extend(
        TrackDefinition(
            f"curve-{i}",
            f"Curve {i}",
            TrackKind.CURVE,
            width=220,
            curve_mnemonics=["ROP"],
        )
        for i in range(8)
    )
    view.set_layout_model(TabletLayout(tracks=tracks))
    view.set_dataset(dataset)
    view.show()
    qapp.processEvents()

    assert view.pinned_track_ids == ()
    assert view.rendered_track_ids[0] == "depth"
    assert view.horizontal_scroll_range()[1] > 0
    view.close()


def test_tablet_view_lod_budget_is_pixel_aware():
    from geoworkbench.tablet.tablet_view import TabletView

    assert TabletView._lod_point_budget(100) == 5000
    assert TabletView._lod_point_budget(1000) == 5000
    assert TabletView._lod_point_budget(100_000) == 20_000


def test_partial_style_refresh_updates_only_target_track(qapp) -> None:
    from geoworkbench.tablet.render_invalidation import DirtyReason

    dataset = Dataset(
        "dataset-dirty",
        "Dirty",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.linspace(0.0, 100.0, 101),
    )
    for mnemonic in ("ROP", "TG"):
        dataset.curves[f"curve-{mnemonic}"] = CurveData(
            CurveMetadata(f"curve-{mnemonic}", mnemonic, mnemonic, "%", None, dataset.dataset_id),
            np.linspace(1.0, 10.0, 101),
        )
    layout = TabletLayout(
        [
            TrackDefinition("rop", "ROP", TrackKind.CURVE, curve_mnemonics=["ROP"]),
            TrackDefinition("tg", "TG", TrackKind.CURVE, curve_mnemonics=["TG"]),
        ]
    )
    view = TabletView()
    view.set_layout_model(layout)
    view.set_dataset(dataset)
    rop_widget = view._rendered["rop"].widget
    tg_widget = view._rendered["tg"].widget
    before = view.dirty_render_stats()

    layout.track_by_id("rop").set_curve_style(
        "ROP", CurveStyle("#ff0000", 3.0, CurveLineStyle.DASH)
    )
    assert view.refresh_track("rop", DirtyReason.STYLE | DirtyReason.DATA)

    after = view.dirty_render_stats()
    assert view._rendered["rop"].widget is rop_widget
    assert view._rendered["tg"].widget is tg_widget
    assert after.full_updates == before.full_updates
    assert after.partial_updates == before.partial_updates + 1
    assert view._rendered["rop"].curve_items["ROP"].opts["pen"].color().name() == "#ff0000"
    view.close()


def test_static_layer_cache_reuses_track_descriptor(qapp) -> None:
    from geoworkbench.tablet.render_invalidation import DirtyReason

    dataset = Dataset(
        "dataset-static",
        "Static",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.linspace(0.0, 10.0, 11),
    )
    layout = TabletLayout([TrackDefinition("depth", "Глубина", TrackKind.DEPTH)])
    view = TabletView()
    view.set_layout_model(layout)
    view.set_dataset(dataset)

    assert view.refresh_track("depth", DirtyReason.STATIC)
    first = view.static_layer_cache_stats()
    assert first.misses == 1
    assert view.refresh_track("depth", DirtyReason.STYLE)
    second = view.static_layer_cache_stats()
    assert second.hits == 1
    assert second.entries == 1
    view.close()


def test_dirty_data_invalidation_clears_only_requested_curve_cache(qapp) -> None:
    from geoworkbench.tablet.render_invalidation import DirtyReason

    dataset = Dataset(
        "dataset-cache-invalidation",
        "Cache invalidation",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.linspace(0.0, 100.0, 1001),
    )
    for mnemonic in ("ROP", "TG"):
        dataset.curves[f"curve-{mnemonic}"] = CurveData(
            CurveMetadata(f"curve-{mnemonic}", mnemonic, mnemonic, "%", None, dataset.dataset_id),
            np.linspace(1.0, 2.0, 1001),
        )
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("rop", "ROP", TrackKind.CURVE, curve_mnemonics=["ROP"]),
                TrackDefinition("tg", "TG", TrackKind.CURVE, curve_mnemonics=["TG"]),
            ]
        )
    )
    view.set_dataset(dataset)
    assert view.geometry_cache_stats().entries == 2

    view.invalidate_track("rop", DirtyReason.DATA)
    assert view.geometry_cache_stats().entries == 1
    assert view.refresh_dirty_tracks() == 1
    assert view.geometry_cache_stats().entries == 2
    view.close()


def test_cursor_overlay_update_does_not_rebuild_curve_geometry(qapp) -> None:
    from geoworkbench.tablet.overlay_layers import OverlayLayerKind

    dataset = Dataset(
        "dataset-overlay-cursor",
        "Overlay cursor",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.linspace(0.0, 100.0, 1001),
    )
    dataset.curves["curve-tg"] = CurveData(
        CurveMetadata("curve-tg", "TG", "TG", "%", None, dataset.dataset_id),
        np.linspace(1.0, 2.0, 1001),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout([TrackDefinition("gas", "Gas", TrackKind.GAS, curve_mnemonics=["TG"])])
    )
    view.set_dataset(dataset)
    before_geometry = view.geometry_cache_stats()
    before_dirty = view.dirty_render_stats()

    view.set_cursor_enabled(True)
    view.set_cursor_depth(42.0)

    after_geometry = view.geometry_cache_stats()
    after_dirty = view.dirty_render_stats()
    assert after_geometry == before_geometry
    assert after_dirty == before_dirty
    assert view.overlay_visible(OverlayLayerKind.CURSOR)
    assert view.overlay_layer_stats().items >= 1
    view.close()


def test_tooltip_and_rubber_band_are_independent_overlay_layers(qapp) -> None:
    from geoworkbench.tablet.overlay_layers import OverlayLayerKind

    dataset = Dataset(
        "dataset-overlay-tools",
        "Overlay tools",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.linspace(0.0, 10.0, 11),
    )
    view = TabletView()
    view.set_layout_model(TabletLayout([TrackDefinition("depth", "Depth", TrackKind.DEPTH)]))
    view.set_dataset(dataset)
    geometry_before = view.geometry_cache_stats()

    assert view.show_overlay_tooltip("depth", 0.5, 4.0, "Depth: 4 m")
    assert view.show_rubber_band("depth", 0.1, 0.9, 2.0, 5.0)
    assert view.overlay_layer_stats().items >= 3  # cursor + tooltip + rubber band
    assert view.geometry_cache_stats() == geometry_before
    assert view.clear_overlay_tooltip("depth") == 1
    assert view.clear_rubber_band("depth") == 1
    assert view.set_overlay_visible(OverlayLayerKind.ANNOTATION, False)
    assert not view.overlay_visible(OverlayLayerKind.ANNOTATION)
    view.close()


def test_tablet_selection_manager_tracks_widget_selection(qapp) -> None:
    dataset = Dataset(
        "dataset-selection-manager",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0]),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("depth", "Depth", TrackKind.DEPTH),
                TrackDefinition("curve", "Curve", TrackKind.CURVE),
            ]
        )
    )
    view.set_dataset(dataset)
    selected: list[object] = []
    view.selection_changed.connect(selected.append)

    assert view.select_track("curve") is True
    assert view.selection_snapshot.primary is not None
    assert view.selection_snapshot.primary.object_id == "curve"
    assert selected
    assert "2px solid #2563eb" in view._rendered["curve"].widget.styleSheet()

    assert view.clear_selection() is True
    assert view.selection_snapshot.items == ()
    assert "1px solid #cbd5e1" in view._rendered["curve"].widget.styleSheet()
    view.close()


def test_track_resize_is_undoable(qapp) -> None:
    dataset = Dataset(
        "dataset-resize-history",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0]),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout([TrackDefinition("curve", "Curve", TrackKind.CURVE, width=220)])
    )
    view.set_dataset(dataset)

    view._resize_track_from_widget("curve", 360)
    assert view.layout_model.track_by_id("curve").width == 360
    assert view.can_undo_interaction
    assert view.undo_interaction()
    assert view.layout_model.track_by_id("curve").width == 220
    assert view.redo_interaction()
    assert view.layout_model.track_by_id("curve").width == 360
    view.close()


def test_track_reorder_is_undoable(qapp) -> None:
    dataset = Dataset(
        "dataset-reorder-history",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0]),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("a", "A", TrackKind.CURVE),
                TrackDefinition("b", "B", TrackKind.CURVE),
                TrackDefinition("c", "C", TrackKind.CURVE),
            ]
        )
    )
    view.set_dataset(dataset)
    original_widgets = {
        track_id: rendered.widget for track_id, rendered in view._rendered.items()
    }

    assert view.move_track_with_history("a", 2)
    assert [track.track_id for track in view.layout_model.tracks] == ["b", "c", "a"]
    assert view.rendered_track_ids == ("b", "c", "a")
    assert all(
        view._rendered[track_id].widget is widget
        for track_id, widget in original_widgets.items()
    )
    assert view.undo_interaction()
    assert [track.track_id for track in view.layout_model.tracks] == ["a", "b", "c"]
    assert view.rendered_track_ids == ("a", "b", "c")
    assert view.redo_interaction()
    assert [track.track_id for track in view.layout_model.tracks] == ["b", "c", "a"]
    assert all(
        view._rendered[track_id].widget is widget
        for track_id, widget in original_widgets.items()
    )
    view.close()


def test_header_hit_testing_returns_track(qapp) -> None:
    dataset = Dataset(
        "dataset-header-hit",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0]),
    )
    view = TabletView()
    view.set_layout_model(TabletLayout([TrackDefinition("curve", "Curve", TrackKind.CURVE)]))
    view.set_dataset(dataset)
    qapp.processEvents()

    hit = view.hit_test_header("curve", 10.0, 5.0)
    assert hit is not None
    assert hit.target.kind.value == "track"
    assert hit.target.object_id == "curve"
    assert view.hit_test_header("curve", 10.0, 10_000.0) is None
    view.close()


def test_curve_hit_testing_selects_nearest_curve(qapp) -> None:
    dataset = Dataset(
        "dataset-curve-hit",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 150.0, 200.0]),
    )
    dataset.curves["curve-tg"] = CurveData(
        CurveMetadata("curve-tg", "TG", "TG", "%", None, dataset.dataset_id),
        np.array([1.0, 2.0, 3.0]),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout([TrackDefinition("gas", "Gas", TrackKind.GAS, curve_mnemonics=["TG"])])
    )
    view.resize(900, 600)
    view.show()
    view.set_dataset(dataset)
    qapp.processEvents()

    rendered = view._rendered["gas"]
    scene_point = rendered.plot.getViewBox().mapViewToScene(QPointF(0.5, 150.0))
    viewport_point = rendered.plot.viewport().mapFromGlobal(
        rendered.plot.mapToGlobal(rendered.plot.mapFromScene(scene_point))
    )
    hit = view.select_curve_at("gas", viewport_point.x(), viewport_point.y(), tolerance_px=12.0)
    assert hit is not None
    assert hit.target.object_id == "TG"
    assert view.selection_snapshot.primary == hit.target
    view.close()


def test_depth_track_uses_compact_resizable_ruler(qapp) -> None:
    dataset = Dataset(
        "dataset-depth-ruler",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.linspace(100.0, 500.0, 401),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout([TrackDefinition("depth", "Глубина", TrackKind.DEPTH, width=120)])
    )
    view.set_dataset(dataset)
    qapp.processEvents()

    widget = view._rendered["depth"].widget
    axis = widget.plot.getAxis("left")
    assert axis.labelText == ""
    assert "Глубина" in widget.title.text()

    widget.set_track_width(160)
    assert widget.width() == 160
    assert axis.width() <= 92
    view.close()


def test_tablet_tracks_fill_scroll_viewport_height(qapp) -> None:
    dataset = Dataset(
        "dataset-full-height",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.linspace(0.0, 1000.0, 1001),
    )
    curve = CurveData(
        CurveMetadata("curve-rop", "ROP", "ROP", "m/h", None, dataset.dataset_id),
        np.linspace(1.0, 20.0, 1001),
    )
    dataset.curves[curve.metadata.curve_id] = curve
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("depth", "Глубина", TrackKind.DEPTH),
                TrackDefinition("rop", "ROP", TrackKind.CURVE, curve_mnemonics=["ROP"]),
            ]
        )
    )
    view.resize(900, 700)
    view.show()
    view.set_dataset(dataset)
    qapp.processEvents()

    viewport_height = view._scroll.viewport().height()
    assert view._rendered["rop"].widget.minimumHeight() >= viewport_height
    assert view._rendered["depth"].widget.minimumHeight() >= viewport_height
    view.close()


def test_track_widget_leaves_plot_body_context_menu_to_tablet_router(qapp) -> None:
    widget = TabletTrackWidget(TrackDefinition("curve", "Curve", TrackKind.CURVE))
    requested: list[str] = []
    widget.context_requested.connect(lambda track_id, _pos: requested.append(track_id))
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(10.0, 10.0),
        QPointF(10.0, 10.0),
        QPointF(10.0, 10.0),
        Qt.MouseButton.RightButton,
        Qt.MouseButton.RightButton,
        Qt.KeyboardModifier.NoModifier,
    )

    assert widget.eventFilter(widget.plot.viewport(), event) is False
    assert requested == []
    widget.close()


def test_depth_span_presets_apply_to_all_tracks_and_keep_top_depth(qapp) -> None:
    depth = np.linspace(100.0, 300.0, 201)
    dataset = Dataset(
        "dataset-depth-span",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    curve = CurveData(
        CurveMetadata(
            "curve-rop",
            "ROP",
            "ROP",
            "m/h",
            "Rate of penetration",
            dataset.dataset_id,
        ),
        np.linspace(0.0, 100.0, depth.size),
    )
    dataset.curves = {curve.metadata.curve_id: curve}
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120),
                TrackDefinition(
                    "rop",
                    "ROP",
                    TrackKind.CURVE,
                    curve_mnemonics=["ROP"],
                ),
            ]
        )
    )
    view.set_dataset(dataset)
    view.set_visible_depth(150.0, 250.0)
    qapp.processEvents()

    preset_row = next(
        row for row in range(view._span_combo.count()) if view._span_combo.itemData(row) == 20.0
    )
    view._depth_span_selected(preset_row)
    qapp.processEvents()

    assert view.visible_depth_range == pytest.approx((150.0, 170.0))
    assert view._span_combo.currentText() == "20 м"
    assert all(
        rendered.plot.viewRange()[1] == pytest.approx([150.0, 170.0])
        for rendered in view._rendered.values()
        if rendered.plot is not None
    )
    view.close()


def test_many_curve_headers_remain_named_and_generic_title_is_readable(qapp) -> None:
    depth = np.linspace(0.0, 100.0, 101)
    dataset = Dataset(
        "dataset-many-curves",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    mnemonics = [f"S{index}" for index in range(1, 10)]
    dataset.curves = {
        f"curve-{mnemonic}": CurveData(
            CurveMetadata(
                f"curve-{mnemonic}",
                mnemonic,
                mnemonic,
                "u",
                f"Parameter {index}",
                dataset.dataset_id,
            ),
            np.linspace(float(index), float(index + 1), depth.size),
        )
        for index, mnemonic in enumerate(mnemonics, start=1)
    }
    track = TrackDefinition(
        "many",
        " / ".join(mnemonics),
        TrackKind.CURVE,
        curve_mnemonics=mnemonics,
        width=360,
    )
    view = TabletView()
    view.set_layout_model(TabletLayout([track]))
    view.set_dataset(dataset)
    qapp.processEvents()

    rendered = view._rendered["many"]
    assert rendered.widget.title.text() == "Параметры (9)"
    assert len(rendered.widget._curve_header_labels) == 9
    assert all(label.text().strip() for label in rendered.widget._curve_header_labels.values())
    assert rendered.widget.curve_header_scroll.maximumHeight() == 320
    view.close()


def test_masterlog_tracks_reserve_one_header_band_and_align_plot_viewports(qapp) -> None:
    depth = np.linspace(95.0, 150.0, 111)
    dataset = Dataset(
        "dataset-masterlog-header-alignment",
        "Masterlog",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    curves: dict[str, CurveData] = {}
    for index, mnemonic in enumerate(("WOB", "ROP", "DMC"), start=1):
        curve = CurveData(
            CurveMetadata(
                f"curve-{mnemonic}",
                mnemonic,
                mnemonic,
                "u",
                mnemonic,
                dataset.dataset_id,
            ),
            np.linspace(float(index), float(index + 1), depth.size),
        )
        curves[curve.metadata.curve_id] = curve
    dataset.curves = curves

    view = TabletView()
    view.resize(1200, 820)
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120),
                TrackDefinition("strat", "Stratigraphy", TrackKind.STRATIGRAPHY, width=150),
                TrackDefinition(
                    "drilling",
                    "Drilling",
                    TrackKind.CURVE,
                    curve_mnemonics=["WOB", "ROP", "DMC"],
                    width=360,
                ),
                TrackDefinition("cuttings", "Cuttings", TrackKind.CUTTINGS, width=220),
                TrackDefinition("lba", "LBA", TrackKind.LBA, width=180),
            ]
        )
    )
    view.set_dataset(dataset)
    view.show()
    qapp.processEvents()

    assert view._rendered["drilling"].widget.natural_curve_header_height == 144
    assert {
        rendered.widget.curve_header_scroll.height() for rendered in view._rendered.values()
    } == {144}

    viewport_tops = {
        rendered.plot.viewport().mapToGlobal(QPoint(0, 0)).y()
        for rendered in view._rendered.values()
        if rendered.plot is not None
    }
    viewport_heights = {
        rendered.plot.viewport().height()
        for rendered in view._rendered.values()
        if rendered.plot is not None
    }
    assert len(viewport_tops) == 1
    assert len(viewport_heights) == 1
    assert all(
        rendered.plot.viewRange()[1] == pytest.approx([95.0, 145.0])
        for rendered in view._rendered.values()
        if rendered.plot is not None
    )
    view.close()


def test_layout_switch_preserves_depth_scale_and_scroll_position(qapp) -> None:
    depth = np.linspace(100.0, 300.0, 201)
    dataset = Dataset(
        "dataset-preserve-span",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    view = TabletView()
    first_layout = TabletLayout([TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120)])
    view.set_layout_model(first_layout)
    view.set_dataset(dataset)
    view.set_visible_depth(150.0, 160.0)
    qapp.processEvents()

    second_layout = TabletLayout(
        [
            TrackDefinition("depth-2", "Depth", TrackKind.DEPTH, width=120),
            TrackDefinition("curve-2", "Curve", TrackKind.CURVE),
        ]
    )
    view.set_layout_model(second_layout)
    qapp.processEvents()

    assert view.visible_depth_range == pytest.approx((150.0, 160.0))
    assert second_layout.visible_depth_top == pytest.approx(150.0)
    assert second_layout.visible_depth_bottom == pytest.approx(160.0)
    view.close()


def test_wheel_over_curve_header_scrolls_all_tracks(qapp) -> None:
    depth = np.linspace(100.0, 300.0, 201)
    dataset = Dataset(
        "dataset-header-wheel",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    curve = CurveData(
        CurveMetadata(
            "curve-rop-header",
            "ROP",
            "ROP",
            "m/h",
            "Rate of penetration",
            dataset.dataset_id,
        ),
        np.linspace(0.0, 100.0, depth.size),
    )
    dataset.curves[curve.metadata.curve_id] = curve
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120),
                TrackDefinition(
                    "rop",
                    "ROP",
                    TrackKind.CURVE,
                    curve_mnemonics=["ROP"],
                ),
            ]
        )
    )
    view.resize(900, 700)
    view.show()
    view.set_dataset(dataset)
    view.set_visible_depth(150.0, 170.0)
    qapp.processEvents()
    header = view._rendered["rop"].widget._curve_header_labels["ROP"]
    wheel = QWheelEvent(
        QPointF(10.0, 10.0),
        QPointF(10.0, 10.0),
        QPoint(),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )

    qapp.sendEvent(header, wheel)
    qapp.processEvents()

    assert view.visible_depth_range == pytest.approx((152.0, 172.0))
    assert view.track_depth_range("depth") == pytest.approx((152.0, 172.0))
    assert view.track_depth_range("rop") == pytest.approx((152.0, 172.0))
    view.close()


def test_depth_span_change_is_stored_in_layout_model(qapp) -> None:
    depth = np.linspace(0.0, 500.0, 501)
    dataset = Dataset(
        "dataset-store-span",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    layout = TabletLayout([TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120)])
    view = TabletView()
    view.set_layout_model(layout)
    view.set_dataset(dataset)

    assert view.set_vertical_span(30.0, top=100.0)
    qapp.processEvents()

    assert layout.visible_depth_top == pytest.approx(100.0)
    assert layout.visible_depth_bottom == pytest.approx(130.0)
    view.close()


def _depth_span_test_view() -> TabletView:
    depth = np.linspace(100.0, 300.0, 201)
    dataset = Dataset(
        "dataset-depth-span-live",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    curve = CurveData(
        CurveMetadata(
            "curve-depth-span-live",
            "ROP",
            "ROP",
            "m/h",
            "Rate of penetration",
            dataset.dataset_id,
        ),
        np.linspace(0.0, 100.0, depth.size),
    )
    dataset.curves = {curve.metadata.curve_id: curve}
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120),
                TrackDefinition(
                    "rop",
                    "ROP",
                    TrackKind.CURVE,
                    curve_mnemonics=["ROP"],
                ),
            ]
        )
    )
    view.resize(1000, 700)
    view.show()
    view.set_dataset(dataset)
    view.set_visible_depth(100.0, 200.0)
    return view


def test_depth_span_presets_include_one_and_five_metres(qapp) -> None:
    view = TabletView()

    values = tuple(
        float(view._span_combo.itemData(row))
        for row in range(view._span_combo.count())
        if view._span_combo.itemData(row) is not None
    )

    assert 1.0 in values
    assert 5.0 in values
    assert 10.0 in values
    assert 50.0 in values
    assert 100.0 in values
    view.close()


def test_new_depth_form_opens_with_fifty_metre_default(qapp) -> None:
    view = _depth_span_test_view()
    # The helper explicitly changes the range to 100-200 for interaction tests,
    # so create a fresh empty layout to verify the real first-open behaviour.
    view.close()

    depth = np.linspace(100.0, 300.0, 201)
    dataset = Dataset(
        "dataset-default-depth-span",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    fresh = TabletView()
    fresh.set_layout_model(
        TabletLayout([TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120)])
    )
    fresh.set_dataset(dataset)
    qapp.processEvents()

    assert fresh.visible_depth_range == pytest.approx((100.0, 150.0))
    assert fresh._span_combo.currentData() == pytest.approx(50.0)
    fresh.close()


def test_selecting_depth_span_changes_graph_without_activated_signal(qapp) -> None:
    view = _depth_span_test_view()
    qapp.processEvents()
    row = view._span_combo.findData(50.0)

    # setCurrentIndex emits currentIndexChanged but not the user-only activated
    # signal. This reproduces the editable-combo path that previously left the
    # graph at 100-200 while the field displayed 50.
    view._span_combo.setCurrentIndex(row)
    qapp.processEvents()

    assert view.visible_depth_range == pytest.approx((100.0, 150.0))
    assert view.layout_model.visible_depth_top == pytest.approx(100.0)
    assert view.layout_model.visible_depth_bottom == pytest.approx(150.0)
    assert all(
        rendered.plot.viewRange()[1] == pytest.approx([100.0, 150.0])
        for rendered in view._rendered.values()
        if rendered.plot is not None
    )
    view.close()


def test_typed_depth_span_applies_immediately_without_enter(qapp) -> None:
    view = _depth_span_test_view()
    qapp.processEvents()
    editor = view._span_combo.lineEdit()
    assert editor is not None
    editor.setFocus()
    editor.selectAll()

    QTest.keyClicks(editor, "30")
    QTest.qWait(220)
    qapp.processEvents()

    assert view.visible_depth_range == pytest.approx((100.0, 130.0))
    assert all(
        rendered.plot.viewRange()[1] == pytest.approx([100.0, 130.0])
        for rendered in view._rendered.values()
        if rendered.plot is not None
    )
    view.close()


def test_depth_span_survives_tablet_resize(qapp) -> None:
    view = _depth_span_test_view()
    qapp.processEvents()
    assert view.set_vertical_span(5.0, top=120.0)
    qapp.processEvents()

    view.resize(1350, 900)
    qapp.processEvents()

    assert view.visible_depth_range == pytest.approx((120.0, 125.0))
    assert all(
        rendered.plot.viewRange()[1] == pytest.approx([120.0, 125.0])
        for rendered in view._rendered.values()
        if rendered.plot is not None
    )
    view.close()


def test_calcimetry_track_renders_las_curves_and_preserves_zero_and_null_gap(qapp) -> None:
    dataset = Dataset(
        "dataset-calc",
        "Calcimetry",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0, 102.0, 103.0]),
    )
    curve = CurveData(
        CurveMetadata(
            "curve-calcite",
            "CACO3",
            "CACO3",
            "%",
            "Кальцит",
            dataset.dataset_id,
        ),
        np.array([25.0, 0.0, np.nan, 50.0]),
    )
    dataset.curves[curve.metadata.curve_id] = curve
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition(
                    "calc",
                    "Кальциметрия",
                    TrackKind.CALCIMETRY,
                    curve_mnemonics=["CACO3"],
                    width=260,
                    curve_styles={"CACO3": CurveStyle("#06b6d4", 2.0)},
                )
            ]
        )
    )
    view.set_dataset(dataset)

    item = view._rendered["calc"].curve_items["CACO3"]
    x_values, y_values = item.getData()

    np.testing.assert_allclose(y_values, [100.0, 101.0, 102.0, 103.0])
    np.testing.assert_allclose(x_values, [25.0, 0.0, np.nan, 50.0], equal_nan=True)
    assert item.opts["connect"] == "finite"


def test_stratigraphy_drag_emits_snapped_interval(qapp) -> None:
    dataset = Dataset(
        "dataset-strat",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 105.0, 110.0, 115.0]),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout([TrackDefinition("strat", "Stratigraphy", TrackKind.STRATIGRAPHY, width=220)])
    )
    view.set_dataset(dataset)
    emitted: list[tuple[float, float]] = []
    view.stratigraphy_interval_requested.connect(lambda top, bottom: emitted.append((top, bottom)))

    assert view.begin_stratigraphy_drag("strat", 101.0) is True
    assert view.update_stratigraphy_drag(114.0) is True
    assert view.finish_stratigraphy_drag(114.0) is True

    assert emitted == [(100.0, 115.0)]
    view.close()


def test_stratigraphy_track_renders_project_intervals(qapp) -> None:
    dataset = Dataset(
        "dataset-strat-render",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 150.0, 200.0]),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout([TrackDefinition("strat", "Возраст", TrackKind.STRATIGRAPHY, width=220)])
    )
    interval = StratigraphyInterval(
        "s1", 100.0, 200.0, "K", "Меловая", "System / Period", "#7fc64e", None
    )
    view.set_stratigraphy([interval])
    view.set_dataset(dataset)

    rendered = view._rendered["strat"].stratigraphy_items
    assert rendered is not None and "s1" in rendered
    assert view.stratigraphy_interval_at_depth(150.0) is interval
    view.close()


def test_tablet_curve_pencil_is_visible_and_emits_edit_request(qapp) -> None:
    dataset = Dataset(
        "dataset-pencil",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0, 102.0, 103.0]),
    )
    curve = CurveData(
        CurveMetadata(
            "curve-pencil",
            "ROP",
            "ROP",
            "m/h",
            None,
            dataset.dataset_id,
            provenance="las:source",
        ),
        np.array([1.0, 2.0, 3.0, 4.0]),
    )
    dataset.curves[curve.metadata.curve_id] = curve
    view = TabletView()
    view.resize(900, 650)
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition(
                    "drilling",
                    "Бурение",
                    TrackKind.CURVE,
                    curve_mnemonics=["ROP"],
                    curve_display={
                        "ROP": CurveDisplaySettings("Скорость бурения", XScale.LINEAR, 0.0, 10.0)
                    },
                )
            ]
        )
    )
    emitted: list[tuple[object, ...]] = []
    view.curve_edit_requested.connect(lambda *args: emitted.append(args))
    view.set_dataset(dataset)
    view.show()
    qapp.processEvents()

    assert view.curve_pencil_controls_visible is True
    assert view._curve_pencil_selector.count() == 1
    assert view.set_curve_pencil_mode(True) is True
    assert view.curve_pencil_target == ("drilling", "ROP")

    plot = view._rendered["drilling"].plot
    assert plot is not None
    viewport = plot.viewport()
    first = plot.mapFromScene(plot.getViewBox().mapViewToScene(QPointF(0.2, 100.2)))
    second = plot.mapFromScene(plot.getViewBox().mapViewToScene(QPointF(0.8, 102.8)))
    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=first)
    QTest.mouseMove(viewport, second)
    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=second)
    qapp.processEvents()

    assert len(emitted) == 1
    assert emitted[0][0] == curve.metadata.curve_id
    assert len(emitted[0][1]) >= 2
    assert len(emitted[0][1]) == len(emitted[0][2])
    view.close()


def test_tablet_curve_pencil_excludes_derived_curves(qapp) -> None:
    dataset = Dataset(
        "dataset-derived-pencil",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0, 102.0]),
    )
    curve = CurveData(
        CurveMetadata(
            "curve-derived",
            "D_EXP",
            "D_EXP",
            None,
            None,
            dataset.dataset_id,
            provenance="calculation:dexp",
        ),
        np.array([1.0, 1.1, 1.2]),
    )
    dataset.curves[curve.metadata.curve_id] = curve
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition(
                    "dexp",
                    "D-экспонента",
                    TrackKind.CURVE,
                    curve_mnemonics=["D_EXP"],
                )
            ]
        )
    )
    view.set_dataset(dataset)
    qapp.processEvents()

    assert view._curve_pencil_selector.count() == 0
    assert view.set_curve_pencil_mode(True) is False
    view.close()


def test_tablet_curve_pencil_handles_descending_axis_and_log_scale(qapp) -> None:
    dataset = Dataset(
        "dataset-pencil-desc",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([103.0, 102.0, 101.0, 100.0]),
    )
    curve = CurveData(
        CurveMetadata(
            "curve-pencil-desc",
            "GR",
            "GR",
            "API",
            None,
            dataset.dataset_id,
            provenance="las:source",
        ),
        np.array([10.0, 10.0, 10.0, 10.0]),
    )
    dataset.curves[curve.metadata.curve_id] = curve
    definition = TrackDefinition(
        "gamma",
        "ГК",
        TrackKind.CURVE,
        curve_mnemonics=["GR"],
        curve_display={"GR": CurveDisplaySettings("ГК", XScale.LOGARITHMIC, 1.0, 100.0)},
    )
    view = TabletView()
    view.set_layout_model(TabletLayout([definition]))
    emitted: list[tuple[object, ...]] = []
    view.curve_edit_requested.connect(lambda *args: emitted.append(args))
    view.set_dataset(dataset)
    qapp.processEvents()

    assert view.set_curve_pencil_mode(True) is True
    assert view._curve_pencil_source_value(definition, "GR", 0.5) == pytest.approx(10.0)
    calcimetry = TrackDefinition(
        "calc-pencil",
        "Кальциметрия",
        TrackKind.CALCIMETRY,
        curve_mnemonics=["GR"],
    )
    assert view._curve_pencil_source_value(calcimetry, "GR", 125.0) == 100.0
    view._curve_pencil_points = [
        view._curve_pencil_point_from_values(102.8, 2.0),
        view._curve_pencil_point_from_values(100.2, 50.0),
    ]
    assert view._commit_curve_pencil_gesture() is True
    assert len(emitted) == 1
    assert list(emitted[0][1]) == [1, 2]
    assert np.all(np.isfinite(emitted[0][2]))
    view.close()


def test_tablet_headers_translate_legacy_vendor_s_codes(qapp) -> None:
    dataset = Dataset(
        "legacy-vendor",
        "Legacy vendor",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0]),
    )
    curves = []
    for mnemonic, unit in (
        ("S300", "атм"),
        ("S720", "м3"),
        ("S800", "°C"),
        ("S900", "°C"),
        ("S50", "мин-1"),
    ):
        curve = CurveData(
            CurveMetadata(
                f"curve-{mnemonic}",
                mnemonic,
                mnemonic,
                unit,
                None,
                dataset.dataset_id,
            ),
            np.array([1.0, 2.0]),
        )
        dataset.curves[curve.metadata.curve_id] = curve
        curves.append(mnemonic)
    track = TrackDefinition(
        "technology",
        "Параметры бурения",
        TrackKind.CURVE,
        curve_mnemonics=curves,
        curve_display={
            mnemonic: CurveDisplaySettings(display_name=mnemonic)
            for mnemonic in curves
        },
    )
    view = TabletView()
    view.set_layout_model(TabletLayout([track]))
    view.set_dataset(dataset)
    qapp.processEvents()

    assert view.legend_labels("technology") == (
        "Давление на манифольде",
        "Суммарный объем в емкостях",
        "Температура на входе",
        "Температура раствора на выходе",
        "Число ходов 1 насоса",
    )
    view.close()


def test_tablet_curve_pencil_connect_points_mode_commits_selected_points(qapp) -> None:
    dataset = Dataset(
        "dataset-pencil-points",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0, 102.0, 103.0]),
    )
    curve = CurveData(
        CurveMetadata(
            "curve-pencil-points",
            "ROP",
            "ROP",
            "m/h",
            None,
            dataset.dataset_id,
            provenance="las:source",
        ),
        np.array([1.0, 2.0, 3.0, 4.0]),
    )
    dataset.curves[curve.metadata.curve_id] = curve
    view = TabletView()
    view.resize(900, 650)
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition(
                    "drilling-points",
                    "Бурение",
                    TrackKind.CURVE,
                    curve_mnemonics=["ROP"],
                    curve_display={
                        "ROP": CurveDisplaySettings(
                            "Скорость бурения", XScale.LINEAR, 0.0, 10.0
                        )
                    },
                )
            ]
        )
    )
    emitted: list[tuple[object, ...]] = []

    def apply_edit(*args: object) -> None:
        emitted.append(args)
        view.acknowledge_curve_pencil_commit(True)

    view.curve_edit_requested.connect(apply_edit)
    view.set_dataset(dataset)
    view.show()
    qapp.processEvents()
    mode_row = view._curve_pencil_mode_selector.findData("connect_points")
    view._curve_pencil_mode_selector.setCurrentIndex(mode_row)
    assert view.set_curve_pencil_mode(True) is True

    plot = view._rendered["drilling-points"].plot
    assert plot is not None
    viewport = plot.viewport()
    first = plot.mapFromScene(plot.getViewBox().mapViewToScene(QPointF(0.2, 100.2)))
    second = plot.mapFromScene(plot.getViewBox().mapViewToScene(QPointF(0.8, 102.8)))
    QTest.mouseClick(viewport, Qt.MouseButton.LeftButton, pos=first)
    QTest.mouseClick(viewport, Qt.MouseButton.LeftButton, pos=second)
    qapp.processEvents()

    assert len(view._curve_pencil_points) == 2
    assert view._curve_pencil_apply_button.isEnabled() is True
    view._curve_pencil_apply_button.click()
    qapp.processEvents()

    assert len(emitted) == 1
    assert emitted[0][0] == curve.metadata.curve_id
    assert view._curve_pencil_points == []
    view.close()


def test_tablet_curve_pencil_failed_commit_keeps_preview(qapp) -> None:
    dataset = Dataset(
        "dataset-pencil-failed",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0, 102.0]),
    )
    curve = CurveData(
        CurveMetadata(
            "curve-pencil-failed",
            "ROP",
            "ROP",
            "m/h",
            None,
            dataset.dataset_id,
            provenance="las:source",
        ),
        np.array([1.0, 2.0, 3.0]),
    )
    dataset.curves[curve.metadata.curve_id] = curve
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition(
                    "failed-track",
                    "Бурение",
                    TrackKind.CURVE,
                    curve_mnemonics=["ROP"],
                    curve_display={
                        "ROP": CurveDisplaySettings("ROP", XScale.LINEAR, 0.0, 10.0)
                    },
                )
            ]
        )
    )
    view.set_dataset(dataset)
    view.set_curve_pencil_mode(True)
    view.curve_edit_requested.connect(
        lambda *_: view.acknowledge_curve_pencil_commit(False, "test failure")
    )
    view._curve_pencil_points = [
        view._curve_pencil_point_from_values(100.0, 2.0),
        view._curve_pencil_point_from_values(102.0, 8.0),
    ]
    view._update_curve_pencil_preview()

    assert view._commit_curve_pencil_gesture() is False
    assert len(view._curve_pencil_points) == 2
    assert view._rendered["failed-track"].curve_pencil_preview is not None
    assert "test failure" in view._curve_pencil_status.text()
    view.close()


def test_tablet_curve_pencil_keeps_visible_live_readout(qapp) -> None:
    dataset = Dataset(
        "dataset-pencil-readout",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0, 102.0]),
    )
    curve = CurveData(
        CurveMetadata(
            "curve-pencil-readout",
            "ROP",
            "ROP",
            "m/h",
            None,
            dataset.dataset_id,
            provenance="las:source",
        ),
        np.array([1.0, 2.0, 3.0]),
    )
    dataset.curves[curve.metadata.curve_id] = curve
    view = TabletView()
    view.resize(600, 600)
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition(
                    "readout-track",
                    "Бурение",
                    TrackKind.CURVE,
                    curve_mnemonics=["ROP"],
                    curve_display={
                        "ROP": CurveDisplaySettings("ROP", XScale.LINEAR, 0.0, 10.0)
                    },
                )
            ]
        )
    )
    view.set_dataset(dataset)
    view.show()
    qapp.processEvents()
    assert view.set_curve_pencil_mode(True) is True
    rendered = view._rendered["readout-track"]
    viewport = rendered.plot.viewport()
    position = QPointF(viewport.width() * 0.5, viewport.height() * 0.5)
    event = QMouseEvent(
        QEvent.Type.MouseMove,
        position,
        position,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )

    view._update_curve_pencil_hover(rendered.plot, event, "readout-track")

    assert rendered.curve_pencil_readout is not None
    assert rendered.curve_pencil_readout.isVisible()
    assert "ROP" in rendered.curve_pencil_readout.text()
    assert "Новое" in rendered.curve_pencil_readout.text()
    assert "Было" in rendered.curve_pencil_readout.text()
    view.close()


def test_tablet_view_renders_rich_annotation_only_on_bound_track(qapp) -> None:
    from geoworkbench.project.annotation_schema import (
        AnnotationKind,
        AnnotationStyle,
        annotation_properties,
    )

    dataset = Dataset(
        "dataset-rich-annotation",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 150.0, 200.0]),
    )
    dataset.upsert_curve("ROP", np.array([10.0, 20.0, 30.0]))
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("depth", "Глубина", TrackKind.DEPTH),
                TrackDefinition(
                    "drilling", "Бурение", TrackKind.CURVE, curve_mnemonics=["ROP"]
                ),
            ]
        )
    )
    style = AnnotationStyle(fill_color="#fff7ed", border_color="#ea580c")
    view.set_canvas_objects(
        [
            CanvasObject(
                "annotation-1",
                "annotation",
                "curve",
                0.5,
                150.0,
                220.0,
                76.0,
                top_depth=150.0,
                bottom_depth=150.0,
                parameter_mnemonic="ROP",
                track_id="drilling",
                properties=annotation_properties(
                    kind=AnnotationKind.CALLOUT,
                    text="Рейс №7",
                    axis_value=None,
                    axis_id=None,
                    parameter_value=20.0,
                    unit="m/h",
                    offset_x=18.0,
                    offset_y=-36.0,
                    style=style,
                    asset_ref=None,
                    visible=True,
                    locked=False,
                    print_enabled=True,
                ),
            )
        ]
    )

    view.set_dataset(dataset)
    qapp.processEvents()

    assert view.rendered_annotation_ids("depth") == ()
    assert view.rendered_annotation_ids("drilling") == ("annotation-1",)
    view.set_annotation_print_mode(True)
    item = view.rendered_annotation_item("annotation-1")
    assert item is not None
    assert item.isVisible() is True
    view.close()
