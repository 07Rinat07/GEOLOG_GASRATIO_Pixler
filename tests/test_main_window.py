from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog, QLabel, QMessageBox

from geoworkbench.data.las_import_policy import LasImportMode
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
from geoworkbench.project.curve_transfer_controller import CurveTransferController
from geoworkbench.project.dataset_merge_controller import DatasetMergeController
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.print_job import PrintJobSettings, PrintOutputFormat
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.report_passport import passport_sidecar_path
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind, XScale
from geoworkbench.tablet.models import CurveLineStyle
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
    window._bind_project_session()


def test_print_report_channels_follow_selected_tablet_columns(qapp) -> None:
    session, _layout = make_session()
    dataset = session.current_dataset
    assert dataset is not None
    layout = session.current_tablet_layout
    assert layout is not None
    dataset.curves["curve-temp"] = CurveData(
        CurveMetadata(
            "curve-temp",
            "MUD_TEMP",
            "MUD_TEMP",
            "degC",
            None,
            dataset.dataset_id,
        ),
        np.array([20.0, 21.0]),
    )
    layout.tracks[1].curve_mnemonics = ["ROP"]
    layout.tracks.append(
        TrackDefinition(
            "temperature",
            "Temperature",
            TrackKind.CURVE,
            curve_mnemonics=["MUD_TEMP"],
        )
    )
    window = MainWindow()
    bind_session(window, session)
    job = PrintJobSettings(
        output_format=PrintOutputFormat.PRINTER,
        included_track_ids=("temperature",),
    )

    assert window._print_report_curve_ids(window.tablet_view, dataset, job) == (
        "curve-temp",
    )
    assert window._print_report_channel_mnemonics(
        window.tablet_view, dataset, job
    ) == ("MUD_TEMP",)
    window.close()


def test_window_starts_on_clear_home_page(qapp) -> None:
    window = MainWindow(language=AppLanguage.EN)
    window.show()
    qapp.processEvents()

    assert window.central_stack.currentWidget() is window.home_page
    assert window.home_action.text() == "Home"
    assert not window.workspace_action.isEnabled()
    assert window.home_page.findChild(type(window.home_page.workspace_button), "homeImportButton")
    assert "No data" in window.home_page.workspace_value.text()
    assert window.home_page.content.width() == min(
        1120, window.home_page.scroll_area.viewport().width()
    )
    window.close()


def test_window_exposes_interpretation_report_workspace(qapp) -> None:
    window = MainWindow(language=AppLanguage.EN)

    tab_index = window.tabs.indexOf(window.interpretation_report_workspace)
    assert tab_index >= 0
    assert window.tabs.tabText(tab_index) == "Interpretation reports"
    assert "interpretation_calculation" in window._session_bindings.binding_names
    workspace_style = window.interpretation_report_workspace.styleSheet()
    assert "background: #f4f7fb" in workspace_style
    assert "QTextBrowser#hydrocarbon-interpretation-preview" in workspace_style
    report_mode = window.interpretation_report_workspace.report_mode
    assert [report_mode.itemData(index) for index in range(report_mode.count())] == [
        "well_text",
        "opus_text",
        "mixture_chart",
        "mixture_text",
    ]
    assert "OPUS C1-C5" in report_mode.itemText(1)
    assert "Gas mixture ramp" in report_mode.itemText(2)
    assert window.interpretation_report_workspace.rop_reference.value() == 50.0
    assert window.interpretation_report_workspace.bit_reference.value() == 10.0
    assert window.interpretation_report_workspace.flow_reference.value() == 500.0
    assert window.interpretation_report_workspace.gas_efficiency.value() == 1.0
    assert "actual ROP" in window.interpretation_report_workspace.calculation_inputs_help.text()
    assert "not the current diameter" in (
        window.interpretation_report_workspace.bit_reference.toolTip()
    )
    report_mode.setCurrentIndex(report_mode.findData("opus_text"))
    assert "10,000 ppm" in window.interpretation_report_workspace.calculation_inputs_help.text()
    assert "separate synchronous TotalGas" in (
        window.interpretation_report_workspace.calculation_inputs_help.text()
    )
    assert window.interpretation_report_workspace.total_gas_lod.isEnabled()
    assert window.interpretation_report_workspace.total_gas_lod.value() == 0.0
    assert "no hidden value" in (
        window.interpretation_report_workspace.total_gas_lod.toolTip()
    )
    assert not window.interpretation_report_workspace.rop_reference.isEnabled()
    window.close()


def test_home_and_workspace_navigation_is_explicit(qapp) -> None:
    window = MainWindow(language=AppLanguage.EN)
    session, _ = make_session()
    bind_session(window, session)

    window._show_current_dataset()
    assert window.central_stack.currentWidget() is window.tabs
    assert window.workspace_action.isEnabled()
    assert "Dataset" in window.home_page.workspace_value.text()

    window.home_action.trigger()
    assert window.central_stack.currentWidget() is window.home_page
    window.workspace_action.trigger()
    assert window.central_stack.currentWidget() is window.tabs
    window.close()


def test_advanced_las_import_stops_when_mode_is_cancelled(qapp, monkeypatch) -> None:
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

    window.open_las_advanced()

    assert not file_dialog_called
    window.close()


def test_regular_las_action_uses_compatible_mode_without_mode_prompt(
    qapp, monkeypatch
) -> None:
    window = MainWindow()
    opened: list[tuple[tuple[Path, ...], object]] = []

    def unexpected_mode_dialog(*args, **kwargs):
        raise AssertionError("Regular LAS import must not show a mode prompt")

    monkeypatch.setattr(
        "geoworkbench.ui.main_window.QInputDialog.getItem",
        unexpected_mode_dialog,
    )
    monkeypatch.setattr(
        "geoworkbench.ui.main_window.QFileDialog.getOpenFileNames",
        lambda *args, **kwargs: (["well.las"], ""),
    )
    window._open_las_files = (  # type: ignore[method-assign]
        lambda paths, mode: opened.append((paths, mode))
    )

    window.open_action.trigger()

    assert opened == [((Path("well.las"),), LasImportMode.COMPATIBLE)]
    window.close()


def test_universal_import_dispatches_selected_format(qapp, monkeypatch) -> None:
    window = MainWindow()
    called: list[Path] = []
    window.open_excel = lambda source=None: called.append(source)  # type: ignore[method-assign]
    monkeypatch.setattr(
        "geoworkbench.ui.main_window.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: ("sample.xlsx", ""),
    )

    window.open_data()

    assert called == [Path("sample.xlsx")]
    window.close()


def test_universal_import_stops_when_cancelled(qapp, monkeypatch) -> None:
    window = MainWindow()
    called: list[Path] = []
    window.open_las = lambda source=None: called.append(source)  # type: ignore[method-assign]
    monkeypatch.setattr(
        "geoworkbench.ui.main_window.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: ("", ""),
    )

    window.open_data()

    assert called == []
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


def test_window_builds_interval_statistics_panel_from_tablet_gesture(qapp) -> None:
    window = MainWindow(language=AppLanguage.EN)
    session, _ = make_session()
    bind_session(window, session)
    dataset = session.current_dataset
    assert dataset is not None
    axis_id = dataset.active_index_id
    assert axis_id is not None

    window._show_interval_analysis_from_gesture(
        {
            "top": 100.0,
            "bottom": 101.0,
            "axis_id": axis_id,
            "axis_label": "Depth",
            "axis_unit": "m",
            "axis_is_datetime": False,
            "mnemonics": ("ROP",),
        }
    )

    statistics = window.interval_statistics_panel.statistics
    assert len(statistics) == 1
    assert statistics[0].mnemonic == "ROP"
    assert statistics[0].minimum == 1.0
    assert statistics[0].maximum == 2.0
    assert statistics[0].mean == 1.5
    assert (
        window.interval_statistics_panel.table.item(0, 0).text() == "Rate of Penetration\nROP · m/h"
    )
    assert window.interval_statistics_panel.table.item(0, 1).text() == "1"
    assert window.interval_statistics_panel.table.item(0, 2).text() == "1.5"
    assert window.interval_statistics_panel.table.item(0, 3).text() == "2"
    assert window.dataset_selection.interval == (100.0, 101.0)
    assert not window.interval_statistics_dock.isHidden()
    window.close()


def test_window_opens_localized_interpretation_report(qapp, monkeypatch) -> None:
    window = MainWindow(language=AppLanguage.EN)
    session, _ = make_session()
    bind_session(window, session)
    opened: list[str] = []
    monkeypatch.setattr(
        "geoworkbench.ui.main_window.InterpretationReportDialog.exec",
        lambda self: opened.append(self.report.well_name) or QDialog.DialogCode.Accepted,
    )

    window.show_interpretation_report()

    assert window.interpretation_report_action.text() == "Full geological report..."
    assert opened == ["Well"]
    window.close()


def test_about_dialog_contains_author_details(qapp, monkeypatch) -> None:
    window = MainWindow()
    captured: list[QDialog] = []

    def capture(dialog: QDialog) -> int:
        captured.append(dialog)
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(QDialog, "exec", capture)

    window.show_about()

    assert len(captured) == 1
    labels = captured[0].findChildren(QLabel)
    texts = [label.text() for label in labels]
    assert "GEOLOG GASRATIO@Pixler" in texts
    assert any(text.startswith("Версия ") for text in texts)
    assert "Rinat Sarmuldin" in texts
    assert "ura07srr@gmail.com" in texts
    assert any("Профессиональная среда" in text for text in texts)
    logo_label = captured[0].findChild(QLabel, "aboutProgramLogo")
    assert logo_label is not None
    assert logo_label.pixmap() is not None
    assert not logo_label.pixmap().isNull()
    email_label = next(label for label in labels if label.text() == "ura07srr@gmail.com")
    assert not email_label.openExternalLinks()
    assert email_label.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse
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


def test_window_applies_curve_style_from_inspector(qapp) -> None:
    window = MainWindow()
    session, layout = make_session()
    layout.track_by_id("curve").curve_mnemonics = ["ROP"]
    bind_session(window, session)
    window._show_current_dataset()
    session.dirty = False

    window._apply_inspector_curve_style("curve", "ROP", "#445566", 2.5, "dash")

    style = layout.track_by_id("curve").curve_style("ROP")
    assert style is not None
    assert style.color == "#445566"
    assert style.width == 2.5
    assert style.line_style is CurveLineStyle.DASH
    assert session.dirty is True
    window.close()


def test_window_applies_grid_from_inspector(qapp) -> None:
    window = MainWindow()
    session, layout = make_session()
    bind_session(window, session)
    window._show_current_dataset()
    session.dirty = False

    window._apply_inspector_grid("curve", False, True, 0.55)

    track = layout.track_by_id("curve")
    assert (track.grid_x, track.grid_y, track.grid_alpha) == (False, True, 0.55)
    assert session.dirty is True
    window.close()


def test_window_applies_x_axis_label_from_inspector(qapp) -> None:
    window = MainWindow()
    session, layout = make_session()
    bind_session(window, session)
    window._show_current_dataset()
    session.dirty = False

    window._apply_inspector_x_axis_label("curve", "ROP, m/h")

    assert layout.track_by_id("curve").x_axis_label == "ROP, m/h"
    assert session.dirty is True
    window.close()


def test_window_applies_selected_tablet_preset(qapp, monkeypatch) -> None:
    window = MainWindow()
    session, layout = make_session()
    preset = TabletLayout([TrackDefinition("preset-depth", "Depth", TrackKind.DEPTH, width=180)])
    session.tablet_presets["Standard"] = preset
    bind_session(window, session)
    window._show_current_dataset()
    monkeypatch.setattr(
        QInputDialog,
        "getItem",
        lambda *args, **kwargs: ("Standard", True),
    )

    window.apply_tablet_preset()

    assert session.current_tablet_layout is not layout
    assert session.current_tablet_layout is not preset
    assert window.tablet_view.rendered_track_ids == ("preset-depth",)
    assert session.dirty is True
    window.close()


def test_window_exports_synchronized_selection_to_csv(qapp, tmp_path, monkeypatch) -> None:
    window = MainWindow()
    session, _ = make_session()
    bind_session(window, session)
    dataset = session.current_dataset
    assert dataset is not None
    window.dataset_selection.select(dataset, 100.0, 101.0, ("curve-1",))
    target = tmp_path / "selection.csv"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(target), "CSV (*.csv)"),
    )

    window.export_selected_csv()

    assert target.read_text(encoding="utf-8").splitlines() == [
        "DEPTH [m],ROP [m/h]",
        "100,1",
        "101,2",
    ]
    window.close()


def test_window_exports_active_curve_view_to_png(qapp, tmp_path, monkeypatch) -> None:
    window = MainWindow()
    session, _ = make_session()
    bind_session(window, session)
    window._show_current_dataset()
    window.resize(800, 600)
    window.show()
    window.tabs.setCurrentWidget(window.curve_view)
    qapp.processEvents()
    target = tmp_path / "curves.png"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(target), "PNG (*.png)"),
    )

    window.export_active_visualization("png")

    assert target.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert passport_sidecar_path(target).is_file()
    window.close()


def test_window_exports_active_tablet_to_pdf(qapp, tmp_path, monkeypatch) -> None:
    window = MainWindow()
    session, _ = make_session()
    bind_session(window, session)
    window._show_current_dataset()
    window.resize(800, 600)
    window.show()
    window.tabs.setCurrentWidget(window.tablet_view)
    qapp.processEvents()
    target = tmp_path / "tablet.pdf"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(target), "PDF (*.pdf)"),
    )

    window.export_active_visualization("pdf")

    assert target.read_bytes().startswith(b"%PDF-")
    assert passport_sidecar_path(target).is_file()
    window.close()


def test_preview_active_visualization_uses_current_tablet_interval(qapp, monkeypatch) -> None:
    window = MainWindow()
    session, _ = make_session()
    bind_session(window, session)
    window._show_current_dataset()
    window.tabs.setCurrentWidget(window.tablet_view)
    window.tablet_view.set_visible_depth(100.0, 101.0)
    captured: dict[str, object] = {}

    def capture_preview(
        widget,
        job,
        source_name,
        *,
        report_context,
        report_form=None,
    ) -> None:
        captured.update(
            widget=widget,
            job=job,
            source_name=source_name,
            report_context=report_context,
            report_form=report_form,
        )

    monkeypatch.setattr(window, "_preview_print_job", capture_preview)

    window.preview_active_visualization()

    assert captured["widget"] is window.tablet_view
    assert captured["report_context"].current_range == (100.0, 101.0)
    window.close()


def test_window_saves_and_applies_export_curve_profile(qapp, monkeypatch) -> None:
    window = MainWindow()
    session, _ = make_session()
    bind_session(window, session)
    dataset = session.current_dataset
    assert dataset is not None
    window.dataset_selection.select(dataset, 100.0, 101.0, ("curve-1",))
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *args, **kwargs: ("Drilling", True),
    )

    window.save_export_profile()

    profile = next(iter(session.project.export_profiles.values()))
    assert profile.name == "Drilling"
    assert profile.curve_mnemonics == ("ROP",)
    window.dataset_selection.clear()
    monkeypatch.setattr(
        QInputDialog,
        "getItem",
        lambda *args, **kwargs: ("Drilling", True),
    )
    window.apply_export_profile()

    assert window.dataset_selection.interval == (100.0, 101.0)
    assert window.dataset_selection.curve_ids == ("curve-1",)
    window.close()


def test_window_exports_current_dataset_to_json(qapp, tmp_path, monkeypatch) -> None:
    window = MainWindow()
    session, _ = make_session()
    bind_session(window, session)
    target = tmp_path / "dataset.json"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(target), "JSON (*.json)"),
    )

    window.export_current_json()

    payload = target.read_text(encoding="utf-8")
    assert '"dataset_id": "dataset-1"' in payload
    assert '"original_mnemonic": "ROP"' in payload
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


def test_window_creates_and_undoes_resampled_copy(qapp, monkeypatch) -> None:
    window = MainWindow(language=AppLanguage.EN)
    session, _ = make_session()
    bind_session(window, session)
    window.depth_axis_controller.session = session
    monkeypatch.setattr(
        "geoworkbench.ui.main_window.DepthResampleDialog.exec",
        lambda self: QDialog.DialogCode.Accepted,
    )
    monkeypatch.setattr(
        "geoworkbench.ui.main_window.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

    window.create_resampled_depth_copy()

    well = session.current_well
    assert well is not None
    assert len(well.datasets) == 2
    assert session.current_dataset_id != "dataset-1"
    assert window.undo_resample_action.isEnabled()
    window.undo_depth_resample()
    assert set(well.datasets) == {"dataset-1"}
    assert session.current_dataset_id == "dataset-1"
    assert window.redo_resample_action.isEnabled()
    window.close()


def test_window_creates_and_undoes_ascending_depth_copy(qapp, monkeypatch) -> None:
    window = MainWindow(language=AppLanguage.EN)
    session, _ = make_session()
    source = session.current_dataset
    assert source is not None
    source.depth[:] = [101.0, 100.0]
    source.active_index.values[:] = source.depth
    bind_session(window, session)
    window.depth_axis_controller.session = session
    monkeypatch.setattr(
        "geoworkbench.ui.main_window.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

    window.create_ascending_depth_copy()

    well = session.current_well
    assert well is not None
    assert len(well.datasets) == 2
    assert window.undo_normalize_depth_action.isEnabled()
    window.undo_ascending_depth_copy()
    assert set(well.datasets) == {"dataset-1"}
    assert session.current_dataset is source
    assert window.redo_normalize_depth_action.isEnabled()
    window.redo_ascending_depth_copy()
    assert len(well.datasets) == 2
    assert window.undo_normalize_depth_action.isEnabled()
    window.close()


def test_window_creates_new_las_dataset(qapp, monkeypatch) -> None:
    window = MainWindow(language=AppLanguage.EN)

    def accept_small_grid(dialog) -> QDialog.DialogCode:
        dialog.stop_input.setValue(1.0)
        dialog.step_input.setValue(0.5)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr("geoworkbench.ui.main_window.NewLasDialog.exec", accept_small_grid)

    window.create_new_las()

    dataset = window.session.current_dataset
    assert dataset is not None
    assert dataset.name == "New LAS"
    np.testing.assert_allclose(dataset.depth, [0.0, 0.5, 1.0])
    assert window.session.dirty is True
    window.close()


def test_window_inserts_curves_and_updates_transfer_history_actions(qapp, monkeypatch) -> None:
    window = MainWindow(language=AppLanguage.EN)
    session, layout = make_session()
    target = session.current_dataset
    well = session.current_well
    assert target is not None and well is not None
    layout.tracks[1].curve_mnemonics = ["GR"]
    source = Dataset("source", "Source GIS", DatasetKind.GIS, DepthDomain.MD, target.depth.copy())
    source.curves["gr"] = CurveData(
        CurveMetadata("gr", "GAMMA", "GR", "API", None, source.dataset_id),
        np.array([10.0, 20.0]),
    )
    well.datasets[source.dataset_id] = source
    bind_session(window, session)
    window._show_current_dataset()
    window.curve_transfer_controller = CurveTransferController(session)
    rendered_widgets = {
        track_id: rendered.widget
        for track_id, rendered in window.tablet_view._rendered.items()
    }
    monkeypatch.setattr(
        "geoworkbench.ui.main_window.CurveTransferDialog.exec",
        lambda self: QDialog.DialogCode.Accepted,
    )

    window.show_curve_transfer()

    transferred = target.curve_by_mnemonic("GR")
    assert transferred is not None
    assert window.undo_transfer_action.isEnabled()
    rendered = window.tablet_view._rendered["curve"]
    assert "GR" in (rendered.curve_items or {})
    assert "GR" in rendered.widget._curve_header_labels
    assert all(
        window.tablet_view._rendered[track_id].widget is widget
        for track_id, widget in rendered_widgets.items()
    )
    assert window.tablet_view.set_curve_pencil_mode(
        True, track_id="curve", mnemonic="GR"
    )
    window.undo_curve_transfer()
    assert target.curve_by_mnemonic("GR") is None
    assert "GR" not in (rendered.curve_items or {})
    assert "GR" not in rendered.widget._curve_header_labels
    assert "GR" not in (rendered.curve_render_keys or {})
    assert window.tablet_view.curve_pencil_enabled is False
    assert window.tablet_view.curve_pencil_target is None
    assert window.redo_transfer_action.isEnabled()
    assert all(
        window.tablet_view._rendered[track_id].widget is widget
        for track_id, widget in rendered_widgets.items()
    )
    window.redo_curve_transfer()
    assert target.curve_by_mnemonic("GR") is transferred
    assert "GR" in (rendered.curve_items or {})
    first_x, first_y = rendered.curve_items["GR"].getData()
    assert first_x is not None and len(first_x) == 2
    assert first_y is not None and len(first_y) == 2
    assert window.undo_transfer_action.isEnabled()
    assert all(
        window.tablet_view._rendered[track_id].widget is widget
        for track_id, widget in rendered_widgets.items()
    )
    # A second cycle catches stale render-key cache entries left by removal.
    window.undo_curve_transfer()
    window.redo_curve_transfer()
    second_x, second_y = rendered.curve_items["GR"].getData()
    assert second_x is not None and len(second_x) == 2
    assert second_y is not None and len(second_y) == 2
    window.close()


def test_daily_las_controller_follows_reopened_project_session(qapp) -> None:
    window = MainWindow(language=AppLanguage.EN)
    previous_session = window.daily_las_growth_controller.session
    session, _layout = make_session()

    bind_session(window, session)

    assert "daily_las_growth" in window._session_bindings.binding_names
    assert window.daily_las_growth_controller.session is session
    assert window.daily_las_growth_controller.session is not previous_session
    assert tuple(
        dataset.dataset_id
        for dataset in window.daily_las_growth_controller.datasets_for_current_well()
    ) == ("dataset-1",)
    window.close()


def test_window_merges_datasets_and_updates_history_actions(qapp, monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    window = MainWindow(language=AppLanguage.EN)
    session, _ = make_session()
    target = session.current_dataset
    well = session.current_well
    assert target is not None and well is not None
    source = Dataset(
        "source", "Source GIS", DatasetKind.GIS, DepthDomain.MD, np.array([99.0, 100.0])
    )
    source.curves["gr"] = CurveData(
        CurveMetadata("gr", "GR", "GR", "API", None, source.dataset_id),
        np.array([9.0, 10.0]),
    )
    well.datasets[source.dataset_id] = source
    bind_session(window, session)
    window.dataset_merge_controller = DatasetMergeController(session)
    monkeypatch.setattr(
        "geoworkbench.ui.main_window.DatasetMergeDialog.exec",
        lambda self: QDialog.DialogCode.Accepted,
    )

    window.show_dataset_merge()

    merged = session.current_dataset
    assert merged is not None and merged.dataset_id not in {"dataset-1", "source"}
    np.testing.assert_allclose(merged.depth, [99.0, 100.0, 101.0])
    assert window.undo_merge_action.isEnabled()
    window.undo_dataset_merge()
    assert session.current_dataset is target
    assert window.redo_merge_action.isEnabled()
    window.close()


def test_project_tree_contains_geology_templates_and_tracks_without_annotations(qapp) -> None:
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
    assert not any(label.startswith("Глубинные заметки") for label in labels)
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


def test_window_shows_las_curve_browser_for_current_dataset(qapp) -> None:
    window = MainWindow()
    session, _ = make_session()
    bind_session(window, session)

    window._show_current_dataset()
    qapp.processEvents()

    assert window.curve_browser.tree.topLevelItemCount() == 1
    assert window.curve_browser.selected_mnemonics() == ["ROP"]
    assert window.curve_browser_dock.isHidden()
    window.close()


def test_window_builds_tablet_from_curve_browser_selection(qapp) -> None:
    window = MainWindow()
    session, _ = make_session()
    bind_session(window, session)
    window._show_current_dataset()

    window._build_tablet_from_curve_selection(["ROP"])
    qapp.processEvents()

    layout = session.current_tablet_layout
    assert layout is not None
    curve_track = next(track for track in layout.tracks if track.kind is TrackKind.CURVE)
    assert curve_track.title == "ROP"
    assert curve_track.curve_mnemonics == ["ROP"]
    assert window.tabs.currentWidget() is window.tablet_view
    window.close()


def test_tablet_interval_handlers_create_resize_and_undo(qapp) -> None:
    from geoworkbench.tablet.interval_interaction import IntervalEditMode

    window = MainWindow()
    session, _layout = make_session()
    bind_session(window, session)
    window.interpretation_controller.session = session
    window._show_current_dataset()

    window.set_interval_interaction_mode(IntervalEditMode.CREATE)
    interpretation_id = window.interpretation_controller.selected_interpretation_id
    assert interpretation_id is not None
    assert any(
        track.kind is TrackKind.INTERPRETATION for track in session.current_tablet_layout.tracks
    )

    window._create_interval_from_tablet(interpretation_id, 100.0, 101.0, "Reservoir")
    interval = window.interpretation_controller.selected_interval()
    assert interval is not None
    assert interval.top_depth == 100.0
    assert interval.bottom_depth == 101.0
    assert window.undo_interpretation_action.isEnabled()

    window._resize_interval_from_tablet(interpretation_id, interval.interval_id, 100.0, 100.5)
    assert window.interpretation_controller.selected_interval().bottom_depth == 100.5

    window.undo_interpretation_edit()
    assert window.interpretation_controller.selected_interval().bottom_depth == 101.0
    window.set_interval_interaction_mode(IntervalEditMode.SELECT)
    window.tablet_view.clear()
    window.close()
    window.deleteLater()
    qapp.processEvents()


def test_pencil_action_edits_visible_curve_directly_in_tablet(qapp) -> None:
    window = MainWindow()
    session, layout = make_session()
    layout.track_by_id("curve").curve_mnemonics = ["ROP"]
    bind_session(window, session)
    window._show_current_dataset()
    window.tabs.setCurrentWidget(window.tablet_view)

    window.pencil_action.setChecked(True)
    qapp.processEvents()

    assert window.tabs.currentWidget() is window.tablet_view
    assert window.tablet_view.curve_pencil_enabled is True
    assert window.tablet_view.curve_pencil_target == ("curve", "ROP")
    assert window.pencil_button.defaultAction() is window.pencil_action
    window.close()


def test_curve_pencil_applies_in_memory_and_marks_project_dirty(qapp) -> None:
    window = MainWindow()
    session, layout = make_session()
    layout.track_by_id("curve").curve_mnemonics = ["ROP"]
    bind_session(window, session)
    window._show_current_dataset()
    window.tabs.setCurrentWidget(window.tablet_view)
    assert window._activate_tablet_curve_pencil("ROP", track_id="curve") is True

    window.tablet_view._curve_pencil_points = [
        window.tablet_view._curve_pencil_point_from_values(100.0, 5.0),
        window.tablet_view._curve_pencil_point_from_values(101.0, 7.0),
    ]
    assert window.tablet_view._commit_curve_pencil_gesture() is True

    curve = session.current_dataset.curve_by_mnemonic("ROP")
    assert curve is not None
    assert np.allclose(curve.values, [5.0, 7.0])
    assert session.dirty is True
    assert "Не сохранено" in window.tablet_view._curve_pencil_status.text()
    window.close()
