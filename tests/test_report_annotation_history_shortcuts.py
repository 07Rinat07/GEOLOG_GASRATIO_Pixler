from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog

from geoworkbench.project.controller import ProjectController
from geoworkbench.services.edit_history import CommandHistory
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_annotation_dialog import InterpretationReportAnnotationDialog
from test_report_annotations import _session


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("suffix", (".geolog.json", ".geologpkg"))
def test_editor_keyboard_history_commit_cancel_and_reopen(
    qapp, tmp_path: Path, language: AppLanguage, suffix: str,
) -> None:
    session = _session()
    dataset = session.current_dataset
    raw_depth = dataset.depth.copy()
    raw_curves = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    history = CommandHistory(max_commands=100)
    dialog = InterpretationReportAnnotationDialog(
        session, language=language, shared_history=history,
    )

    def press(editor, *, redo=False):
        # Focus a command control so native text-field Undo stays independent.
        editor.add_button.setFocus()
        qapp.processEvents()
        modifiers = Qt.KeyboardModifier.ControlModifier
        if redo:
            modifiers |= Qt.KeyboardModifier.ShiftModifier
        QTest.keyClick(editor.add_button, Qt.Key.Key_Z, modifiers)
        qapp.processEvents()

    try:
        dialog.show()
        dialog.activateWindow()
        qapp.processEvents()
        for index in range(20):
            dialog.annotation.setCurrentIndex(0)
            dialog.track.setCurrentText("curve:TG")
            dialog.depth_spin.setValue(1001.0)
            dialog.text.setText(f"Keyboard note {language.value} {index}")
            dialog.add_button.click()
        records = dialog.controller.available()
        assert len(records) == 20
        dialog.text.setText("")
        dialog.text.setFocus()
        QTest.keyClicks(dialog.text, "Native text draft")
        QTest.keyClick(dialog.text, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        qapp.processEvents()
        assert dialog.text.text() == ""
        assert dialog.controller.available() == records
        for remaining in range(19, -1, -1):
            press(dialog)
            assert dialog.controller.available() == records[:remaining]
        press(dialog)
        assert dialog.controller.available() == ()
        for restored in range(1, 21):
            press(dialog, redo=True)
            assert dialog.controller.available() == records[:restored]
        press(dialog, redo=True)
        assert dialog.controller.available() == records
        dialog.accept()
        target = tmp_path / ("keyboard-history" + suffix)
        ProjectController(session=session).save_project(target)
        reopened = ProjectController().open_project(target)
        second = InterpretationReportAnnotationDialog(
            reopened, language=language, shared_history=history,
        )
        try:
            second.show()
            second.activateWindow()
            qapp.processEvents()
            assert second.controller.available() == records
            assert not second.undo_button.isEnabled()
            assert not second.redo_button.isEnabled()
            press(second)
            press(second, redo=True)
            assert not reopened.dirty
            second.annotation.setCurrentIndex(0)
            second.text.setText("Cancelled keyboard draft")
            second.depth_spin.setValue(1002.0)
            second.add_button.click()
            press(second)
            assert second.controller.available() == records
            press(second, redo=True)
            assert len(second.controller.available()) == 21
            second.reject()
            assert second.controller.available() == records
            assert not reopened.dirty
            np.testing.assert_array_equal(reopened.current_dataset.depth, raw_depth)
            for key, values in raw_curves.items():
                np.testing.assert_array_equal(reopened.current_dataset.curves[key].values, values)
        finally:
            second.deleteLater()
    finally:
        if dialog.result() != QDialog.DialogCode.Accepted:
            dialog.reject()
        dialog.deleteLater()
        qapp.processEvents()
