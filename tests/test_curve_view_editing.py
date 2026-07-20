import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.services.curve_editing import DrawPoint
from geoworkbench.services.dataset_selection import DatasetIntervalSelection
from geoworkbench.services.localization import AppLanguage
from geoworkbench.visualization.curve_view import CurveView


def make_dataset() -> tuple[Dataset, CurveData]:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0, 102.0, 103.0]),
    )
    curve = CurveData(
        CurveMetadata("curve-1", "ROP", "ROP", "m/h", None, dataset.dataset_id),
        np.array([1.0, 2.0, 3.0, 4.0]),
    )
    dataset.curves[curve.metadata.curve_id] = curve
    return dataset, curve


def test_curve_view_converts_draw_points_to_edit_request(qapp) -> None:
    dataset, curve = make_dataset()
    view = CurveView()
    emitted: list[tuple[str, object, object]] = []
    view.edit_requested.connect(
        lambda curve_id, indices, values: emitted.append((curve_id, indices, values))
    )
    view.show_dataset(dataset, ["ROP"])
    assert view.set_edit_mode(True) is True

    committed = view.commit_draw_points([DrawPoint(100.0, 10.0), DrawPoint(102.0, 30.0)])
    qapp.processEvents()

    assert committed is True
    assert emitted[0][0] == curve.metadata.curve_id
    np.testing.assert_array_equal(emitted[0][1], [0, 1, 2])
    np.testing.assert_allclose(emitted[0][2], [10.0, 20.0, 30.0])
    view.close()


def test_curve_view_requires_single_curve_and_edit_mode(qapp) -> None:
    dataset, _ = make_dataset()
    second = CurveData(
        CurveMetadata("curve-2", "C1", "C1", "%", None, dataset.dataset_id),
        np.array([1.0, 2.0, 3.0, 4.0]),
    )
    dataset.curves[second.metadata.curve_id] = second
    view = CurveView()
    view.show_dataset(dataset, ["ROP", "C1"])

    assert view.can_edit is False
    assert view.set_edit_mode(True) is False
    assert view.commit_draw_points([DrawPoint(100.0, 1.0), DrawPoint(101.0, 2.0)]) is False
    view.close()


def test_curve_view_prefers_compatible_gas_curves_and_distinct_colors(qapp) -> None:
    dataset, _ = make_dataset()
    dataset.curves = {
        "lith": CurveData(
            CurveMetadata("lith", "LITH_CODE", "LITH_CODE", None, None, dataset.dataset_id),
            np.array([39.0, 39.0, 60.0, 60.0]),
        ),
        "c1": CurveData(
            CurveMetadata("c1", "C1", "C1", "%", None, dataset.dataset_id),
            np.array([0.1, 0.2, 0.3, 0.4]),
        ),
        "c2": CurveData(
            CurveMetadata("c2", "C2", "C2", "%", None, dataset.dataset_id),
            np.array([0.01, 0.02, 0.03, 0.04]),
        ),
        "tgas": CurveData(
            CurveMetadata("tgas", "TGAS", "TGAS", "%", None, dataset.dataset_id),
            np.array([0.2, 0.4, 0.6, 0.8]),
        ),
    }
    view = CurveView()

    view.show_dataset(dataset)

    assert view.displayed_mnemonics == ("TGAS", "C1", "C2")
    assert "LITH_CODE" not in view.displayed_mnemonics
    colors = {item.opts["pen"].color().name() for item in view._curve_items.values()}
    assert len(colors) == 3
    assert view._plot.getAxis("left").autoSIPrefix is False
    view.close()


def test_curve_view_mouse_drag_emits_edit_request(qapp) -> None:
    dataset, _ = make_dataset()
    view = CurveView()
    emitted: list[tuple[object, ...]] = []
    view.edit_requested.connect(lambda *args: emitted.append(args))
    view.resize(700, 500)
    view.show()
    view.show_dataset(dataset, ["ROP"])
    view.set_edit_mode(True)
    qapp.processEvents()
    plot = view.findChild(pg.PlotWidget)
    assert plot is not None
    viewport = plot.viewport()
    first = plot.mapFromScene(plot.getViewBox().mapViewToScene(QPointF(1.5, 100.2)))
    second = plot.mapFromScene(plot.getViewBox().mapViewToScene(QPointF(3.5, 102.8)))

    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=first)
    QTest.mouseMove(viewport, second)
    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=second)
    qapp.processEvents()

    assert len(emitted) == 1
    assert emitted[0][0] == "curve-1"
    assert len(emitted[0][1]) >= 1
    view.close()


def test_curve_view_region_and_shared_selection_stay_synchronized(qapp) -> None:
    dataset, _ = make_dataset()
    selection = DatasetIntervalSelection()
    view = CurveView(selection)
    view.show_dataset(dataset)

    selection.select(dataset, 101.0, 102.0)
    assert view._selection_region is not None
    assert view._selection_region.getRegion() == (101.0, 102.0)

    view._selection_region.setRegion((100.0, 101.0))
    view._selection_region.sigRegionChangeFinished.emit(view._selection_region)
    assert selection.interval == (100.0, 101.0)
    view.close()


def test_curve_view_cursor_snaps_to_sample_and_shows_visible_values(qapp) -> None:
    dataset, _ = make_dataset()
    dataset.curves["curve-2"] = CurveData(
        CurveMetadata("curve-2", "C1", "C1", "%", None, dataset.dataset_id),
        np.array([10.0, 20.0, np.nan, 40.0]),
    )
    view = CurveView(language=AppLanguage.EN)
    view.show_dataset(dataset, ["ROP", "C1"])

    assert view.show_cursor_at_depth(101.6, 2.5)

    assert view.cursor_text == "Depth: 102 m  |  ROP: 3 m/h  |  C1: — %"
    assert view._cursor_horizontal is not None
    assert view._cursor_horizontal.value() == 102.0
    assert view._cursor_horizontal.isVisible()
    assert view._cursor_vertical is not None
    assert view._cursor_vertical.value() == 2.5
    view._hide_cursor()
    assert view.cursor_text == "Move the pointer over the plot to inspect values"
    assert not view._cursor_horizontal.isVisible()
    view.close()


def test_curve_view_cursor_requires_dataset_and_finite_depth(qapp) -> None:
    view = CurveView()
    assert not view.show_cursor_at_depth(100.0)
    dataset, _ = make_dataset()
    view.show_dataset(dataset)
    assert not view.show_cursor_at_depth(np.nan)
    view.close()


def test_curve_view_accepts_dataset_without_curves(qapp) -> None:
    dataset, _ = make_dataset()
    dataset.curves.clear()
    view = CurveView()

    view.show_dataset(dataset)

    assert view._curve_items == {}
    assert "показано кривых — 0" in view.title_text
    view.close()


def test_curve_view_limits_screen_points_but_preserves_peak(qapp) -> None:
    depth = np.arange(100_000, dtype=np.float64)
    dataset = Dataset("large", "Large", DatasetKind.GTI, DepthDomain.MD, depth)
    values = np.zeros_like(depth)
    values[54_321] = 1234.0
    curve = CurveData(
        CurveMetadata("curve", "TG", "TG", "%", None, dataset.dataset_id),
        values,
    )
    dataset.curves[curve.metadata.curve_id] = curve
    view = CurveView()

    view.show_dataset(dataset, ["TG"])

    items = view._plot.listDataItems()
    assert len(items) == 1
    plotted_values, plotted_depth = items[0].getData()
    assert plotted_values is not None and plotted_depth is not None
    assert plotted_depth.size <= 5000
    assert np.max(plotted_values) == 1234.0
    assert 54_321.0 in plotted_depth
    assert dataset.curves["curve"].values.size == 100_000
    view.close()


def test_curve_view_restores_full_detail_for_visible_depth_range(qapp) -> None:
    depth = np.arange(100_000, dtype=np.float64)
    dataset = Dataset("large", "Large", DatasetKind.GTI, DepthDomain.MD, depth)
    values = np.sin(depth / 10.0)
    curve = CurveData(
        CurveMetadata("curve", "TG", "TG", "%", None, dataset.dataset_id),
        values,
    )
    dataset.curves[curve.metadata.curve_id] = curve
    view = CurveView()
    view.show_dataset(dataset, ["TG"])

    view._plot.setYRange(50_000.0, 50_250.0, padding=0)
    qapp.processEvents()

    plotted_values, plotted_depth = view._curve_items["curve"].getData()
    assert plotted_values is not None and plotted_depth is not None
    np.testing.assert_array_equal(plotted_depth, depth[50_000:50_251])
    np.testing.assert_allclose(plotted_values, values[50_000:50_251])
    assert dataset.curves["curve"].values.size == 100_000
    view.close()
