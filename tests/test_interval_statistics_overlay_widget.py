import numpy as np
from PySide6.QtCore import QPoint

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
    Project,
    Well,
)
from geoworkbench.project.curve_editing_controller import CurveEditingController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.ui.main_window import MainWindow


def make_session() -> tuple[ProjectSession, TabletLayout]:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0]),
    )
    well = Well("well-1", "Well", datasets={dataset.dataset_id: dataset})
    curve = CurveData(
        CurveMetadata("curve-1", "ROP", "ROP", "m/h", None, dataset.dataset_id),
        np.array([1.0, 2.0]),
    )
    dataset.curves[curve.metadata.curve_id] = curve
    layout = TabletLayout(
        [
            TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120),
            TrackDefinition("curve", "Curve", TrackKind.CURVE, width=240),
        ]
    )
    session = ProjectSession(
        project=Project("project-1", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=dataset.dataset_id,
        tablet_layouts={dataset.dataset_id: layout},
    )
    return session, layout


def bind_session(window: MainWindow, session: ProjectSession) -> None:
    window.project_controller.session = session
    window.tablet_controller.session = session
    window.dataset_export_controller.session = session
    window.depth_annotation_controller.session = session
    window.curve_editing_controller = CurveEditingController(session)
    window._update_curve_edit_actions()


def test_statistics_overlay_is_clipped_to_tab_workspace(qapp) -> None:
    window = MainWindow(language=AppLanguage.EN)
    session, _ = make_session()
    bind_session(window, session)
    window.resize(1100, 720)
    window.show()
    qapp.processEvents()

    dataset = session.current_dataset
    assert dataset is not None
    window._show_interval_analysis_from_gesture(
        {
            "top": 100.0,
            "bottom": 101.0,
            "axis_id": dataset.active_index_id,
            "axis_label": "Depth",
            "axis_unit": "m",
            "axis_is_datetime": False,
            "mnemonics": ("ROP",),
        }
    )
    qapp.processEvents()

    overlay = window.interval_statistics_dock
    assert overlay.parentWidget() is window.tablet_view
    assert overlay.x() >= 0
    assert overlay.y() >= 0
    assert overlay.geometry().right() <= window.tablet_view.rect().right()
    assert overlay.geometry().bottom() <= window.tablet_view.rect().bottom()
    window.close()


def test_user_moved_statistics_overlay_does_not_snap_back_on_resize(qapp) -> None:
    window = MainWindow()
    window.resize(1200, 800)
    window.show()
    qapp.processEvents()
    overlay = window.interval_statistics_dock
    overlay.show_preserving_position()
    overlay.move_constrained(QPoint(120, 90), user_move=True)
    qapp.processEvents()

    window.resize(1180, 780)
    window._adapt_interval_statistics_dock(force=True)
    qapp.processEvents()

    assert overlay.user_positioned
    assert overlay.x() == 120
    assert overlay.y() == 90
    window.close()


def test_close_button_path_clears_report_and_interval_selection(qapp) -> None:
    window = MainWindow(language=AppLanguage.EN)
    session, _ = make_session()
    bind_session(window, session)
    dataset = session.current_dataset
    assert dataset is not None
    window._show_interval_analysis_from_gesture(
        {
            "top": 100.0,
            "bottom": 101.0,
            "axis_id": dataset.active_index_id,
            "axis_label": "Depth",
            "axis_unit": "m",
            "axis_is_datetime": False,
            "mnemonics": ("ROP",),
        }
    )
    assert window.dataset_selection.interval == (100.0, 101.0)

    window.interval_statistics_dock.closeRequested.emit()
    qapp.processEvents()

    assert window.interval_statistics_panel.statistics == ()
    assert window.interval_statistics_dock.isHidden()
    assert window.dataset_selection.interval is None
    window.close()
