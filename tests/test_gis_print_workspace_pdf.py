"""Independent combined GIS print approval through a real temporary PDF."""
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QComboBox, QDialog, QPushButton

from geoworkbench.domain.models import LithologyInterval
from geoworkbench.services.interpretation_gis_interval_evidence_html import gis_interval_evidence_table
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui import interpretation_report_workspace_final as final
from geoworkbench.ui.gis_geology_evidence_dialog import GisGeologyEvidenceDialog
from test_gas_interval_gis_review_ui import _with_inserted_gis
from test_gis_interval_compare_ui import _wait_review
from test_interpretation_geology_evidence_ui_pdf_handoff import (
    _bounded_native_qt as _bounded_native_qt,
    _no_unexpected_modal_message as _no_unexpected_modal_message,
)
from test_interpretation_method_comparison_ui_print_handoff import (
    _AcceptedPrintDialog, _capture_spooled_pdf, _prepare_print,
)


def _prepare(qapp, monkeypatch, tmp_path, language, approval):
    workspace, session, receiver, dataset = _with_inserted_gis(monkeypatch, tmp_path, language)
    session.current_well.lithology = [LithologyInterval("print-lith", 100.0, 102.0, "limestone")]
    key = next(key for key, curve in dataset.curves.items() if curve.metadata.original_mnemonic == "GR")
    _prepare_print(monkeypatch, workspace)
    errors = []
    monkeypatch.setattr(workspace, "_show_export_error", errors.append)

    def inspect(preview):
        assert not preview.confirm_print_button.isEnabled()
        item = next(preview.curves.item(i) for i in range(preview.curves.count())
                    if preview.curves.item(i).data(Qt.ItemDataRole.UserRole) == key)
        item.setCheckState(Qt.CheckState.Checked)
        preview.review.click()
        _wait_review(qapp, preview)
        if approval == "cancel":
            return QDialog.DialogCode.Rejected
        button = {
            "print": preview.confirm_print_button, "html": preview.confirm_html_button,
            "word": preview.confirm_word_button, "pdf": preview.confirm_pdf_button,
            "excel": preview.confirm_excel_button,
        }[approval]
        assert button.isEnabled()
        button.click()
        return preview.result()

    monkeypatch.setattr(GisGeologyEvidenceDialog, "exec", inspect)
    workspace.geology_evidence_button.click()
    workspace._geology_evidence_dialog.findChild(
        QPushButton, "interpretation-geology-combined-gis",
    ).click()
    return workspace, session, receiver, dataset, key, errors


@pytest.mark.parametrize("language", tuple(AppLanguage))
@pytest.mark.parametrize("approval", ("print", "html", "word", "pdf", "excel", "cancel"))
def test_print_operator_approval_reaches_real_pdf(qapp, monkeypatch, tmp_path, language, approval):
    workspace, session, receiver, dataset, key, errors = _prepare(
        qapp, monkeypatch, tmp_path, language, approval,
    )
    try:
        selected = workspace._gis_print_selection
        assert (selected is not None) == (approval == "print")
        assert workspace._geology_print_evidence == ()
        assert workspace._geology_print_field_selection is None
        before = dataset.curves[key].values.copy()
        printed = _capture_spooled_pdf(monkeypatch)
        paths = []
        renderer = final.export_hydrocarbon_interpretation_pdf

        def capture(report, path, **kwargs):
            paths.append(Path(path))
            if selected is not None:
                assert kwargs["gis_evidence"] == selected.evidence
                assert kwargs["geology_evidence"] == (selected.evidence.geology,)
            else:
                assert "gis_evidence" not in kwargs
            return renderer(report, path, **kwargs)

        monkeypatch.setattr(final, "export_hydrocarbon_interpretation_pdf", capture)
        workspace._print_report()
        assert not errors and len(printed) == 1
        pages, text, content = printed[0]
        assert pages and content.startswith(b"%PDF")
        if selected is not None:
            projection = gis_interval_evidence_table(selected.evidence, language)
            assert projection.title in text
            assert "print-lith" in text
        else:
            assert "print-lith" not in text
        assert paths and all(not path.exists() for path in paths)
        assert receiver.curves == {} and session.current_dataset is dataset
        np.testing.assert_array_equal(dataset.curves[key].values, before)
    finally:
        workspace.close()


@pytest.mark.parametrize("phase", ("identity", "driver", "queued"))
@pytest.mark.parametrize("change", ("curve", "candidate", "geology"))
def test_changed_print_source_never_spools(qapp, monkeypatch, tmp_path, phase, change):
    workspace, session, _, dataset, key, errors = _prepare(
        qapp, monkeypatch, tmp_path, AppLanguage.EN, "print",
    )
    try:
        assert workspace._gis_print_selection is not None
        printed = _capture_spooled_pdf(monkeypatch)

        def mutate():
            if change == "curve":
                dataset.curves[key].values[1] = 1.5
            elif change == "geology":
                session.current_well.lithology = [LithologyInterval("changed", 100.0, 102.0, "sandstone")]
            else:
                workspace._geology_evidence_dialog.findChild(
                    QComboBox, "interpretation-geology-evidence-select",
                ).setCurrentIndex(1)

        if phase == "identity":
            original = workspace._select_report_identity

            def identity(report):
                mutate()
                return original(report)

            monkeypatch.setattr(workspace, "_select_report_identity", identity)
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
        assert len(errors) == 1 and printed == []
        assert workspace._gis_print_selection is None
    finally:
        workspace.close()


def test_changed_curve_after_first_page_stops_remaining_print(qapp, monkeypatch, tmp_path):
    workspace, _, _, dataset, key, errors = _prepare(
        qapp, monkeypatch, tmp_path, AppLanguage.EN, "print",
    )
    try:
        sent = []

        def spool(path, _printer, pages, **kwargs):
            assert Path(path).read_bytes().startswith(b"%PDF")
            assert kwargs["cancel_requested"]() is False
            sent.append(tuple(pages)[0])
            dataset.curves[key].values[1] = 1.5
            assert kwargs["cancel_requested"]() is True
            return False

        monkeypatch.setattr(final, "print_pdf_page_selection", spool)
        workspace._print_report()
        assert not errors and len(sent) == 1
        assert workspace._gis_print_selection is None
        assert "Printing was stopped" in workspace.status.text()
    finally:
        workspace.close()


def test_separate_geology_replaces_only_print_approval(qapp, monkeypatch, tmp_path):
    workspace, _, _, _, _, _ = _prepare(qapp, monkeypatch, tmp_path, AppLanguage.EN, "print")
    try:
        assert workspace._gis_print_selection is not None
        workspace._geology_evidence_dialog.findChild(
            QPushButton, "interpretation-geology-include-in-print",
        ).click()
        assert workspace._gis_print_selection is None
        assert len(workspace._geology_print_evidence) == 1
    finally:
        workspace.close()
