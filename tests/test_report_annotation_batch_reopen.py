import numpy as np
import pytest
from PySide6.QtWidgets import QDialog, QListWidget

from geoworkbench.project.controller import ProjectController
from geoworkbench.project.report_annotation_controller import ReportAnnotationController
from geoworkbench.services.edit_history import CommandHistory
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_annotation_dialog import InterpretationReportAnnotationDialog
from test_report_annotations_multiwell_acceptance import PAIRS, _select, _two_well_session


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("suffix", [".geolog.json", ".geologpkg"])
def test_group_delete_apply_cancel_multiwell_and_production_reopen(qapp, tmp_path, monkeypatch, language, suffix):
    session = _two_well_session()
    history = CommandHistory()
    expected = {}
    sources = {}
    dialogs = []
    def choose(selection):
        listing = selection.findChild(QListWidget, "report-annotation-group-selection")
        assert listing.count() == 3
        listing.item(0).setSelected(True)
        listing.item(2).setSelected(True)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(QDialog, "exec", choose)
    try:
        for well_id, dataset_id, depth in PAIRS:
            _select(session, well_id, dataset_id)
            dataset = session.current_dataset
            sources[dataset_id] = (dataset.depth.copy(), {key: curve.values.copy() for key, curve in dataset.curves.items()})
            dialog = InterpretationReportAnnotationDialog(session, language=language, shared_history=history)
            dialogs.append(dialog)
            for i in range(3):
                dialog.annotation.setCurrentIndex(0)
                dialog.text.setText(f"{language.value} {well_id} {i}")
                dialog.depth_spin.setValue(depth + i)
                dialog.add_button.click()
            records = dialog.controller.available()
            dialog.batch_remove_button.click()
            assert dialog.controller.available() == (records[1],)
            dialog.undo_button.click()
            assert dialog.controller.available() == records
            dialog.redo_button.click()
            assert dialog.controller.available() == (records[1],)
            dialog.apply_button.click()
            dialog.annotation.setCurrentIndex(0)
            dialog.text.setText("Cancelled draft")
            dialog.depth_spin.setValue(depth)
            dialog.add_button.click()
            dialog.reject()
            expected[dataset_id] = (records[1],)
            assert dialog.controller.available() == expected[dataset_id]
        target = tmp_path / ("batch-reopen" + suffix)
        ProjectController(session=session).save_project(target)
        reopened = ProjectController().open_project(target)
        assert not reopened.dirty
        for well_id, dataset_id, _ in PAIRS:
            _select(reopened, well_id, dataset_id)
            controller = ReportAnnotationController(reopened, shared_history=history)
            assert controller.available() == expected[dataset_id]
            assert not controller.can_undo
            assert not controller.can_redo
            dataset = reopened.current_dataset
            depth, curves = sources[dataset_id]
            np.testing.assert_array_equal(dataset.depth, depth)
            for key, values in curves.items():
                np.testing.assert_array_equal(dataset.curves[key].values, values)
        assert not reopened.dirty
        assert expected[PAIRS[0][1]][0].scope_id != expected[PAIRS[1][1]][0].scope_id
    finally:
        for dialog in dialogs:
            dialog.deleteLater()
        qapp.processEvents()
