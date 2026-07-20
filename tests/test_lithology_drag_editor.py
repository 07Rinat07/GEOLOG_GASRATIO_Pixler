from __future__ import annotations

import numpy as np
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.lithotype_catalog_controller import CatalogLithotype
from geoworkbench.services.localization import AppLanguage
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView
from geoworkbench.ui.lithology_interval_dialog import LithologyIntervalDialog


def _catalog() -> tuple[CatalogLithotype, ...]:
    return (
        CatalogLithotype(
            "sandstone",
            "SS",
            "Песчаник",
            "Sandstone",
            "sedimentary",
            "#e7cf8b",
            "dots",
            True,
            "Құмтас",
        ),
        CatalogLithotype(
            "clay",
            "CL",
            "Глина",
            "Clay",
            "sedimentary",
            "#94a3b8",
            "horizontal",
            True,
            "Саз",
        ),
    )


def _view(qapp) -> TabletView:
    dataset = Dataset(
        "dataset-lithology-drag",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.arange(100.0, 181.0, 10.0),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout([TrackDefinition("lithology", "Литология", TrackKind.LITHOLOGY)])
    )
    view.set_lithology([], _catalog())
    view.resize(520, 620)
    view.show()
    view.set_dataset(dataset)
    qapp.processEvents()
    return view


def test_quick_lithology_dialog_contains_one_noneditable_rock_selector(qapp) -> None:
    dialog = LithologyIntervalDialog(
        110.0,
        120.0,
        _catalog(),
        language=AppLanguage.RU,
    )

    assert dialog.windowTitle() == "Новый литологический интервал"
    assert dialog.top_depth == 110.0
    assert dialog.bottom_depth == 120.0
    assert dialog.lithotype_input.isEditable() is False
    assert dialog.lithotype_input.count() == 2
    assert dialog.lithotype_id == "sandstone"
    dialog.lithotype_input.setCurrentIndex(1)
    assert dialog.lithotype_id == "clay"
    dialog.close()


def test_lithology_drag_snaps_interval_and_emits_request(qapp) -> None:
    view = _view(qapp)
    requests: list[tuple[float, float]] = []
    view.lithology_interval_requested.connect(
        lambda top, bottom: requests.append((top, bottom))
    )

    assert view.begin_lithology_drag("lithology", 108.0)
    assert view.update_lithology_drag(172.0)
    assert view.lithology_preview_range == (110.0, 170.0)
    assert view._rendered["lithology"].lithology_preview is not None
    assert view.finish_lithology_drag(172.0)

    assert requests == [(110.0, 170.0)]
    assert view.lithology_preview_range is None
    assert view._rendered["lithology"].lithology_preview is None
    view.close()


def _mouse_event(
    event_type: QEvent.Type,
    viewport,
    position: QPointF,
    *,
    button: Qt.MouseButton,
    buttons: Qt.MouseButton,
    modifiers: Qt.KeyboardModifier,
) -> QMouseEvent:
    global_position = QPointF(viewport.mapToGlobal(position.toPoint()))
    return QMouseEvent(
        event_type,
        position,
        position,
        global_position,
        button,
        buttons,
        modifiers,
    )


def _viewport_point_for_depth(view: TabletView, depth: float) -> QPointF:
    plot = view._rendered["lithology"].plot
    assert plot is not None
    scene = plot.getViewBox().mapViewToScene(QPointF(0.5, depth))
    plot_position = plot.mapFromScene(scene)
    return QPointF(plot.viewport().mapFrom(plot, plot_position))


def test_shift_left_mouse_drag_in_lithology_track_opens_range_request(qapp) -> None:
    view = _view(qapp)
    rendered = view._rendered["lithology"]
    assert rendered.plot is not None
    viewport = rendered.plot.viewport()
    requests: list[tuple[float, float]] = []
    view.lithology_interval_requested.connect(
        lambda top, bottom: requests.append((top, bottom))
    )
    start = _viewport_point_for_depth(view, 110.0)
    finish = _viewport_point_for_depth(view, 140.0)

    press = _mouse_event(
        QEvent.Type.MouseButtonPress,
        viewport,
        start,
        button=Qt.MouseButton.LeftButton,
        buttons=Qt.MouseButton.LeftButton,
        modifiers=Qt.KeyboardModifier.ShiftModifier,
    )
    move = _mouse_event(
        QEvent.Type.MouseMove,
        viewport,
        finish,
        button=Qt.MouseButton.NoButton,
        buttons=Qt.MouseButton.LeftButton,
        modifiers=Qt.KeyboardModifier.ShiftModifier,
    )
    release = _mouse_event(
        QEvent.Type.MouseButtonRelease,
        viewport,
        finish,
        button=Qt.MouseButton.LeftButton,
        buttons=Qt.MouseButton.NoButton,
        modifiers=Qt.KeyboardModifier.ShiftModifier,
    )

    assert view.eventFilter(viewport, press) is True
    assert view.eventFilter(viewport, move) is True
    assert view.eventFilter(viewport, release) is True
    assert requests == [(110.0, 140.0)]
    view.close()
