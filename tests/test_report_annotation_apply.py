import numpy as np
import pytest
from PySide6.QtWidgets import QDialog

from geoworkbench.project.controller import ProjectController
from geoworkbench.services.edit_history import CommandHistory
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_annotation_dialog import InterpretationReportAnnotationDialog
from test_report_annotations import _session


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("replace_branch", [False, True])
def test_apply_keeps_history_and_cancel_returns_latest_applied_draft(
    qapp, language, replace_branch,
):
    session = _session()
    dataset = session.current_dataset
    depth = dataset.depth.copy()
    curves = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    history = CommandHistory()
    dialog = InterpretationReportAnnotationDialog(session, language=language, shared_history=history)
    try:
        for index in range(2):
            dialog.annotation.setCurrentIndex(0)
            dialog.text.setText(f"Applied {index}")
            dialog.depth_spin.setValue(1000.0 + index)
            dialog.add_button.click()
        applied = dialog.controller.available()
        retained = history.next_undo
        dialog.apply_button.click()
        assert history.next_undo is retained
        assert dialog.controller.can_undo
        assert dialog.result() != QDialog.DialogCode.Accepted
        dialog.undo_button.click()
        dialog.undo_button.click()
        if replace_branch:
            dialog.annotation.setCurrentIndex(0)
            dialog.text.setText("Replacement draft")
            dialog.depth_spin.setValue(1002.0)
            dialog.add_button.click()
        dialog.reject()
        assert dialog.controller.available() == applied
        assert history.next_undo is retained
        assert not history.can_redo
        dialog.controller.undo()
        dialog.controller.redo()
        assert dialog.controller.available() == applied
        np.testing.assert_array_equal(dataset.depth, depth)
        for key, values in curves.items():
            np.testing.assert_array_equal(dataset.curves[key].values, values)
    finally:
        dialog.close()
        dialog.deleteLater()
        qapp.processEvents()


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("suffix", [".geolog.json", ".geologpkg"])
def test_latest_apply_survives_cancel_save_and_reopen(qapp, tmp_path, language, suffix):
    session = _session()
    dataset = session.current_dataset
    source_depth = dataset.depth.copy()
    source_curves = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    history = CommandHistory()
    dialog = InterpretationReportAnnotationDialog(session, language=language, shared_history=history)
    reopened_dialog = None
    try:
        for index in range(2):
            dialog.annotation.setCurrentIndex(0)
            dialog.text.setText(f"Applied {index}")
            dialog.depth_spin.setValue(1000.0 + index)
            dialog.add_button.click()
            dialog.apply_button.click()
        applied = dialog.controller.available()
        dialog.annotation.setCurrentIndex(0)
        dialog.text.setText("Cancelled draft")
        dialog.depth_spin.setValue(1002.0)
        dialog.add_button.click()
        dialog.reject()
        assert dialog.controller.available() == applied
        assert session.dirty
        path = tmp_path / ("applied-annotations" + suffix)
        ProjectController(session=session).save_project(path)
        reopened = ProjectController().open_project(path)
        assert not reopened.dirty
        reopened_dialog = InterpretationReportAnnotationDialog(
            reopened, language=language, shared_history=history,
        )
        assert reopened_dialog.controller.available() == applied
        assert not reopened_dialog.undo_button.isEnabled()
        assert not reopened_dialog.redo_button.isEnabled()
        reopened_dialog.apply_button.click()
        reopened_dialog.reject()
        assert not reopened.dirty
        assert reopened_dialog.controller.available() == applied
        np.testing.assert_array_equal(reopened.current_dataset.depth, source_depth)
        for key, values in source_curves.items():
            np.testing.assert_array_equal(reopened.current_dataset.curves[key].values, values)
    finally:
        dialog.deleteLater()
        if reopened_dialog is not None:
            reopened_dialog.deleteLater()
        qapp.processEvents()
