import numpy as np
from PySide6.QtWidgets import QMessageBox

from geoworkbench.domain.models import (
    CanvasObject,
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
    LithologyInterval,
    Project,
    Well,
)
from geoworkbench.project.curve_editing_controller import CurveEditingController
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
    curve = CurveData(
        CurveMetadata("curve-1", "ROP", "ROP", "m/h", None, dataset.dataset_id),
        np.array([1.0, 2.0]),
    )
    dataset.curves[curve.metadata.curve_id] = curve
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
    window.curve_editing_controller = CurveEditingController(session)
    window._update_curve_edit_actions()


def test_open_las_stops_when_import_mode_is_cancelled(qapp, monkeypatch) -> None:
    window = MainWindow()
    file_dialog_called = False

    monkeypatch.setattr(
        "geoworkbench.ui.main_window.QInputDialog.getItem",
        lambda *args, **kwargs: ("", False),
    )

    def unexpected_file_dialog(*args, **kwargs):
        nonlocal file_dialog_called
        file_dialog_called = True
        return ([], "")

    monkeypatch.setattr(
        "geoworkbench.ui.main_window.QFileDialog.getOpenFileNames",
        unexpected_file_dialog,
    )

    window.open_las()

    assert not file_dialog_called
    window.close()


def test_window_restores_saved_layout(qapp) -> None:
    window = MainWindow()
    assert not window.windowIcon().isNull()
    session, layout = make_session()
    bind_session(window, session)

    window._show_current_dataset()
    qapp.processEvents()

    assert window.tablet_view.layout_model is layout
    assert set(window.tablet_view.rendered_track_ids) == {"depth", "curve"}
    window.close()


def test_about_dialog_contains_logo(qapp, monkeypatch) -> None:
    window = MainWindow()
    captured: list[QMessageBox] = []

    def capture(dialog: QMessageBox) -> int:
        captured.append(dialog)
        return 0

    monkeypatch.setattr(QMessageBox, "exec", capture)

    window.show_about()

    assert len(captured) == 1
    assert not captured[0].iconPixmap().isNull()
    assert "Сармулдин Ринат" in captured[0].text()
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


def test_window_persists_width_requested_by_track_widget(qapp) -> None:
    window = MainWindow()
    session, layout = make_session()
    bind_session(window, session)
    window._show_current_dataset()
    session.dirty = False

    window.tablet_view.track_width_change_requested.emit("curve", 340)
    qapp.processEvents()

    assert layout.track_by_id("curve").width == 340
    assert session.dirty is True
    assert window.windowTitle().endswith(" *")
    window.close()


def test_window_applies_track_settings_from_inspector(qapp) -> None:
    window = MainWindow()
    session, layout = make_session()
    bind_session(window, session)
    window._show_current_dataset()
    session.dirty = False

    window._apply_inspector_track_settings("curve", 420, "linear", -10.0, 10.0)
    qapp.processEvents()

    track = layout.track_by_id("curve")
    assert track.width == 420
    assert track.x_min == -10.0
    assert track.x_max == 10.0
    assert session.dirty is True
    window.close()


def test_window_applies_curve_edit_and_updates_undo_redo_actions(qapp) -> None:
    window = MainWindow()
    session, _ = make_session()
    bind_session(window, session)
    dataset = session.current_dataset
    assert dataset is not None
    curve = dataset.curves["curve-1"]

    window._apply_curve_draw_edit("curve-1", np.array([0]), np.array([10.0]))
    qapp.processEvents()

    assert curve.values[0] == 10.0
    assert window.undo_action.isEnabled() is True
    assert window.redo_action.isEnabled() is False

    window.undo_curve_edit()
    assert curve.values[0] == 1.0
    assert window.redo_action.isEnabled() is True

    window.redo_curve_edit()
    assert curve.values[0] == 10.0
    window.close()


def test_project_tree_contains_geology_annotations_templates_and_tracks(qapp) -> None:
    window = MainWindow()
    session, _ = make_session()
    well = session.current_well
    assert well is not None
    well.lithology.append(LithologyInterval("layer", 100.0, 101.0, "sandstone", None))
    well.canvas_objects.append(
        CanvasObject(
            "note",
            "depth_annotation",
            "depth",
            0.0,
            100.5,
            1.0,
            0.0,
            top_depth=100.5,
            properties={"text": "Контакт"},
        )
    )
    session.project.description_templates["Песчаник"] = "Описание"
    bind_session(window, session)

    window._refresh_tree()

    labels: list[str] = []
    iterator = window.tree.invisibleRootItem()

    def collect(item) -> None:
        labels.append(item.text(0))
        for index in range(item.childCount()):
            collect(item.child(index))

    collect(iterator)
    assert any(label.startswith("Литология (1)") for label in labels)
    assert any(label.startswith("Глубинные заметки (1)") for label in labels)
    assert any(label.startswith("Шаблоны описаний (1)") for label in labels)
    assert any(label.startswith("Слои планшета (2)") for label in labels)
    window.close()


def test_project_tree_track_activation_selects_inspector_track(qapp) -> None:
    window = MainWindow()
    session, _ = make_session()
    bind_session(window, session)
    window._refresh_tree()

    track_item = None
    iterator = window.tree.invisibleRootItem()
    pending = [iterator]
    while pending:
        item = pending.pop()
        data = item.data(0, 256)
        if data and data[0] == "track" and data[-1] == "curve":
            track_item = item
            break
        pending.extend(item.child(index) for index in range(item.childCount()))

    assert track_item is not None
    window._activate_tree_item(track_item)

    assert window._selected_track_id == "curve"
    assert "Curve" in window.inspector._summary.text()
    window.close()
