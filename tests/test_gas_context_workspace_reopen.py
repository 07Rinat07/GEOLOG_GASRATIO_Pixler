import numpy as np
import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from geoworkbench.domain.gas_context_events import GasContextEventType
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.interpretation_calculation_controller import InterpretationCalculationController
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.gas_context_event_dialog import GasContextEventDialog
from geoworkbench.ui.interpretation_report_workspace import InterpretationReportWorkspace
from test_gas_context_negative_depth_acceptance import _negative_session


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("suffix", [".geolog.json", ".geologpkg"])
def test_real_workspace_gas_context_controls_save_cancel_and_project_reopen(qapp, tmp_path, language, suffix):
    session = _negative_session()
    workspace = InterpretationReportWorkspace(InterpretationCalculationController(session), language=language)
    failures = []
    before = session.current_dataset.depth.copy()
    curves_before = {key: curve.values.copy() for key, curve in session.current_dataset.curves.items()}

    def edit(save):
        dialog = QApplication.activeModalWidget()
        try:
            assert isinstance(dialog, GasContextEventDialog)
            assert dialog.language is language
            dialog.type_input.setCurrentIndex(dialog.type_input.findData(GasContextEventType.CONNECTION_GAS))
            dialog.top_input.setValue(-61.125 if save else -50.0)
            dialog.bottom_input.setValue(-57.875 if save else -48.0)
            dialog.add_button.click()
            assert dialog.table.rowCount() == (1 if save else 2)
            buttons = dialog.findChild(QDialogButtonBox, "gas-context-event-buttons")
            buttons.button(QDialogButtonBox.StandardButton.Save if save else QDialogButtonBox.StandardButton.Cancel).click()
        except BaseException as exc:
            failures.append(exc)
            if isinstance(dialog, GasContextEventDialog):
                dialog.reject()

    try:
        QTimer.singleShot(0, lambda: edit(True))
        workspace.gas_context_button.click()
        assert failures == []
        well = session.current_well
        assert len(well.gas_context_events) == 1
        event = well.gas_context_events[0]
        assert event.event_type is GasContextEventType.CONNECTION_GAS
        assert (event.top_depth, event.bottom_depth) == (-61.125, -57.875)
        persisted = tuple(well.gas_context_events)
        QTimer.singleShot(0, lambda: edit(False))
        workspace.gas_context_button.click()
        assert failures == []
        assert tuple(well.gas_context_events) == persisted
        path = tmp_path / ("context" + suffix)
        ProjectController(session=session).save_project(path)
        reopened = ProjectController().open_project(path)
        assert tuple(reopened.current_well.gas_context_events) == persisted
        assert not reopened.dirty
        np.testing.assert_array_equal(reopened.current_dataset.depth, before)
        np.testing.assert_array_equal(session.current_dataset.depth, before)
        for key, values in curves_before.items():
            np.testing.assert_array_equal(reopened.current_dataset.curves[key].values, values)
            np.testing.assert_array_equal(session.current_dataset.curves[key].values, values)
    finally:
        workspace.close()
        workspace.deleteLater()
        qapp.processEvents()
