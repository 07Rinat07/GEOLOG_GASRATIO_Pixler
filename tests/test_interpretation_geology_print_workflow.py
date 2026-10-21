"""Verified measured geology through production system-print preparation."""
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QComboBox, QDialog, QPushButton

from geoworkbench.services.interpretation_geology_interval_evidence_html import geology_interval_evidence_table
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui import interpretation_report_workspace_final as final
from test_interpretation_geology_evidence_operator_ui import _workspace
from test_interpretation_geology_evidence_ui_pdf_handoff import (
    _bounded_native_qt as _bounded_native_qt,
    _no_unexpected_modal_message as _no_unexpected_modal_message,
)
from test_interpretation_method_comparison_ui_print_handoff import (
    _AcceptedPrintDialog, _capture_spooled_pdf, _prepare_print,
)


def _prepare(qapp, monkeypatch, language=AppLanguage.EN):
    workspace, session = _workspace(monkeypatch, language)
    _prepare_print(monkeypatch, workspace)
    errors = []
    monkeypatch.setattr(workspace, "_show_export_error", errors.append)
    workspace.geology_evidence_button.click()
    qapp.processEvents()
    assert workspace._geology_evidence_dialog is not None
    return workspace, session, errors


def _approve(workspace, output="print"):
    button = workspace._geology_evidence_dialog.findChild(QPushButton, "interpretation-geology-include-in-" + output)
    assert button is not None
    button.click()


@pytest.mark.parametrize("language", tuple(AppLanguage))
def test_confirmed_print_contains_current_md_observations(qapp, monkeypatch, language):
    workspace, session, errors = _prepare(qapp, monkeypatch, language)
    dataset = session.current_dataset
    depth = dataset.depth.copy()
    curves = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    _approve(workspace)
    selected = workspace._geology_print_evidence
    assert len(selected) == 1
    assert workspace._geology_pdf_evidence == ()
    assert workspace._geology_word_evidence == ()
    assert workspace._geology_excel_evidence == ()
    printed = _capture_spooled_pdf(monkeypatch)
    paths = []
    renderer = final.export_hydrocarbon_interpretation_pdf
    def observed(report, path, **kwargs):
        paths.append(Path(path))
        assert kwargs["geology_evidence"] == selected
        return renderer(report, path, **kwargs)
    monkeypatch.setattr(final, "export_hydrocarbon_interpretation_pdf", observed)
    workspace._print_report()
    assert errors == []
    assert len(printed) == 1
    pages, text, contents = printed[0]
    assert pages and contents.startswith(b"%PDF")
    assert geology_interval_evidence_table(selected[0], language).title in text
    for item in selected[0].intersections:
        assert item.source_id in text
    assert all(not path.exists() for path in paths)
    np.testing.assert_array_equal(dataset.depth, depth)
    for key, values in curves.items():
        np.testing.assert_array_equal(dataset.curves[key].values, values)
    workspace.close()


@pytest.mark.parametrize("action", ("view", "pdf", "word", "excel", "candidate", "refresh"))
def test_other_output_approvals_do_not_include_geology_in_print(qapp, monkeypatch, action):
    workspace, _, errors = _prepare(qapp, monkeypatch)
    if action in {"pdf", "word", "excel"}:
        _approve(workspace, action)
    elif action in {"candidate", "refresh"}:
        _approve(workspace)
        if action == "refresh":
            workspace.refresh()
        else:
            workspace._geology_evidence_dialog.findChild(QComboBox, "interpretation-geology-evidence-select").setCurrentIndex(1)
    calls = []
    renderer = final.export_hydrocarbon_interpretation_pdf
    def capture(report, path, **kwargs):
        calls.append(kwargs)
        return renderer(report, path, **kwargs)
    monkeypatch.setattr(final, "export_hydrocarbon_interpretation_pdf", capture)
    printed = _capture_spooled_pdf(monkeypatch)
    workspace._print_report()
    assert errors == [] and len(printed) == 1
    assert len(calls) == 1 and "geology_evidence" not in calls[0]
    workspace.close()


def _assert_changes_block_print(qapp, monkeypatch, phase, change):
    workspace, session, errors = _prepare(qapp, monkeypatch)
    _approve(workspace)
    printed = _capture_spooled_pdf(monkeypatch)
    def mutate():
        if change == "geology":
            session.current_well.cuttings[0].description = "Changed after approval"
        elif change == "threshold":
            workspace.threshold.setValue(workspace.threshold.value() + 1)
        elif change == "language":
            workspace.report_output_language.setCurrentIndex(workspace.report_output_language.findData(AppLanguage.RU))
        elif change == "dataset":
            session.current_dataset.dataset_id = "foreign"
        else:
            workspace.report = replace(workspace.report, generated_at="new report")
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
                if phase == "driver":
                    mutate()
                else:
                    QTimer.singleShot(0, mutate)
                return QDialog.DialogCode.Accepted
        monkeypatch.setattr(final, "QPrintDialog", ChangingDialog)
    workspace._print_report()
    assert printed == []
    assert len(errors) == 1
    assert workspace._geology_print_evidence == ()
    workspace.close()


@pytest.mark.parametrize("change", ("geology", "threshold", "language", "dataset", "report"))
def test_changes_in_identity_block_spooling(qapp, monkeypatch, change):
    _assert_changes_block_print(qapp, monkeypatch, "identity", change)


@pytest.mark.parametrize("change", ("geology", "threshold", "language", "dataset", "report"))
def test_changes_in_layout_block_spooling(qapp, monkeypatch, change):
    _assert_changes_block_print(qapp, monkeypatch, "layout", change)


@pytest.mark.parametrize("change", ("geology", "threshold", "language", "dataset", "report"))
def test_changes_in_driver_block_spooling(qapp, monkeypatch, change):
    _assert_changes_block_print(qapp, monkeypatch, "driver", change)


@pytest.mark.parametrize("change", ("geology", "threshold", "language", "dataset", "report"))
def test_queued_changes_before_spool_block_output(qapp, monkeypatch, change):
    _assert_changes_block_print(qapp, monkeypatch, "queued", change)


@pytest.mark.parametrize("change", ("threshold", "candidate"))
def test_source_change_during_spooling_stops_remaining_pages(qapp, monkeypatch, change):
    workspace, _, errors = _prepare(qapp, monkeypatch)
    _approve(workspace)
    sent = []
    def spool(path, _printer, pages, **kwargs):
        assert Path(path).read_bytes().startswith(b"%PDF")
        assert kwargs["cancel_requested"]() is False
        sent.append(tuple(pages)[0])
        if change == "threshold":
            workspace.threshold.setValue(workspace.threshold.value() + 1)
        else:
            workspace._geology_evidence_dialog.findChild(QComboBox, "interpretation-geology-evidence-select").setCurrentIndex(1)
        assert kwargs["cancel_requested"]() is True
        return False
    monkeypatch.setattr(final, "print_pdf_page_selection", spool)
    workspace._print_report()
    assert errors == [] and len(sent) == 1
    assert workspace._geology_print_evidence == ()
    assert "Printing was stopped" in workspace.status.text()
    workspace.close()


def test_driver_cancellation_discards_temporary_pdf(qapp, monkeypatch):
    workspace, _, errors = _prepare(qapp, monkeypatch)
    _approve(workspace)
    printed = _capture_spooled_pdf(monkeypatch)
    paths = []
    renderer = final.export_hydrocarbon_interpretation_pdf
    def observed(report, path, **kwargs):
        paths.append(Path(path))
        return renderer(report, path, **kwargs)
    class CancelledDialog(_AcceptedPrintDialog):
        def exec(self):
            return QDialog.DialogCode.Rejected
    monkeypatch.setattr(final, "QPrintDialog", CancelledDialog)
    monkeypatch.setattr(final, "export_hydrocarbon_interpretation_pdf", observed)
    workspace._print_report()
    assert printed == [] and errors == []
    assert paths and all(not path.exists() for path in paths)
    workspace.close()
