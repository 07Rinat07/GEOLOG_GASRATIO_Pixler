import numpy as np
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView


def _mouse_event(
    event_type: QEvent.Type,
    viewport,
    position: QPointF,
    *,
    button: Qt.MouseButton,
    buttons: Qt.MouseButton,
) -> QMouseEvent:
    global_position = QPointF(viewport.mapToGlobal(position.toPoint()))
    return QMouseEvent(
        event_type,
        position,
        position,
        global_position,
        button,
        buttons,
        Qt.KeyboardModifier.ShiftModifier,
    )


def _viewport_point_for_axis(view: TabletView, track_id: str, value: float) -> QPointF:
    plot = view._rendered[track_id].plot
    assert plot is not None
    scene = plot.getViewBox().mapViewToScene(QPointF(0.5, value))
    plot_position = plot.mapFromScene(scene)
    return QPointF(plot.viewport().mapFrom(plot, plot_position))


def test_tablet_interval_analysis_emits_all_visible_parameters(qapp) -> None:
    dataset = Dataset(
        "dataset-analysis",
        "Analysis",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 110.0, 120.0, 130.0]),
    )
    dataset.upsert_curve("ROP", np.array([1.0, 2.0, 3.0, 4.0]), unit="m/h")
    dataset.upsert_curve("TG", np.array([10.0, 20.0, 30.0, 40.0]), unit="%")
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition(
                    "drilling", "Drilling", TrackKind.CURVE, curve_mnemonics=["ROP"]
                ),
                TrackDefinition("gas", "Gas", TrackKind.GAS, curve_mnemonics=["TG"]),
            ]
        )
    )
    view.set_dataset(dataset)
    qapp.processEvents()
    requests: list[dict[str, object]] = []
    view.interval_analysis_requested.connect(requests.append)

    assert view.begin_interval_analysis("drilling", 108.0)
    assert view.update_interval_analysis(123.0)
    assert view.interval_analysis_range == (110.0, 120.0)
    assert all(
        rendered.analysis_region is not None and rendered.analysis_region.isVisible()
        for rendered in view._rendered.values()
    )
    assert view.finish_interval_analysis(123.0)

    assert len(requests) == 1
    assert requests[0]["top"] == 110.0
    assert requests[0]["bottom"] == 120.0
    assert requests[0]["mnemonics"] == ("ROP", "TG")
    view.close()


def test_shift_left_drag_dispatches_interval_analysis(qapp) -> None:
    dataset = Dataset(
        "dataset-shift-analysis",
        "Analysis",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 110.0, 120.0, 130.0]),
    )
    dataset.upsert_curve("ROP", np.array([1.0, 2.0, 3.0, 4.0]), unit="m/h")
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [TrackDefinition("curve", "Curve", TrackKind.CURVE, curve_mnemonics=["ROP"])]
        )
    )
    view.resize(520, 620)
    view.show()
    view.set_dataset(dataset)
    qapp.processEvents()
    rendered = view._rendered["curve"]
    assert rendered.plot is not None
    viewport = rendered.plot.viewport()
    requests: list[dict[str, object]] = []
    view.interval_analysis_requested.connect(requests.append)
    start = _viewport_point_for_axis(view, "curve", 110.0)
    finish = _viewport_point_for_axis(view, "curve", 120.0)

    assert view.eventFilter(
        viewport,
        _mouse_event(
            QEvent.Type.MouseButtonPress,
            viewport,
            start,
            button=Qt.MouseButton.LeftButton,
            buttons=Qt.MouseButton.LeftButton,
        ),
    )
    assert view.eventFilter(
        viewport,
        _mouse_event(
            QEvent.Type.MouseMove,
            viewport,
            finish,
            button=Qt.MouseButton.NoButton,
            buttons=Qt.MouseButton.LeftButton,
        ),
    )
    assert view.eventFilter(
        viewport,
        _mouse_event(
            QEvent.Type.MouseButtonRelease,
            viewport,
            finish,
            button=Qt.MouseButton.LeftButton,
            buttons=Qt.MouseButton.NoButton,
        ),
    )

    assert requests[0]["top"] == 110.0
    assert requests[0]["bottom"] == 120.0
    view.close()


def test_geological_shift_gestures_keep_their_existing_role(qapp) -> None:
    dataset = Dataset(
        "dataset-geology",
        "Geology",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 110.0, 120.0]),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout([TrackDefinition("lithology", "Lithology", TrackKind.LITHOLOGY)])
    )
    view.set_dataset(dataset)
    qapp.processEvents()

    assert view.begin_interval_analysis("lithology", 100.0) is False
    assert view.begin_lithology_drag("lithology", 100.0) is True
    view.cancel_lithology_interaction()
    view.close()
