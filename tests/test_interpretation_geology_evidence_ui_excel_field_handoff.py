"""Explicit operator measured-field selection for the real Excel exporter.

Native Qt cases are isolated under the Windows quality runner (issue #544).
"""
from pathlib import Path

from openpyxl import load_workbook
import pytest
from PySide6.QtWidgets import QComboBox, QPushButton

from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.interpretation_geology_interval_evidence_html import (
    geology_interval_evidence_table,
)
from test_interpretation_geology_evidence_operator_ui import _workspace
from test_interpretation_geology_evidence_ui_pdf_handoff import (
    _bounded_native_qt as _bounded_native_qt,
    _no_unexpected_modal_message as _no_unexpected_modal_message,
)


def _prepare(qapp, monkeypatch, tmp_path, language=AppLanguage.EN):
    workspace, session = _workspace(monkeypatch, language)
    target = tmp_path / "selected.xlsx"
    monkeypatch.setattr(workspace, "_choose_target", lambda *_: target)
    monkeypatch.setattr(workspace, "_show_export_success", lambda *_: None)
    workspace.geology_evidence_button.click()
    qapp.processEvents()
    dialog = workspace._geology_evidence_dialog
    assert dialog is not None
    field = dialog.findChild(
        QComboBox, "interpretation-geology-measured-field-preview",
    )
    confirm = dialog.findChild(
        QPushButton, "interpretation-geology-confirm-field-excel",
    )
    assert field is not None and confirm is not None
    return workspace, session, target, field, confirm


def _confirm(workspace, qapp, field, confirm):
    assert not confirm.isEnabled()
    field.setCurrentIndex(next(
        index for index in range(field.count())
        if field.itemData(index) == ("calcimetry", "calcite_percent")
    ))
    qapp.processEvents()
    assert confirm.isEnabled()
    confirm.click()
    qapp.processEvents()
    selection = workspace._geology_excel_field_selection
    assert selection is not None
    assert workspace._geology_excel_evidence == ()
    return selection


@pytest.mark.parametrize("language", tuple(AppLanguage))
def test_explicit_excel_field_produces_real_localized_workbook(
    qapp, monkeypatch, tmp_path, language,
):
    workspace, session, target, field, confirm = _prepare(
        qapp, monkeypatch, tmp_path, language,
    )
    selected = _confirm(workspace, qapp, field, confirm)
    assert workspace._geology_pdf_field_selection is None
    assert workspace._geology_html_field_selection is None
    assert workspace._geology_word_evidence == ()
    assert workspace._geology_print_evidence == ()
    before = repr(session.current_well)
    expected = geology_interval_evidence_table(
        selected.evidence[0], language, fields=selected.fields,
    )
    errors = []
    monkeypatch.setattr(workspace, "_show_export_error", errors.append)
    workspace._export_xlsx()
    assert not errors
    workbook = load_workbook(target)
    try:
        sheet = workbook[{
            AppLanguage.EN: "Gas and geology MD",
            AppLanguage.RU: "Газ и геология MD",
            AppLanguage.KK: "Газ және геология MD",
        }[language]]
        rows = list(sheet.values)
        assert expected.field_coverage_title in [row[0] for row in rows]
        assert expected.field_coverage_headings in [
            tuple(row[:len(expected.field_coverage_headings)]) for row in rows
        ]
        for evidence_row in expected.field_coverage_rows:
            assert evidence_row in [
                tuple(row[:len(evidence_row)]) for row in rows
            ]
        assert sheet.auto_filter.ref is None
    finally:
        workbook.close()
    assert repr(session.current_well) == before
    workspace.close()


@pytest.mark.parametrize("change", ("field", "candidate", "threshold"))
def test_excel_field_change_revokes_approval_before_export(
    qapp, monkeypatch, tmp_path, change,
):
    workspace, _, _, field, confirm = _prepare(qapp, monkeypatch, tmp_path)
    _confirm(workspace, qapp, field, confirm)
    if change == "field":
        field.setCurrentIndex(next(
            i for i in range(field.count())
            if field.itemData(i) == ("calcimetry", "dolomite_percent")
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
    assert workspace._geology_excel_field_selection is None
    calls = []

    def capture(_report, _dataset, file_path, **kwargs):
        calls.append(kwargs)
        return Path(file_path)

    from geoworkbench.data import hydrocarbon_interpretation_export_readable as readable
    monkeypatch.setattr(readable, "export_readable_hydrocarbon_interpretation_xlsx", capture)
    workspace._export_xlsx()
    assert len(calls) == 1
    assert "geology_field_selection" not in calls[0]
    assert "geology_source_key" not in calls[0]
    workspace.close()


@pytest.mark.parametrize("change", ("geology", "dataset", "language"))
def test_source_changed_during_excel_target_dialog_preserves_file(
    qapp, monkeypatch, tmp_path, change,
):
    workspace, session, target, field, confirm = _prepare(
        qapp, monkeypatch, tmp_path,
    )
    _confirm(workspace, qapp, field, confirm)
    target.write_bytes(b"approved original workbook")

    def choose(*_args):
        if change == "geology":
            session.current_well.cuttings[0].description = "edited after approval"
        elif change == "dataset":
            session.current_dataset.dataset_id = "unrelated"
        else:
            workspace.report_output_language.setCurrentIndex(
                workspace.report_output_language.findData(AppLanguage.RU),
            )
        return target

    monkeypatch.setattr(workspace, "_choose_target", choose)
    errors = []
    monkeypatch.setattr(workspace, "_show_export_error", errors.append)
    workspace._export_xlsx()
    assert len(errors) == 1
    assert target.read_bytes() == b"approved original workbook"
    assert workspace._geology_excel_field_selection is None
    workspace.close()


@pytest.mark.parametrize("other", ("html", "pdf", "excel_observations"))
def test_other_approvals_never_enable_excel_measured_fields(
    qapp, monkeypatch, tmp_path, other,
):
    workspace, _, _, field, _ = _prepare(qapp, monkeypatch, tmp_path)
    field.setCurrentIndex(next(
        i for i in range(field.count())
        if field.itemData(i) == ("calcimetry", "calcite_percent")
    ))
    qapp.processEvents()
    dialog = workspace._geology_evidence_dialog
    name = {
        "html": "interpretation-geology-confirm-field-html",
        "pdf": "interpretation-geology-confirm-field-pdf",
        "excel_observations": "interpretation-geology-include-in-excel",
    }[other]
    dialog.findChild(QPushButton, name).click()
    qapp.processEvents()
    assert workspace._geology_excel_field_selection is None
    calls = []

    def capture(_report, _dataset, path, **kwargs):
        calls.append(kwargs)
        return Path(path)

    from geoworkbench.data import hydrocarbon_interpretation_export_readable as readable
    monkeypatch.setattr(readable, "export_readable_hydrocarbon_interpretation_xlsx", capture)
    workspace._export_xlsx()
    assert len(calls) == 1
    assert "geology_field_selection" not in calls[0]
    assert "geology_source_key" not in calls[0]
    workspace.close()
