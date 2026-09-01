from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtWidgets import QFileDialog, QMessageBox

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, new_id
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.main_window import MainWindow
from geoworkbench.ui.session_safety import CloseChoice


def _finish_deferred_setup(qapp) -> None:
    for _ in range(5):
        qapp.processEvents()


def _dataset(source: Path, *, source_format: str = "GeoScape II GS2") -> Dataset:
    return Dataset(
        dataset_id=new_id(),
        name="Imported working data",
        kind=DatasetKind.USER,
        depth_domain=DepthDomain.MD,
        depth=np.asarray([1000.0, 1000.5, 1001.0], dtype=np.float64),
        source_path=source,
        parameters={
            "SOURCE_FORMAT": source_format,
            "SOURCE_FILE": str(source),
        },
    )


def test_session_panel_shows_active_project_well_dataset_and_source(qapp, tmp_path) -> None:
    window = MainWindow(language=AppLanguage.RU)
    window.show()
    _finish_deferred_setup(qapp)

    window.session.project.name = "Field interpretation project"
    dataset = _dataset(tmp_path / "geoscape_source.gs2")
    window.session.add_dataset(dataset, well_name="Well 494", create_new_well=True)

    controller = window._session_safety_controller
    controller.refresh()
    panel = window.session_info_panel

    assert "Field interpretation project" in panel.project_label.text()
    assert "Well 494" in panel.well_label.text()
    assert "Imported working data" in panel.dataset_label.text()
    assert "geoscape_source.gs2" in panel.source_label.text()
    assert panel.state_label.text() == "Изменено"
    assert "GeoScape II GS2" in panel.toolTip()
    assert "Строк: 3" in panel.toolTip()
    assert "Кривых: 0" in panel.toolTip()
    assert panel.workflow_label.objectName() == "sessionWorkflowLabel"
    assert panel.workflow_label.text() == (
        f"Источник: {dataset.source_path}  →  "
        "Файл проекта: не сохранён  →  "
        "Экспорт: отдельный LAS-файл"
    )

    window.session.dirty = False
    controller.refresh()
    assert panel.state_label.text() == "Сохранено"

    window.change_language(AppLanguage.EN)
    controller.refresh()
    assert panel.project_label.text().startswith("Project:")
    assert panel.state_label.text() == "Saved"
    assert panel.workflow_label.text() == (
        f"Source: {dataset.source_path}  →  "
        "Project file: not saved  →  "
        "Export: separate LAS file"
    )

    project_path = tmp_path / "projects" / "Well 494.geologpkg"
    window.project_controller.project_path = project_path
    controller.refresh()
    assert panel.workflow_label.text() == (
        f"Source: {dataset.source_path}  →  "
        f"Project file: {project_path}  →  "
        "Export: separate LAS file"
    )

    window.change_language(AppLanguage.RU)
    controller.refresh()
    assert panel.workflow_label.text() == (
        f"Источник: {dataset.source_path}  →  "
        f"Файл проекта: {project_path}  →  "
        "Экспорт: отдельный LAS-файл"
    )

    window.close()


def test_close_protection_handles_cancel_discard_and_project_save(
    qapp, tmp_path, monkeypatch
) -> None:
    window = MainWindow(language=AppLanguage.RU)
    window.show()
    _finish_deferred_setup(qapp)
    controller = window._session_safety_controller
    controller.prompt_enabled = True
    window.session.dirty = True

    monkeypatch.setattr(controller, "_ask_close_choice", lambda: CloseChoice.CANCEL)
    assert controller._handle_close_request() is False

    monkeypatch.setattr(controller, "_ask_close_choice", lambda: CloseChoice.DISCARD)
    assert controller._handle_close_request() is True

    saved_path = tmp_path / "session.geolog.json"
    window.project_controller.project_path = saved_path
    notified: list[Path] = []

    def save_project() -> None:
        window.session.dirty = False

    monkeypatch.setattr(window, "save_project", save_project)
    monkeypatch.setattr(controller, "_notify_saved_path", notified.append)
    monkeypatch.setattr(controller, "_ask_close_choice", lambda: CloseChoice.SAVE_PROJECT)
    window.session.dirty = True

    assert controller._handle_close_request() is True
    assert notified == [saved_path]
    window.close()


def test_las_close_export_always_asks_for_target_and_never_uses_source_implicitly(
    qapp, tmp_path, monkeypatch
) -> None:
    source = tmp_path / "original.las"
    source.write_text("~Version", encoding="utf-8")
    chosen = tmp_path / "operator_selected_name.las"

    window = MainWindow(language=AppLanguage.RU)
    window.show()
    _finish_deferred_setup(qapp)
    window.session.add_dataset(_dataset(source, source_format="LAS"), create_new_well=True)
    controller = window._session_safety_controller
    controller.prompt_enabled = True

    dialog_calls: list[tuple[str, str]] = []

    def choose_target(_parent, _title: str, initial: str, _filter: str):
        dialog_calls.append((initial, str(chosen)))
        return str(chosen), "LAS (*.las)"

    exported: list[Path] = []

    def export_to_path(target: Path) -> Path:
        exported.append(target)
        target.write_text("edited LAS", encoding="utf-8")
        return target

    monkeypatch.setattr(QFileDialog, "getSaveFileName", choose_target)
    monkeypatch.setattr(window, "_export_current_dataset_to_path", export_to_path)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

    assert controller._export_las_before_close() is True
    assert len(dialog_calls) == 1
    assert Path(dialog_calls[0][0]).name == "original_edited.las"
    assert exported == [chosen]
    assert source.read_text(encoding="utf-8") == "~Version"
    window.session.dirty = False
    window.close()


def test_successful_las_export_reports_exact_path(qapp, tmp_path, monkeypatch) -> None:
    exported_target = tmp_path / "chosen_by_operator.las"
    exported_target.write_text("LAS", encoding="utf-8")
    produced: list[Path] = []

    def fake_export(self, target: Path) -> Path:
        produced.append(target)
        return target

    monkeypatch.setattr(MainWindow, "_export_current_dataset_to_path", fake_export)
    window = MainWindow(language=AppLanguage.RU)
    window.show()
    _finish_deferred_setup(qapp)
    controller = window._session_safety_controller
    controller.prompt_enabled = True
    notified: list[Path] = []
    monkeypatch.setattr(controller, "_notify_saved_path", notified.append)

    result = window._export_current_dataset_to_path(exported_target)

    assert Path(result) == exported_target
    assert produced == [exported_target]
    assert notified == [exported_target]
    window.close()


def test_project_save_transition_reports_exact_project_path(qapp, tmp_path, monkeypatch) -> None:
    window = MainWindow(language=AppLanguage.RU)
    window.show()
    _finish_deferred_setup(qapp)
    controller = window._session_safety_controller
    controller.prompt_enabled = True
    saved_path = tmp_path / "operator_project.geolog.json"
    window.project_controller.project_path = saved_path
    notified: list[Path] = []
    monkeypatch.setattr(controller, "_notify_saved_path", notified.append)

    window.session.dirty = True
    controller.refresh()
    window.session.dirty = False
    controller.refresh()
    _finish_deferred_setup(qapp)

    assert notified == [saved_path]
    window.close()
