"""Complete reviewed geology workflow: independent approvals and atomic Excel."""
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import fitz
import numpy as np
from openpyxl import load_workbook
import pytest
from PySide6.QtWidgets import QComboBox, QPushButton, QTextBrowser

from geoworkbench.data import hydrocarbon_interpretation_export_readable as readable
from geoworkbench.services.interpretation_geology_interval_evidence_html import geology_interval_evidence_table
from geoworkbench.services.localization import AppLanguage
from test_interpretation_geology_evidence_operator_ui import _workspace
from test_interpretation_geology_evidence_ui_pdf_handoff import (
    _bounded_native_qt as _bounded_native_qt,
    _no_unexpected_modal_message as _no_unexpected_modal_message,
)
from test_interpretation_method_comparison_ui_pdf_handoff import _prepare_dialogs
from test_interpretation_method_comparison_ui_print_handoff import _prepare_print, _capture_spooled_pdf


def _prepare(qapp, monkeypatch, tmp_path, language=AppLanguage.EN):
    workspace, session = _workspace(monkeypatch, language)
    _prepare_dialogs(monkeypatch, workspace)
    monkeypatch.setattr(workspace, "_choose_target", lambda suffix, *_: tmp_path / ("report" + suffix))
    monkeypatch.setattr(workspace, "_show_export_success", lambda *_: None)
    errors = []
    monkeypatch.setattr(workspace, "_show_export_error", errors.append)
    workspace.geology_evidence_button.click()
    qapp.processEvents()
    assert workspace._geology_evidence_dialog is not None
    return workspace, session, errors


def _approve(workspace, output):
    button = workspace._geology_evidence_dialog.findChild(
        QPushButton, "interpretation-geology-include-in-" + output,
    )
    assert button is not None
    button.click()


def _excel_values(path, language):
    workbook = load_workbook(path)
    try:
        name = readable._GEOLOGY_EVIDENCE_SHEET_NAMES[language]
        return [str(cell.value) for row in workbook[name] for cell in row if cell.value is not None]
    finally:
        workbook.close()


@pytest.mark.parametrize("language", tuple(AppLanguage))
def test_one_reviewed_snapshot_reaches_html_pdf_word_excel(qapp, monkeypatch, tmp_path, language):
    workspace, session, errors = _prepare(qapp, monkeypatch, tmp_path, language)
    dataset = session.current_dataset
    depth = dataset.depth.copy()
    curves = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    for output in ("excel", "pdf", "word", "print"):
        _approve(workspace, output)
    selected = workspace._geology_excel_evidence
    assert selected == workspace._geology_pdf_evidence == workspace._geology_word_evidence == workspace._geology_print_evidence
    assert len(selected) == 1
    projection = geology_interval_evidence_table(selected[0], language)
    viewer = workspace._geology_evidence_dialog.findChild(QTextBrowser, "interpretation-geology-evidence-content")
    assert projection.title in viewer.toPlainText()
    workspace._export_xlsx()
    workspace._export_docx()
    workspace._export_pdf()
    assert errors == []
    excel = _excel_values(tmp_path / "report.xlsx", language)
    with ZipFile(tmp_path / "report.docx") as archive:
        word = " ".join(ET.fromstring(archive.read("word/document.xml")).itertext())
    with fitz.open(tmp_path / "report.pdf") as document:
        pdf = re.sub(r"\s+", " ", " ".join(page.get_text() for page in document))
    _prepare_print(monkeypatch, workspace)
    printed = _capture_spooled_pdf(monkeypatch)
    workspace._print_report()
    assert len(printed) == 1
    assert projection.title in printed[0][1]
    assert projection.title in excel and projection.title in word and projection.title in pdf
    for row in (*projection.coverage_rows, *projection.rows):
        for cell in row:
            assert cell in excel
            assert cell in word
    for observation in selected[0].intersections:
        assert observation.source_id in pdf
        assert observation.source_id in printed[0][1]
    np.testing.assert_array_equal(dataset.depth, depth)
    for key, values in curves.items():
        np.testing.assert_array_equal(dataset.curves[key].values, values)
    workspace.close()


@pytest.mark.parametrize("action", ("view", "pdf", "word", "candidate", "refresh"))
def test_excel_requires_its_own_current_approval(qapp, monkeypatch, tmp_path, action):
    workspace, _, errors = _prepare(qapp, monkeypatch, tmp_path)
    if action in {"pdf", "word"}:
        _approve(workspace, action)
    elif action in {"candidate", "refresh"}:
        _approve(workspace, "excel")
        if action == "refresh":
            workspace.refresh()
        else:
            workspace._geology_evidence_dialog.findChild(QComboBox, "interpretation-geology-evidence-select").setCurrentIndex(1)
    calls = []
    def capture(_report, _dataset, path, **kwargs):
        calls.append(kwargs)
        return Path(path)
    monkeypatch.setattr(readable, "export_readable_hydrocarbon_interpretation_xlsx", capture)
    workspace._export_xlsx()
    assert errors == []
    assert len(calls) == 1
    assert "geology_evidence" not in calls[0]
    workspace.close()


def _assert_change_preserves_excel(qapp, monkeypatch, tmp_path, phase, change):
    workspace, session, errors = _prepare(qapp, monkeypatch, tmp_path)
    _approve(workspace, "excel")
    target = tmp_path / "report.xlsx"
    target.write_bytes(b"previous workbook")
    def mutate():
        if change == "geology":
            session.current_well.cuttings[0].description = "Changed after confirmation"
        elif change == "threshold":
            workspace.threshold.setValue(workspace.threshold.value() + 1)
        elif change == "language":
            workspace.report_output_language.setCurrentIndex(workspace.report_output_language.findData(AppLanguage.RU))
        else:
            session.current_dataset.dataset_id = "changed-source"
    if phase == "file_dialog":
        def choose(*_):
            mutate()
            return target
        monkeypatch.setattr(workspace, "_choose_target", choose)
    else:
        original = workspace._update_report_export_progress
        def progress(stage, current, total):
            original(stage, current, total)
            if current == int(phase.rsplit("_", 1)[1]):
                mutate()
        monkeypatch.setattr(workspace, "_update_report_export_progress", progress)
    workspace._export_xlsx()
    assert len(errors) == 1
    assert workspace._geology_excel_evidence == ()
    assert target.read_bytes() == b"previous workbook"
    assert not list(tmp_path.glob(".report-*.xlsx"))
    workspace.close()


@pytest.mark.parametrize("change", ("geology", "threshold", "language", "dataset"))
def test_file_dialog_changes_preserve_excel(qapp, monkeypatch, tmp_path, change):
    _assert_change_preserves_excel(qapp, monkeypatch, tmp_path, "file_dialog", change)


@pytest.mark.parametrize("change", ("geology", "threshold", "language", "dataset"))
def test_intermediate_progress_changes_preserve_excel(qapp, monkeypatch, tmp_path, change):
    _assert_change_preserves_excel(qapp, monkeypatch, tmp_path, "progress_15", change)


@pytest.mark.parametrize("change", ("geology", "threshold", "language", "dataset"))
def test_precommit_progress_changes_preserve_excel(qapp, monkeypatch, tmp_path, change):
    _assert_change_preserves_excel(qapp, monkeypatch, tmp_path, "progress_95", change)


def test_oversized_observation_from_ui_never_truncates_existing_excel(qapp, monkeypatch, tmp_path):
    workspace, session, errors = _prepare(qapp, monkeypatch, tmp_path)
    session.current_well.cuttings[0].description = "Long saved observation " * 2000
    workspace.geology_evidence_button.click()
    qapp.processEvents()
    _approve(workspace, "excel")
    assert workspace._geology_excel_evidence
    target = tmp_path / "report.xlsx"
    target.write_bytes(b"previous workbook")
    workspace._export_xlsx()
    assert len(errors) == 1
    assert "cell text limit" in str(errors[0])
    assert target.read_bytes() == b"previous workbook"
    workspace.close()
