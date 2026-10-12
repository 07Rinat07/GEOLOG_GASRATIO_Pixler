import pytest
from PySide6.QtWidgets import QDialog, QListWidget

from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_annotation_dialog import InterpretationReportAnnotationDialog
from test_report_annotations import _session


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("cancel_selection", [False, True])
def test_group_delete_real_button_and_selection_preserve_undo_cancel(qapp, monkeypatch, language, cancel_selection):
    session = _session()
    dialog = InterpretationReportAnnotationDialog(session, language=language)
    try:
        assert not dialog.batch_remove_button.isEnabled()
        for i in range(3):
            dialog.annotation.setCurrentIndex(0)
            dialog.text.setText(f"Note {i}")
            dialog.depth_spin.setValue(1000.0 + i)
            dialog.add_button.click()
        records = dialog.controller.available()
        dialog.apply_button.click()
        def choose(selection):
            listing = selection.findChild(QListWidget, "report-annotation-group-selection")
            assert listing.count() == 3
            listing.item(0).setSelected(True)
            listing.item(2).setSelected(True)
            return QDialog.DialogCode.Rejected if cancel_selection else QDialog.DialogCode.Accepted
        monkeypatch.setattr(QDialog, "exec", choose)
        dialog.batch_remove_button.click()
        if cancel_selection:
            assert dialog.controller.available() == records
        else:
            assert dialog.controller.available() == (records[1],)
            dialog.undo_button.click()
            assert dialog.controller.available() == records
            dialog.redo_button.click()
            assert dialog.controller.available() == (records[1],)
        dialog.reject()
        assert dialog.controller.available() == records
    finally:
        dialog.deleteLater()
        qapp.processEvents()
