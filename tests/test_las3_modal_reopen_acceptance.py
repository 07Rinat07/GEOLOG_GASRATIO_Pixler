from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialogButtonBox

from geoworkbench.project.controller import ProjectController
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.import_review_dialog import ImportReviewDialog
from geoworkbench.ui.main_window import MainWindow
from tools.fetch_external_format_fixtures import CORPUS


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("extension", [".geolog.json", ".geologpkg"])
def test_pilot_real_modal_apply_reopen_and_cancel_preserve_source(
    qapp, monkeypatch, tmp_path: Path, language: AppLanguage, extension: str,
) -> None:
    source = CORPUS / "las/3.0/sample_3.0.las"
    raw = source.read_bytes()
    window = MainWindow()
    window.change_language(language)
    monkeypatch.setattr("geoworkbench.ui.main_window.QFileDialog.getOpenFileName",
                        lambda *args, **kwargs: (str(source), "LAS"))
    monkeypatch.setattr(window, "_confirm_las_review", lambda *args: True)
    monkeypatch.setattr("geoworkbench.ui.main_window.QMessageBox.warning", lambda *args: None)
    real_exec = ImportReviewDialog.exec
    accepted = True
    dialogs = []
    def modal_exec(dialog):
        dialogs.append(dialog)
        QTimer.singleShot(0, lambda: dialog.buttons.button(
            QDialogButtonBox.StandardButton.Ok if accepted else QDialogButtonBox.StandardButton.Cancel
        ).click())
        return real_exec(dialog)
    monkeypatch.setattr(ImportReviewDialog, "exec", modal_exec)
    try:
        window.open_las3_pilot_action.trigger()
        dataset = window.session.current_dataset
        assert dataset is not None
        assert dialogs[-1].accepted_dataset is not None
        assert "3.0" in dialogs[-1].format_capabilities_summary.text()
        np.testing.assert_array_equal(dataset.depth, [1670.0, 1669.875, 1669.75])
        curves = {key: curve.values.copy() for key, curve in dataset.curves.items()}
        report = window.session.import_reports[dataset.dataset_id]
        project = tmp_path / ("pilot" + extension)
        ProjectController(session=window.session).save_project(project)
        reopened = ProjectController().open_project(project)
        restored = reopened.current_dataset
        assert restored is not None
        np.testing.assert_array_equal(restored.depth, dataset.depth)
        for key, values in curves.items():
            np.testing.assert_array_equal(restored.curves[key].values, values)
            assert restored.curves[key].metadata.unit == dataset.curves[key].metadata.unit
        assert reopened.source_documents[restored.dataset_id].to_bytes() == raw
        assert reopened.import_reports[restored.dataset_id].issues == report.issues
        assert reopened.dirty is False
        registered_ids = set(window.session.source_documents)
        before_dirty = window.session.dirty
        accepted = False
        window.open_las3_pilot_action.trigger()
        assert dialogs[-1].accepted_dataset is None
        assert window.session.current_dataset is dataset
        assert set(window.session.source_documents) == registered_ids
        assert window.session.dirty == before_dirty
        for key, values in curves.items():
            np.testing.assert_array_equal(dataset.curves[key].values, values)
        assert source.read_bytes() == raw
    finally:
        window.close()
