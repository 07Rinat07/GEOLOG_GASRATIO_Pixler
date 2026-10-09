from copy import deepcopy
from pathlib import Path
import json
from unicodedata import normalize
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import fitz
import numpy as np
from openpyxl import load_workbook
import pytest
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QDialog

from geoworkbench.domain.report_composition import (
    DEFAULT_INTERPRETATION_REPORT_COMPOSITION,
    ReportHeaderFields,
    ensure_report_composition_id,
    report_header_fields,
    with_report_header_fields,
)
from geoworkbench.printing.hydrocarbon_report_i18n import hydrocarbon_report_labels
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.report_passport import passport_sidecar_path
from geoworkbench.ui import interpretation_report_workspace_final as final
from geoworkbench.ui.interpretation_report_workspace import InterpretationReportWorkspace
from test_interpretation_depth_interval import _session


def _normalized(text):
    return "".join(normalize("NFKC", text).split())


def _header(language, profile):
    prefix = f"{language.value.upper()}-{profile}"
    return ReportHeaderFields(
        report_profile=profile,
        report_title=prefix + " TITLE Әғқң <&>",
        document_number=prefix + "-DOCUMENT",
        revision="03",
        prepared_by=prefix + "-PREPARED",
        checked_by=prefix + "-CHECKED",
        report_date="2026-10-10",
        summary=prefix + "-SUMMARY",
    )


def _file_text(path):
    if path.suffix == ".pdf":
        with fitz.open(path) as pdf:
            return "\n".join(page.get_text() for page in pdf)
    if path.suffix == ".docx":
        with ZipFile(path) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))
        return "".join(
            node.text or ""
            for node in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
        )
    book = load_workbook(path, data_only=True)
    try:
        return "\n".join(
            str(cell.value)
            for sheet in book
            for row in sheet
            for cell in row
            if cell.value is not None
        )
    finally:
        book.close()


@pytest.mark.parametrize("ui_language", list(AppLanguage))
@pytest.mark.parametrize("output_language", list(AppLanguage))
@pytest.mark.parametrize("profile", ["standard", "opus"])
def test_production_output_language_routes_all_formats_and_saved_headers(
    qapp,
    tmp_path: Path,
    monkeypatch,
    ui_language,
    output_language,
    profile,
):
    session = _session()
    dataset = session.current_dataset
    composition = ensure_report_composition_id(
        DEFAULT_INTERPRETATION_REPORT_COMPOSITION, dataset.dataset_id
    )
    for language in AppLanguage:
        composition = with_report_header_fields(
            composition, language.value, _header(language, profile)
        )
    session.report_compositions[dataset.dataset_id] = composition
    project_path = tmp_path / "languages.geologpkg"
    ProjectController(session=session).save_project(project_path)
    session = ProjectController().open_project(project_path)
    dataset = session.current_dataset
    before_dataset = deepcopy(dataset)
    workspace = InterpretationReportWorkspace(
        InterpretationCalculationController(session), language=ui_language
    )
    try:
        mode = "well_text" if profile == "standard" else "opus_text"
        workspace.report_mode.setCurrentIndex(workspace.report_mode.findData(mode))
        report = workspace.report
        assert report is not None and report.report_profile == profile
        before_report = deepcopy(report)
        workspace.report_output_language.setCurrentIndex(
            workspace.report_output_language.findData(output_language)
        )
        assert workspace.report is report
        assert workspace.language == ui_language
        labels = hydrocarbon_report_labels(output_language)
        chosen_header = _header(output_language, profile)
        preview = _normalized(workspace.preview.toPlainText())
        assert _normalized(chosen_header.summary) in preview
        assert _normalized(labels.project) in preview
        other_ui = AppLanguage.KK if ui_language != AppLanguage.KK else AppLanguage.EN
        workspace.set_language(other_ui)
        assert workspace.report_output_language.currentData() == output_language
        assert _normalized(chosen_header.summary) in _normalized(workspace.preview.toPlainText())
        monkeypatch.setattr(
            final.InterpretationReportDetailsDialog,
            "exec",
            lambda self: QDialog.DialogCode.Accepted,
        )
        monkeypatch.setattr(
            final.InterpretationPrintLayoutDialog, "exec", lambda self: QDialog.DialogCode.Accepted
        )
        monkeypatch.setattr(workspace, "_show_export_success", lambda *args: None)
        monkeypatch.setattr(workspace, "_show_export_error", lambda error: pytest.fail(str(error)))
        for suffix, method in (
            (".pdf", "_export_pdf"),
            (".docx", "_export_docx"),
            (".xlsx", "_export_xlsx"),
        ):
            target = tmp_path / ("report" + suffix)
            monkeypatch.setattr(workspace, "_choose_target", lambda *args, target=target: target)
            getattr(workspace, method)()
            text = _normalized(_file_text(target))
            for value in (
                chosen_header.report_title,
                chosen_header.document_number,
                chosen_header.prepared_by,
                labels.project,
            ):
                assert _normalized(value) in text
            for language in AppLanguage:
                if language != output_language:
                    assert _normalized(_header(language, profile).document_number) not in text
            if suffix == ".pdf":
                passport = json.loads(passport_sidecar_path(target).read_text(encoding="utf-8"))
                assert passport["language"] == output_language.value
        prepared = tmp_path / "prepared.pdf"
        original_export = final.export_hydrocarbon_interpretation_pdf

        def capture_export(report, target, **kwargs):
            assert kwargs["language"] == output_language
            result = original_export(report, target, **kwargs)
            prepared.write_bytes(Path(result).read_bytes())
            return result

        monkeypatch.setattr(final, "export_hydrocarbon_interpretation_pdf", capture_export)
        printed = tmp_path / "printed.pdf"

        class Dialog(final.QPrintDialog):
            def __init__(self, printer, parent):
                super().__init__(printer, parent)
                self.target_printer = printer

            def exec(self):
                self.target_printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
                self.target_printer.setOutputFileName(str(printed))
                self.target_printer.setResolution(150)
                return QDialog.DialogCode.Accepted

        monkeypatch.setattr(final, "QPrintDialog", Dialog)
        workspace._print_report()
        prepared_text = _normalized(_file_text(prepared))
        assert _normalized(chosen_header.report_title) in prepared_text
        assert _normalized(labels.project) in prepared_text
        with fitz.open(printed) as pdf:
            assert len(pdf) > 0
            assert all(page.get_images() for page in pdf)
        current = workspace._report_composition()
        for language in AppLanguage:
            saved = report_header_fields(current, language.value, profile)
            expected = _header(language, profile)
            assert saved.report_title == expected.report_title
            assert saved.document_number == expected.document_number
            other_profile = "opus" if profile == "standard" else "standard"
            assert report_header_fields(current, language.value, other_profile) is None
        assert report == before_report
        np.testing.assert_array_equal(dataset.depth, before_dataset.depth)
        for key, curve in dataset.curves.items():
            assert curve.metadata == before_dataset.curves[key].metadata
            np.testing.assert_array_equal(curve.values, before_dataset.curves[key].values)
    finally:
        workspace.close()
        workspace.deleteLater()
        qapp.processEvents()
