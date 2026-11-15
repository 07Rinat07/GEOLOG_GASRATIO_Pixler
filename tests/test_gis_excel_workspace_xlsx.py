"""Operator-specific GIS Excel approval reaches the real workbook."""
import numpy as np
from openpyxl import load_workbook
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QDialog, QPushButton

from geoworkbench.data import hydrocarbon_interpretation_export_readable as readable
from geoworkbench.domain.models import LithologyInterval
from geoworkbench.services.interpretation_gis_interval_evidence_html import gis_interval_evidence_table
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.gis_geology_evidence_dialog import GisGeologyEvidenceDialog
from test_gas_interval_gis_review_ui import _with_inserted_gis
from test_gis_interval_compare_ui import _wait_review
from test_interpretation_geology_evidence_ui_pdf_handoff import (
    _bounded_native_qt as _bounded_native_qt,
    _no_unexpected_modal_message as _no_unexpected_modal_message,
)


def _prepare(qapp, monkeypatch, tmp_path, language, approval):
    workspace, session, receiver, dataset = _with_inserted_gis(monkeypatch, tmp_path, language)
    session.current_well.lithology = [LithologyInterval("excel-lith", 100.0, 102.0, "limestone")]
    key = next(key for key, curve in dataset.curves.items() if curve.metadata.original_mnemonic == "GR")
    target = tmp_path / "gis.xlsx"
    monkeypatch.setattr(workspace, "_choose_target", lambda *_: target)
    monkeypatch.setattr(workspace, "_show_export_success", lambda *_: None)

    def inspect(preview):
        assert not preview.confirm_excel_button.isEnabled()
        item = next(preview.curves.item(i) for i in range(preview.curves.count())
                    if preview.curves.item(i).data(Qt.ItemDataRole.UserRole) == key)
        item.setCheckState(Qt.CheckState.Checked)
        preview.review.click()
        _wait_review(qapp, preview)
        if approval == "cancel":
            return QDialog.DialogCode.Rejected
        button = {"excel": preview.confirm_excel_button, "html": preview.confirm_html_button,
                  "word": preview.confirm_word_button, "pdf": preview.confirm_pdf_button}[approval]
        assert button.isEnabled()
        button.click()
        return preview.result()

    monkeypatch.setattr(GisGeologyEvidenceDialog, "exec", inspect)
    workspace.geology_evidence_button.click()
    workspace._geology_evidence_dialog.findChild(
        QPushButton, "interpretation-geology-combined-gis",
    ).click()
    return workspace, session, receiver, dataset, key, target


@pytest.mark.parametrize("language", tuple(AppLanguage))
@pytest.mark.parametrize("approval", ("excel", "html", "word", "pdf", "cancel"))
def test_excel_operator_approval_reaches_real_workbook(qapp, monkeypatch, tmp_path, language, approval):
    workspace, session, receiver, dataset, key, target = _prepare(
        qapp, monkeypatch, tmp_path, language, approval,
    )
    try:
        selection = workspace._gis_excel_selection
        assert (selection is not None) == (approval == "excel")
        assert (workspace._gis_word_selection is not None) == (approval == "word")
        assert (workspace._gis_pdf_selection is not None) == (approval == "pdf")
        assert workspace._geology_excel_evidence == ()
        assert workspace._geology_excel_field_selection is None
        before = dataset.curves[key].values.copy()
        errors = []
        monkeypatch.setattr(workspace, "_show_export_error", errors.append)
        workspace._export_xlsx()
        assert errors == []
        workbook = load_workbook(target)
        try:
            name = readable._GIS_EVIDENCE_SHEET_NAMES[language]
            geology_name = readable._GEOLOGY_EVIDENCE_SHEET_NAMES[language]
            if selection is None:
                assert name not in workbook.sheetnames and geology_name not in workbook.sheetnames
            else:
                projection = gis_interval_evidence_table(selection.evidence, language)
                sheet = workbook[name]
                assert sheet["A1"].value == projection.title
                assert tuple(tuple(cell.value for cell in row)
                             for row in sheet.iter_rows(min_row=4)) == projection.rows
                assert geology_name in workbook.sheetnames
        finally:
            workbook.close()
        assert receiver.curves == {} and session.current_dataset is dataset
        np.testing.assert_array_equal(dataset.curves[key].values, before)
    finally:
        workspace.close()


@pytest.mark.parametrize("change", ("curve", "candidate", "geology"))
def test_stale_excel_approval_preserves_previous_workbook(qapp, monkeypatch, tmp_path, change):
    workspace, session, _, dataset, key, target = _prepare(
        qapp, monkeypatch, tmp_path, AppLanguage.EN, "excel",
    )
    try:
        assert workspace._gis_excel_selection is not None
        target.write_bytes(b"previous workbook")

        def choose(*_):
            if change == "curve":
                dataset.curves[key].values[1] = 1.5
            elif change == "geology":
                session.current_well.lithology = [LithologyInterval("changed", 100.0, 102.0, "sandstone")]
            else:
                workspace._geology_evidence_dialog.findChild(
                    QComboBox, "interpretation-geology-evidence-select",
                ).setCurrentIndex(1)
            return target

        monkeypatch.setattr(workspace, "_choose_target", choose)
        errors = []
        monkeypatch.setattr(workspace, "_show_export_error", errors.append)
        workspace._export_xlsx()
        assert len(errors) == 1
        assert target.read_bytes() == b"previous workbook"
        assert workspace._gis_excel_selection is None
    finally:
        workspace.close()


def test_separate_geology_approval_replaces_combined_excel(qapp, monkeypatch, tmp_path):
    workspace, _, _, _, _, _ = _prepare(qapp, monkeypatch, tmp_path, AppLanguage.EN, "excel")
    try:
        assert workspace._gis_excel_selection is not None
        workspace._geology_evidence_dialog.findChild(
            QPushButton, "interpretation-geology-include-in-excel",
        ).click()
        assert workspace._gis_excel_selection is None
        assert len(workspace._geology_excel_evidence) == 1
    finally:
        workspace.close()
