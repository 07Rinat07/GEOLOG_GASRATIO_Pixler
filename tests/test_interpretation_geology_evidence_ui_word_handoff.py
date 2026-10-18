"""Separate operator approval and current-source handoff to production Word."""
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QComboBox, QPushButton

from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.interpretation_geology_interval_evidence_html import geology_interval_evidence_table
from geoworkbench.ui import interpretation_report_workspace_drilling as drilling
from test_interpretation_geology_evidence_operator_ui import _workspace
from test_interpretation_method_comparison_ui_docx_handoff import _mock_report_details_dialog
from test_interpretation_geology_evidence_ui_pdf_handoff import (
    _bounded_native_qt as _bounded_native_qt,
    _no_unexpected_modal_message as _no_unexpected_modal_message,
)


def _prepare(qapp, monkeypatch, tmp_path, language=AppLanguage.EN):
    workspace, session = _workspace(monkeypatch, language)
    _mock_report_details_dialog(monkeypatch, workspace)
    target = tmp_path / "selected.docx"
    monkeypatch.setattr(workspace, "_choose_target", lambda *_: target)
    monkeypatch.setattr(workspace, "_show_export_success", lambda *_: None)
    workspace.geology_evidence_button.click()
    qapp.processEvents()
    dialog = workspace._geology_evidence_dialog
    assert dialog is not None
    approve = dialog.findChild(QPushButton, "interpretation-geology-include-in-word")
    assert approve is not None
    return workspace, session, target, approve


@pytest.mark.parametrize("language", tuple(AppLanguage))
def test_separate_word_approval_reaches_real_document(qapp, monkeypatch, tmp_path, language):
    workspace, _, target, approve = _prepare(qapp, monkeypatch, tmp_path, language)
    assert workspace._geology_word_evidence == ()
    approve.click()
    selected = workspace._geology_word_evidence
    assert len(selected) == 1
    assert workspace._geology_pdf_evidence == ()
    errors = []
    monkeypatch.setattr(workspace, "_show_export_error", errors.append)
    workspace._export_docx()
    assert errors == []
    with ZipFile(target) as archive:
        text = " ".join(ET.fromstring(archive.read("word/document.xml")).itertext())
    projection = geology_interval_evidence_table(selected[0], language)
    assert projection.title in text
    for row in projection.rows:
        for cell in row:
            assert cell in text
    workspace.close()


@pytest.mark.parametrize("action", ("view", "pdf_only", "switch_candidate", "refresh"))
def test_no_word_approval_passes_no_new_kwargs(qapp, monkeypatch, tmp_path, action):
    workspace, _, _, approve = _prepare(qapp, monkeypatch, tmp_path)
    if action == "pdf_only":
        workspace._geology_evidence_dialog.findChild(
            QPushButton, "interpretation-geology-include-in-pdf",
        ).click()
    elif action in {"switch_candidate", "refresh"}:
        approve.click()
        if action == "refresh":
            workspace.refresh()
        else:
            workspace._geology_evidence_dialog.findChild(
                QComboBox, "interpretation-geology-evidence-select",
            ).setCurrentIndex(1)
    calls = []
    def capture(_report, target, **kwargs):
        calls.append(kwargs)
        return Path(target)
    monkeypatch.setattr(drilling, "export_polished_hydrocarbon_interpretation_docx", capture)
    workspace._export_docx()
    assert len(calls) == 1
    assert "geology_evidence" not in calls[0]
    workspace.close()


@pytest.mark.parametrize("change", ("geology", "threshold", "language", "dataset"))
def test_changes_in_dialogs_preserve_existing_document(qapp, monkeypatch, tmp_path, change):
    workspace, session, target, approve = _prepare(qapp, monkeypatch, tmp_path)
    approve.click()
    target.write_bytes(b"previous document")
    original = workspace._select_report_identity
    def mutate(report):
        if change == "geology":
            session.current_well.cuttings[0].description = "Changed after selection"
        elif change == "threshold":
            QTimer.singleShot(0, lambda: workspace.threshold.setValue(workspace.threshold.value() + 1))
        elif change == "language":
            workspace.report_output_language.setCurrentIndex(
                workspace.report_output_language.findData(AppLanguage.RU),
            )
        else:
            session.current_dataset.dataset_id = "foreign-dataset"
        return original(report)
    monkeypatch.setattr(workspace, "_select_report_identity", mutate)
    errors = []
    monkeypatch.setattr(workspace, "_show_export_error", errors.append)
    workspace._export_docx()
    assert len(errors) == 1
    assert target.read_bytes() == b"previous document"
    assert workspace._geology_word_evidence == ()
    workspace.close()
