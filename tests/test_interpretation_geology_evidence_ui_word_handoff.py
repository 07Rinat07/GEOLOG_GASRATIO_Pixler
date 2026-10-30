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



def _confirm_measured_word_field(workspace, qapp, field=("calcimetry", "calcite_percent")):
    dialog = workspace._geology_evidence_dialog
    assert dialog is not None
    choice = dialog.findChild(
        QComboBox, "interpretation-geology-measured-field-preview",
    )
    confirm = dialog.findChild(
        QPushButton, "interpretation-geology-confirm-field-word",
    )
    assert choice is not None and confirm is not None
    assert not confirm.isEnabled()
    index = next(
        i for i in range(choice.count()) if choice.itemData(i) == field
    )
    choice.setCurrentIndex(index)
    qapp.processEvents()
    assert confirm.isEnabled()
    confirm.click()
    qapp.processEvents()
    assert workspace._geology_word_field_selection is not None
    assert workspace._geology_word_evidence == ()
    return choice, confirm


@pytest.mark.parametrize("language", tuple(AppLanguage))
def test_explicit_measured_word_field_reaches_real_polished_docx(
    qapp, monkeypatch, tmp_path, language,
):
    workspace, session, target, approve_observations = _prepare(
        qapp, monkeypatch, tmp_path, language,
    )
    session.current_well.cuttings[0].calcite_percent = 0.0
    session.current_well.cuttings[0].dolomite_percent = None
    before = repr(session.current_well)
    choice, confirm = _confirm_measured_word_field(workspace, qapp)
    assert choice.currentData() == ("calcimetry", "calcite_percent")
    assert workspace._geology_pdf_field_selection is None
    assert workspace._geology_html_field_selection is None
    assert workspace._geology_excel_evidence == ()
    assert workspace._geology_print_evidence == ()
    assert approve_observations.isEnabled()
    approved = workspace._geology_word_field_selection
    assert approved is not None
    expected = geology_interval_evidence_table(
        approved.evidence[0], language, fields=approved.fields,
    )
    errors = []
    monkeypatch.setattr(workspace, "_show_export_error", errors.append)
    workspace._export_docx()
    assert errors == []
    assert target.is_file()
    with ZipFile(target) as archive:
        content = " ".join(ET.fromstring(archive.read("word/document.xml")).itertext())
    assert expected.field_coverage_title in content
    for row in expected.field_coverage_rows:
        for cell in row:
            assert cell in content
    assert "1002.00" in content and "1010.00" in content
    assert repr(session.current_well) == before
    workspace.close()


@pytest.mark.parametrize("change", ("field", "candidate", "threshold"))
def test_changed_word_field_approval_is_revoked_before_export(
    qapp, monkeypatch, tmp_path, change,
):
    workspace, _, _, _ = _prepare(qapp, monkeypatch, tmp_path)
    choice, _ = _confirm_measured_word_field(workspace, qapp)
    if change == "field":
        choice.setCurrentIndex(next(
            i for i in range(choice.count())
            if choice.itemData(i) == ("calcimetry", "dolomite_percent")
        ))
    elif change == "candidate":
        selector = workspace._geology_evidence_dialog.findChild(
            QComboBox, "interpretation-geology-evidence-select",
        )
        assert selector is not None
        selector.setCurrentIndex(1)
    else:
        workspace.threshold.setValue(workspace.threshold.value() + 0.5)
    qapp.processEvents()
    assert workspace._geology_word_field_selection is None
    calls = []

    def capture(_report, _target, **kwargs):
        calls.append(kwargs)
        return Path(_target)

    monkeypatch.setattr(drilling, "export_polished_hydrocarbon_interpretation_docx", capture)
    workspace._export_docx()
    assert len(calls) == 1
    assert "geology_field_selection" not in calls[0]
    assert "geology_source_key" not in calls[0]
    workspace.close()


@pytest.mark.parametrize("change", ("geology", "dataset", "language"))
def test_word_measured_field_stale_during_report_dialog_preserves_docx(
    qapp, monkeypatch, tmp_path, change,
):
    workspace, session, target, _ = _prepare(qapp, monkeypatch, tmp_path)
    _confirm_measured_word_field(workspace, qapp)
    target.write_bytes(b"prior operator-approved Word document")
    original = workspace._select_report_identity

    def mutate(report):
        if change == "geology":
            session.current_well.cuttings[0].description = "edited after approval"
        elif change == "dataset":
            session.current_dataset.dataset_id = "unrelated"
        else:
            workspace.report_output_language.setCurrentIndex(
                workspace.report_output_language.findData(AppLanguage.RU),
            )
        return original(report)

    monkeypatch.setattr(workspace, "_select_report_identity", mutate)
    errors = []
    monkeypatch.setattr(workspace, "_show_export_error", errors.append)
    workspace._export_docx()
    assert len(errors) == 1
    assert target.read_bytes() == b"prior operator-approved Word document"
    assert workspace._geology_word_field_selection is None
    workspace.close()


@pytest.mark.parametrize("other_approval", ("html", "pdf", "word_observations"))
def test_other_operator_approvals_never_enable_word_field_export(
    qapp, monkeypatch, tmp_path, other_approval,
):
    workspace, _, _, _ = _prepare(qapp, monkeypatch, tmp_path)
    dialog = workspace._geology_evidence_dialog
    assert dialog is not None
    choice = dialog.findChild(
        QComboBox, "interpretation-geology-measured-field-preview",
    )
    assert choice is not None
    choice.setCurrentIndex(next(
        i for i in range(choice.count())
        if choice.itemData(i) == ("calcimetry", "calcite_percent")
    ))
    qapp.processEvents()
    object_name = {
        "html": "interpretation-geology-confirm-field-html",
        "pdf": "interpretation-geology-confirm-field-pdf",
        "word_observations": "interpretation-geology-include-in-word",
    }[other_approval]
    button = dialog.findChild(QPushButton, object_name)
    assert button is not None
    button.click()
    qapp.processEvents()
    assert workspace._geology_word_field_selection is None
    calls = []

    def capture(_report, target, **kwargs):
        calls.append(kwargs)
        return Path(target)

    monkeypatch.setattr(drilling, "export_polished_hydrocarbon_interpretation_docx", capture)
    workspace._export_docx()
    assert len(calls) == 1
    assert "geology_field_selection" not in calls[0]
    assert "geology_source_key" not in calls[0]
    workspace.close()


def test_word_observation_approval_revokes_previous_field_selection(
    qapp, monkeypatch, tmp_path,
):
    workspace, _, _, approve_observations = _prepare(qapp, monkeypatch, tmp_path)
    _confirm_measured_word_field(workspace, qapp)
    assert workspace._geology_word_field_selection is not None
    approve_observations.click()
    assert workspace._geology_word_field_selection is None
    assert len(workspace._geology_word_evidence) == 1
    workspace.close()
