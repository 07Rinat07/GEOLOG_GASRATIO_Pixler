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

    committed = view.commit_draw_points(
        [DrawPoint(100.0, 10.0), DrawPoint(102.0, 30.0)]
    )
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
    view.show_dataset(dataset)

    assert view.can_edit is False
    assert view.set_edit_mode(True) is False
    assert view.commit_draw_points([DrawPoint(100.0, 1.0), DrawPoint(101.0, 2.0)]) is False
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
