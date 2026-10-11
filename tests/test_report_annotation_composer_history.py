from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QDialog

from geoworkbench.project.controller import ProjectController
from geoworkbench.project.interpretation_calculation_controller import InterpretationCalculationController
from geoworkbench.project.report_annotation_controller import ReportAnnotationController
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_annotation_dialog import InterpretationReportAnnotationDialog
from geoworkbench.ui.interpretation_report_workspace import InterpretationReportWorkspace
from test_report_annotations_multiwell_acceptance import PAIRS, _select, _two_well_session


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("suffix", (".geolog.json", ".geologpkg"))
def test_composer_annotation_history_cancel_multiwell_and_reopen(
    qapp, tmp_path: Path, monkeypatch, language: AppLanguage, suffix: str,
) -> None:
    session = _two_well_session()
    editor = ReportAnnotationController(session)
    sources = {
        dataset_id: (
            session.project.wells[well_id].datasets[dataset_id].depth.copy(),
            session.project.wells[well_id].datasets[dataset_id]
            .curves[f"curve-{dataset_id}"].values.copy(),
        )
        for well_id, dataset_id, _ in PAIRS
    }
    workspace = InterpretationReportWorkspace(
        InterpretationCalculationController(session), language=language,
    )
    dialogs = []
    phase = "commit-a"
    committed = {}

    def execute(dialog):
        dialogs.append(dialog)
        assert dialog.parent() is workspace
        assert dialog._language is language
        assert dialog.controller.shared_history is workspace._report_annotation_history
        assert not dialog.undo_button.isEnabled()
        assert not dialog.redo_button.isEnabled()
        dataset_id = session.current_dataset_id
        if phase == "inspect":
            expected = committed[dataset_id]
            assert dialog.controller.available() == expected
            dialog.annotation.setCurrentIndex(1)
            assert dialog.text.text() == expected[0].text
            assert dialog.depth_spin.value() == expected[0].depth
            dialog.reject()
            return QDialog.DialogCode.Rejected

        assert dialog.controller.available() == ()
        first_depth = session.current_dataset.depth[0]
        count = 20 if phase == "commit-a" else 1
        for index in range(count):
            dialog.annotation.setCurrentIndex(0)
            dialog.track.setCurrentText("curve:C1")
            dialog.depth_spin.setValue(first_depth + 1.0)
            dialog.text.setText(f"{language.value}:{dataset_id}:{index}")
            dialog.add_button.click()
            assert len(dialog.controller.available()) == index + 1
        records = dialog.controller.available()
        if phase == "commit-a":
            for remaining in range(19, -1, -1):
                assert dialog.undo_button.isEnabled()
                dialog.undo_button.click()
                assert dialog.controller.available() == records[:remaining]
            assert not dialog.undo_button.isEnabled()
            for restored in range(1, 21):
                assert dialog.redo_button.isEnabled()
                dialog.redo_button.click()
                assert dialog.controller.available() == records[:restored]
            assert not dialog.redo_button.isEnabled()
        if phase == "cancel-b":
            dialog.reject()
            assert dialog.controller.available() == ()
            return QDialog.DialogCode.Rejected
        committed[dataset_id] = records
        dialog.accept()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(InterpretationReportAnnotationDialog, "exec", execute)
    try:
        # Drive the real Composer button; only the modal wait is scripted.
        workspace.report_annotations_button.click()
        assert len(dialogs) == 1
        assert len(editor.available()) == 20
        _select(session, "well-b", "dataset-b")
        workspace.refresh()
        phase = "cancel-b"
        workspace.report_annotations_button.click()
        assert len(dialogs) == 2
        assert editor.available() == ()
        _select(session, "well-a", "dataset-a")
        assert editor.available() == committed["dataset-a"]
        _select(session, "well-b", "dataset-b")
        workspace.refresh()
        phase = "commit-b"
        workspace.report_annotations_button.click()
        assert len(dialogs) == 3
        assert editor.available() == committed["dataset-b"]
        assert committed["dataset-a"][0].scope_id != committed["dataset-b"][0].scope_id

        target = tmp_path / ("composer-history" + suffix)
        ProjectController(session=session).save_project(target)
        reopened = ProjectController().open_project(target)
        assert not reopened.dirty
        for dialog in dialogs:
            dialog.deleteLater()
        workspace.close()
        workspace.deleteLater()
        qapp.processEvents()
        dialogs.clear()
        session = reopened
        editor = ReportAnnotationController(session)
        workspace = InterpretationReportWorkspace(
            InterpretationCalculationController(session), language=language,
        )
        phase = "inspect"
        for well_id, dataset_id, _ in PAIRS:
            _select(session, well_id, dataset_id)
            workspace.refresh()
            workspace.report_annotations_button.click()
            assert editor.available() == committed[dataset_id]
            assert not session.dirty
            dataset = session.current_dataset
            expected_depth, expected_values = sources[dataset_id]
            np.testing.assert_array_equal(dataset.depth, expected_depth)
            np.testing.assert_array_equal(
                dataset.curves[f"curve-{dataset_id}"].values, expected_values,
            )
        assert len(dialogs) == 2
        with pytest.raises(KeyError):
            editor.get(committed["dataset-a"][0].annotation_id)
    finally:
        for dialog in dialogs:
            dialog.deleteLater()
        workspace.close()
        workspace.deleteLater()
        qapp.processEvents()
