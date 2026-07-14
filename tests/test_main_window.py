import numpy as np

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, Project, Well
from geoworkbench.project.session import ProjectSession
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind, XScale
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
    layout = TabletLayout(
        [
            TrackDefinition("depth", "Глубина", TrackKind.DEPTH, width=120),
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


def test_window_restores_saved_layout(qapp) -> None:
    window = MainWindow()
    session, layout = make_session()
    bind_session(window, session)

    window._show_current_dataset()
    qapp.processEvents()

    assert window.tablet_view.layout_model is layout
    assert set(window.tablet_view.rendered_track_ids) == {"depth", "curve"}
    window.close()


def test_hide_track_command_updates_model_and_view(qapp) -> None:
    window = MainWindow()
    session, layout = make_session()
    bind_session(window, session)
    window._show_current_dataset()
    session.dirty = False
    window._selected_track_id = "curve"

    window.hide_selected_track()
    qapp.processEvents()

    assert layout.track_by_id("curve").visible is False
    assert set(window.tablet_view.rendered_track_ids) == {"depth"}
    assert session.dirty is True
    assert window.windowTitle().endswith(" *")
    window.close()


def test_window_clears_views_for_project_without_datasets(qapp) -> None:
    window = MainWindow()
    bind_session(window, ProjectSession(project=Project("empty", "Empty")))

    window._show_current_dataset()
    qapp.processEvents()

    assert window.tablet_view.layout_model.tracks == []
    assert window.tablet_view.rendered_track_ids == ()
    assert window.curve_view.title_text == "Откройте LAS-файл"
    window.close()


def test_window_applies_selected_track_x_scale(qapp) -> None:
    window = MainWindow()
    session, layout = make_session()
    bind_session(window, session)
    window._show_current_dataset()
    window._selected_track_id = "curve"

    window.set_selected_track_x_scale(XScale.LOGARITHMIC)
    qapp.processEvents()

    assert layout.track_by_id("curve").x_scale is XScale.LOGARITHMIC
    assert session.dirty is True
    window.close()
