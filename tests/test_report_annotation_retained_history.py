import pytest

from geoworkbench.project.report_annotation_controller import ReportAnnotationController
from geoworkbench.services.edit_history import CommandHistory
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_annotation_dialog import InterpretationReportAnnotationDialog
from test_report_annotations_multiwell_acceptance import PAIRS, _select, _two_well_session


@pytest.mark.parametrize("language", list(AppLanguage))
def test_reopening_editor_retains_history_and_cancel_restores_earlier_edits(qapp, language):
    session = _two_well_session()
    history = CommandHistory()
    dialogs = []
    try:
        _select(session, *PAIRS[0][:2])
        first = InterpretationReportAnnotationDialog(session, language=language, shared_history=history)
        dialogs.append(first)
        first.text.setText("Saved A")
        first.depth_spin.setValue(1001.0)
        first.add_button.click()
        records = first.controller.available()
        retained = history.next_undo
        first.accept()
        reopened = InterpretationReportAnnotationDialog(session, language=language, shared_history=history)
        dialogs.append(reopened)
        assert history.next_undo is retained
        assert reopened.undo_button.isEnabled()
        reopened.undo_button.click()
        assert reopened.controller.available() == ()
        reopened.reject()
        assert reopened.controller.available() == records
        assert history.next_undo is retained
        assert reopened.controller.can_undo

        _select(session, *PAIRS[1][:2])
        second = InterpretationReportAnnotationDialog(session, language=language, shared_history=history)
        dialogs.append(second)
        assert history.next_undo is retained
        assert not second.undo_button.isEnabled()
        assert not second.redo_button.isEnabled()
        second.text.setText("Saved B")
        second.depth_spin.setValue(2001.0)
        second.add_button.click()
        second.apply_button.click()
        second.reject()
        b_records = second.controller.available()
        assert len(b_records) == 1
        _select(session, *PAIRS[0][:2])
        a = ReportAnnotationController(session, shared_history=history)
        assert not a.can_undo
        assert a.available() == records
        _select(session, *PAIRS[1][:2])
        second.controller.undo()
        assert second.controller.available() == ()
        assert not second.controller.can_undo
        _select(session, *PAIRS[0][:2])
        assert a.can_undo
        assert not a.can_redo
        a.undo()
        a.redo()
        assert a.available() == records
    finally:
        for dialog in dialogs:
            dialog.deleteLater()
        qapp.processEvents()
