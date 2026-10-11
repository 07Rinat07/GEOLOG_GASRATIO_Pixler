from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QDialog

from geoworkbench.project.controller import ProjectController
from geoworkbench.project.interpretation_calculation_controller import InterpretationCalculationController
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_annotation_dialog import InterpretationReportAnnotationDialog
from geoworkbench.ui.interpretation_report_workspace import InterpretationReportWorkspace
from test_gas_mixture_ramp_report import _session


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("suffix", [".geolog.json", ".geologpkg"])
def test_annotation_button_matches_editor_availability_after_reopen(qapp, tmp_path: Path, monkeypatch, language, suffix):
    target = tmp_path / ("annotation-availability" + suffix)
    ProjectController(session=_session()).save_project(target)
    session = ProjectController().open_project(target)
    dataset = session.current_dataset
    before_depth = dataset.depth.copy()
    before_curves = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    workspace = InterpretationReportWorkspace(InterpretationCalculationController(session), language=language)
    opened = []

    def execute(dialog):
        assert dialog.parent() is workspace
        assert dialog._language is workspace.language
        assert dialog.controller.available() == ()
        opened.append(dialog)
        dialog.accept()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(InterpretationReportAnnotationDialog, "exec", execute)
    try:
        for mode in ("well_text", "mixture_chart", "mixture_text", "opus_text", "well_text"):
            index = workspace.report_mode.findData(mode)
            assert index >= 0
            workspace.report_mode.setCurrentIndex(index)
            expected = not mode.startswith("mixture_")
            assert workspace.report_annotations_button.isEnabled() is expected
            count = len(opened)
            workspace.report_annotations_button.click()
            assert len(opened) == count + int(expected)
            if not expected:
                workspace._edit_report_annotations()
                assert len(opened) == count
            other_language = AppLanguage.KK if language is not AppLanguage.KK else AppLanguage.EN
            workspace.set_language(other_language)
            assert workspace.report_annotations_button.isEnabled() is expected
            workspace.set_language(language)
        dataset_id = session.current_dataset_id
        session.current_dataset_id = None
        workspace.refresh()
        assert not workspace.report_annotations_button.isEnabled()
        count = len(opened)
        workspace.report_annotations_button.click()
        workspace._edit_report_annotations()
        assert len(opened) == count
        session.current_dataset_id = dataset_id
        workspace.refresh()
        assert workspace.report_annotations_button.isEnabled()
        workspace.report_annotations_button.click()
        assert len(opened) == count + 1
        np.testing.assert_array_equal(dataset.depth, before_depth)
        for key, values in before_curves.items():
            np.testing.assert_array_equal(dataset.curves[key].values, values)
    finally:
        for dialog in opened:
            dialog.deleteLater()
        workspace.close()
        workspace.deleteLater()
        qapp.processEvents()
