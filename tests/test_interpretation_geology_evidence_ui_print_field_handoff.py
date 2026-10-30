"""Source-bound operator-measured fields through the system print PDF and spooler.

These Qt tests are process-isolated by the Windows quality gate (#544).
No physical printer is required: a simulated spooler reads the real PDF.
"""
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtWidgets import QComboBox, QDialog, QPushButton

from geoworkbench.services.interpretation_geology_interval_evidence_html import (
    geology_interval_evidence_table,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui import interpretation_report_workspace_final as final
from test_interpretation_geology_evidence_operator_ui import _workspace
from test_interpretation_geology_evidence_ui_pdf_handoff import (
    _bounded_native_qt as _bounded_native_qt,
    _no_unexpected_modal_message as _no_unexpected_modal_message,
)
from test_interpretation_method_comparison_ui_print_handoff import (
    _AcceptedPrintDialog,
    _capture_spooled_pdf,
    _prepare_print,
)


def _prepare(qapp, monkeypatch, language=AppLanguage.EN):
    workspace, session = _workspace(monkeypatch, language)
    _prepare_print(monkeypatch, workspace)
    errors = []
    monkeypatch.setattr(workspace, "_show_export_error", errors.append)
    workspace.geology_evidence_button.click()
    qapp.processEvents()
    dialog = workspace._geology_evidence_dialog
    assert dialog is not None
    chooser = dialog.findChild(
        QComboBox, "interpretation-geology-measured-field-preview",
    )
    button = dialog.findChild(
        QPushButton, "interpretation-geology-confirm-field-print",
    )
    assert chooser is not None and button is not None
    return workspace, session, errors, chooser, button


def _approve(workspace, qapp, chooser, button):
    assert not button.isEnabled()
    chooser.setCurrentIndex(next(
        i for i in range(chooser.count())
        if chooser.itemData(i) == ("calcimetry", "calcite_percent")
    ))
    qapp.processEvents()
    assert button.isEnabled()
    button.click()
    qapp.processEvents()
    approved = workspace._geology_print_field_selection
    assert approved is not None
    assert workspace._geology_print_evidence == ()
    return approved


@pytest.mark.parametrize("language", tuple(AppLanguage))
def test_print_field_approval_reaches_real_printed_pdf(
    qapp, monkeypatch, language,
):
    workspace, session, errors, chooser, button = _prepare(
        qapp, monkeypatch, language,
    )
    approved = _approve(workspace, qapp, chooser, button)
    expected = geology_interval_evidence_table(
        approved.evidence[0], language, fields=approved.fields,
    )
    assert expected.field_coverage_rows
    assert workspace._geology_pdf_field_selection is None
    assert workspace._geology_excel_field_selection is None
    assert workspace._geology_word_field_selection is None
    before = repr(session.current_well)
    printed = _capture_spooled_pdf(monkeypatch)
    observed_kwargs = []
    real_export = final.export_hydrocarbon_interpretation_pdf

    def checked_export(report, path, **kwargs):
        observed_kwargs.append(kwargs)
        assert kwargs["geology_evidence"] == approved.evidence
        assert kwargs["geology_fields"] == approved.fields
        return real_export(report, path, **kwargs)

    monkeypatch.setattr(final, "export_hydrocarbon_interpretation_pdf", checked_export)
    workspace._print_report()
    assert not errors and len(printed) == 1 and len(observed_kwargs) == 1
    pages, text, data = printed[0]
    assert pages and data.startswith(b"%PDF")
    assert expected.field_coverage_title in text
    assert expected.field_coverage_rows[0][0] in text
    assert repr(session.current_well) == before
    workspace.close()


@pytest.mark.parametrize("change", ("field", "candidate", "threshold"))
def test_changed_print_field_confirmation_does_not_leak_to_pdf(
    qapp, monkeypatch, change,
):
    workspace, _, errors, chooser, button = _prepare(qapp, monkeypatch)
    _approve(workspace, qapp, chooser, button)
    if change == "field":
        chooser.setCurrentIndex(next(
            i for i in range(chooser.count())
            if chooser.itemData(i) == ("calcimetry", "dolomite_percent")
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
    assert workspace._geology_print_field_selection is None
    printed = _capture_spooled_pdf(monkeypatch)
    captured = []
    original = final.export_hydrocarbon_interpretation_pdf

    def capture(report, path, **kwargs):
        captured.append(kwargs)
        return original(report, path, **kwargs)

    monkeypatch.setattr(final, "export_hydrocarbon_interpretation_pdf", capture)
    workspace._print_report()
    assert not errors and len(printed) == 1 and len(captured) == 1
    assert "geology_fields" not in captured[0]
    workspace.close()


@pytest.mark.parametrize("phase", ("identity", "layout", "driver"))
@pytest.mark.parametrize("change", ("geology", "dataset", "language"))
def test_stale_print_field_never_reaches_spooler(
    qapp, monkeypatch, phase, change,
):
    workspace, session, errors, chooser, button = _prepare(qapp, monkeypatch)
    _approve(workspace, qapp, chooser, button)
    printed = _capture_spooled_pdf(monkeypatch)

    def mutate():
        if change == "geology":
            session.current_well.cuttings[0].description = "edited after approval"
        elif change == "dataset":
            session.current_dataset.dataset_id = "changed"
        else:
            workspace.report_output_language.setCurrentIndex(
                workspace.report_output_language.findData(AppLanguage.RU),
            )

    if phase == "identity":
        original = workspace._select_report_identity

        def identity(report):
            mutate()
            return original(report)

        monkeypatch.setattr(workspace, "_select_report_identity", identity)
    elif phase == "layout":
        def layout(_dialog):
            mutate()
            return QDialog.DialogCode.Accepted

        monkeypatch.setattr(final.InterpretationPrintLayoutDialog, "exec", layout)
    else:
        class ChangingDialog(_AcceptedPrintDialog):
            def exec(self):
                mutate()
                return QDialog.DialogCode.Accepted

        monkeypatch.setattr(final, "QPrintDialog", ChangingDialog)
    workspace._print_report()
    assert len(errors) == 1
    assert printed == []
    assert workspace._geology_print_field_selection is None
    workspace.close()


@pytest.mark.parametrize("other", ("html", "pdf", "excel", "word", "print_observations"))
def test_other_output_approvals_never_enable_print_measured_fields(
    qapp, monkeypatch, other,
):
    workspace, _, errors, chooser, _ = _prepare(qapp, monkeypatch)
    chooser.setCurrentIndex(next(
        i for i in range(chooser.count())
        if chooser.itemData(i) == ("calcimetry", "calcite_percent")
    ))
    qapp.processEvents()
    names = {
        "html": "interpretation-geology-confirm-field-html",
        "pdf": "interpretation-geology-confirm-field-pdf",
        "excel": "interpretation-geology-confirm-field-excel",
        "word": "interpretation-geology-confirm-field-word",
        "print_observations": "interpretation-geology-include-in-print",
    }
    # Word field confirmation is only visible on main after merging PR #794.
    pressed = workspace._geology_evidence_dialog.findChild(
        QPushButton, names[other],
    )
    assert pressed is not None
    pressed.click()
    qapp.processEvents()
    assert workspace._geology_print_field_selection is None
    printed = _capture_spooled_pdf(monkeypatch)
    original = final.export_hydrocarbon_interpretation_pdf
    kwargs_seen = []

    def capture(report, path, **kwargs):
        kwargs_seen.append(kwargs)
        return original(report, path, **kwargs)

    monkeypatch.setattr(final, "export_hydrocarbon_interpretation_pdf", capture)
    workspace._print_report()
    assert not errors and len(printed) == 1 and len(kwargs_seen) == 1
    assert "geology_fields" not in kwargs_seen[0]
    workspace.close()


def test_print_field_change_after_first_page_cancels_remaining_spool(
    qapp, monkeypatch,
):
    workspace, session, errors, chooser, button = _prepare(qapp, monkeypatch)
    _approve(workspace, qapp, chooser, button)
    events = []

    def spool(source, _printer, pages, **kwargs):
        assert Path(source).read_bytes().startswith(b"%PDF")
        assert kwargs["cancel_requested"]() is False
        events.append(tuple(pages)[0])
        session.current_well.cuttings[0].description = "changed after first page"
        assert kwargs["cancel_requested"]() is True
        return False

    monkeypatch.setattr(final, "print_pdf_page_selection", spool)
    workspace._print_report()
    assert not errors
    assert len(events) == 1
    assert workspace._geology_print_field_selection is None
    workspace.close()
