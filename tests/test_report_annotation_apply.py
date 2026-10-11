import numpy as np
import pytest
from PySide6.QtWidgets import QDialog

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
