import numpy as np
import pyqtgraph as pg
import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent

from geoworkbench.domain.models import (
    CanvasObject,
    CurveData,
    CurveMetadata,
    CuttingsComponent,
    CuttingsSample,
    Dataset,
    DatasetKind,
    DepthDomain,
    LithologyInterval,
    StratigraphyInterval,
)
from geoworkbench.project.lithotype_catalog_controller import CatalogLithotype
from geoworkbench.tablet.models import (
    CurveLineStyle,
    CurveStyle,
    TabletLayout,
    TrackDefinition,
    TrackKind,
    XScale,
)
from geoworkbench.tablet.tablet_view import TabletTrackWidget, TabletView, curve_legend_label


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

    assert view.legend_labels("curves") == ("C1 [%]", "ROP")
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

    assert view.cursor_depth == 151.0
    assert all(item.cursor_line is not None for item in view._rendered.values())
    assert all(item.cursor_line.value() == 151.0 for item in view._rendered.values())
    assert view.cursor_summary(151.0) == "Глубина: 150 м | C1: 2 % | ROP: 20 m/h"
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
    assert "Шлам 100–110 м: Песчаник: 70%; Глина: 30%" in view.cursor_summary(105.0)
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

    assert calc_items is not None and len(calc_items["sample"]) == 3
    assert lba_items is not None and len(lba_items["sample"]) == 1
    assert ("Кальциметрия: CaCO₃ 65%; CaMg(CO₃)₂ 20%; нераств. остаток 15%") in summary
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
            grid_alpha=0.4,
        )
    )

    assert widget.plot.getAxis("bottom").grid == pytest.approx(102.0)
    assert widget.plot.getAxis("left").grid is False
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

    assert view.zoom_depth(0.5)
    assert view.visible_depth_range == pytest.approx((1055.0, 1165.0))
    assert view.scroll_depth(10.0)

    assert view.visible_depth_range == pytest.approx((1110.0, 1220.0))
    assert view.track_depth_range("depth") == pytest.approx((1110.0, 1220.0))
    assert view.track_depth_range("curve") == pytest.approx((1110.0, 1220.0))
    assert emitted == pytest.approx([(1055.0, 1165.0), (1110.0, 1220.0)])
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
    qapp.sendEvent(viewport, zoom_event)

    assert view.visible_depth_range == pytest.approx((1022.0, 1198.0))

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

    assert view.visible_depth_range == pytest.approx((1043.12, 1219.12))
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

    assert full_count == 5000
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


def test_tablet_view_renders_depth_annotations_on_every_track(qapp) -> None:
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

    assert view.rendered_annotation_ids("depth") == ("note-1",)
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
        TabletLayout([TrackDefinition("lithology", "Литология", TrackKind.LITHOLOGY)])
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
        TabletLayout([TrackDefinition("lithology", "Литология", TrackKind.LITHOLOGY)])
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
    assert "Интерпретация «Primary»: Fluid / Gas (120–160 м)" in view.cursor_summary(150.0)
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
