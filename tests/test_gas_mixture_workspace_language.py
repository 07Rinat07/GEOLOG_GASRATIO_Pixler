from pathlib import Path
from unicodedata import normalize

import fitz
import pytest
from PySide6.QtWidgets import QDialog

from geoworkbench.printing import gas_mixture_ramp_report as ramp
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.interpretation_calculation_controller import InterpretationCalculationController
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui import interpretation_report_workspace_legacy as legacy
from geoworkbench.ui.interpretation_report_workspace import InterpretationReportWorkspace
from test_gas_mixture_ramp_report import _session


def _normalized(text):
    return ''.join(normalize('NFKC', text).split())


@pytest.mark.parametrize('ui_language', list(AppLanguage))
@pytest.mark.parametrize('output_language', list(AppLanguage))
@pytest.mark.parametrize('mode', ['mixture_chart', 'mixture_text'])
def test_production_workspace_keeps_preview_pdf_and_printer_language_independent(
    qapp, tmp_path: Path, monkeypatch, ui_language, output_language, mode,
):
    project_path = tmp_path / 'ramp.geologpkg'
    ProjectController(session=_session()).save_project(project_path)
    session = ProjectController().open_project(project_path)
    workspace = InterpretationReportWorkspace(InterpretationCalculationController(session), language=ui_language)
    try:
        workspace.report_mode.setCurrentIndex(workspace.report_mode.findData(mode))
        report = workspace.gas_mixture_report
        assert report is not None
        assert not workspace.ramp_output_language.isHidden()
        workspace.ramp_output_language.setCurrentIndex(workspace.ramp_output_language.findData(output_language))
        assert workspace.gas_mixture_report is report
        assert workspace.language == ui_language
        labels = ramp._labels(output_language)
        assert labels['title'] in workspace.preview.toPlainText()
        other_ui = AppLanguage.KK if ui_language != AppLanguage.KK else AppLanguage.EN
        workspace.set_language(other_ui)
        assert workspace.ramp_output_language.currentData() == output_language
        assert labels['title'] in workspace.preview.toPlainText()
        target = tmp_path / 'export.pdf'
        monkeypatch.setattr(workspace, '_choose_target', lambda *args: target)
        monkeypatch.setattr(workspace, '_show_export_success', lambda *args: None)
        monkeypatch.setattr(workspace, '_show_export_error', lambda error: pytest.fail(str(error)))
        workspace._export_pdf()
        printed = tmp_path / 'printed.pdf'
        class Dialog:
            def __init__(self, printer, parent):
                self.printer = printer
            def setWindowTitle(self, title):
                pass
            def exec(self):
                self.printer.setOutputFormat(self.printer.OutputFormat.PdfFormat)
                self.printer.setOutputFileName(str(printed))
                return QDialog.DialogCode.Accepted
        monkeypatch.setattr(legacy, 'QPrintDialog', Dialog)
        workspace._print_report()
        for path in (target, printed):
            with fitz.open(path) as pdf:
                text = _normalized('\n'.join(page.get_text() for page in pdf))
                for value in (labels['title'], labels['component'], labels['composition'], *ramp.localized_ramp_warnings(report.warnings, output_language)):
                    assert _normalized(value) in text
                if output_language == AppLanguage.EN:
                    assert 'Компонент' not in text
        workspace.report_mode.setCurrentIndex(workspace.report_mode.findData('well_text'))
        assert workspace.ramp_output_language.isHidden()
        workspace.report_mode.setCurrentIndex(workspace.report_mode.findData(mode))
        assert workspace.ramp_output_language.currentData() == output_language
    finally:
        workspace.close()
        workspace.deleteLater()
        qapp.processEvents()
