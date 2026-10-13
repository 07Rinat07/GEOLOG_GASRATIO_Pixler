import pytest

from geoworkbench.domain.report_annotations import ReportAnnotationKind
from geoworkbench.project.controller import ProjectController
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_annotation_dialog import InterpretationReportAnnotationDialog
from test_report_annotations import _session


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("extension", [".geolog.json", ".geologpkg"])
def test_real_symbol_controls_history_print_toggle_cancel_and_reopen(qapp, tmp_path, language, extension):
    session = _session()
    dialog = InterpretationReportAnnotationDialog(session, language=language)
    dialog.kind.setCurrentIndex(dialog.kind.findData(ReportAnnotationKind.SYMBOL.value))
    assert dialog.symbol.isEnabled()
    dialog.symbol.setCurrentIndex(dialog.symbol.findData("diamond"))
    dialog.text.setText("Author caption")
    dialog.depth_spin.setValue(1001.0)
    dialog.print_enabled.setChecked(False)
    dialog.add_button.click()
    record = dialog.controller.available()[0]
    assert record.symbol_id.value == "diamond"
    assert record.print_enabled is False
    dialog.symbol.setCurrentIndex(dialog.symbol.findData("cross"))
    dialog.save_button.click()
    assert dialog.controller.available()[0].symbol_id.value == "cross"
    dialog.undo_button.click()
    assert dialog.controller.available()[0].symbol_id.value == "diamond"
    dialog.redo_button.click()
    dialog.apply_button.click()
    dialog.print_enabled.setChecked(True)
    dialog.save_button.click()
    dialog.reject()
    assert dialog.controller.available()[0].print_enabled is False
    target = tmp_path / ("symbol" + extension)
    ProjectController(session=session).save_project(target)
    reopened = ProjectController().open_project(target)
    editor = InterpretationReportAnnotationDialog(reopened, language=language)
    editor.annotation.setCurrentIndex(1)
    assert editor.kind.currentData() == "symbol"
    assert editor.symbol.currentData() == "cross"
    assert editor.text.text() == "Author caption"
    assert editor.print_enabled.isChecked() is False
    editor.reject()
    dialog.close()
    editor.close()
