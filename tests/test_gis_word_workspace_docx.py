"""Operator-approved combined observations reach the production Word exporter."""
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QDialog, QPushButton

from geoworkbench.domain.models import LithologyInterval
from geoworkbench.services.interpretation_gis_interval_evidence_html import gis_interval_evidence_table
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.gis_geology_evidence_dialog import GisGeologyEvidenceDialog
from test_gas_interval_gis_review_ui import _with_inserted_gis
from test_gis_interval_compare_ui import _wait_review
from test_interpretation_method_comparison_ui_docx_handoff import _mock_report_details_dialog
from test_interpretation_geology_evidence_ui_pdf_handoff import (
    _bounded_native_qt as _bounded_native_qt,
    _no_unexpected_modal_message as _no_unexpected_modal_message,
)


def _prepare(qapp, monkeypatch, tmp_path, language, approval):
    workspace, session, receiver, dataset = _with_inserted_gis(monkeypatch, tmp_path, language)
    session.current_well.lithology = [LithologyInterval("word-lith", 100.0, 102.0, "limestone")]
    key = next(key for key, curve in dataset.curves.items() if curve.metadata.original_mnemonic == "GR")
    target = tmp_path / "gis.docx"
    _mock_report_details_dialog(monkeypatch, workspace)
    monkeypatch.setattr(workspace, "_choose_target", lambda *_: target)
    monkeypatch.setattr(workspace, "_show_export_success", lambda *_: None)

    def inspect(preview):
        assert not preview.confirm_word_button.isEnabled()
        item = next(preview.curves.item(i) for i in range(preview.curves.count())
                    if preview.curves.item(i).data(Qt.ItemDataRole.UserRole) == key)
        item.setCheckState(Qt.CheckState.Checked)
        preview.review.click()
        _wait_review(qapp, preview)
        if approval == "cancel":
            return QDialog.DialogCode.Rejected
        button = preview.confirm_word_button if approval == "word" else preview.confirm_html_button
        assert button.isEnabled()
        button.click()
        return preview.result()

    monkeypatch.setattr(GisGeologyEvidenceDialog, "exec", inspect)
    workspace.geology_evidence_button.click()
    dialog = workspace._geology_evidence_dialog
    dialog.findChild(QPushButton, "interpretation-geology-combined-gis").click()
    return workspace, session, receiver, dataset, key, target


@pytest.mark.parametrize("language", tuple(AppLanguage))
@pytest.mark.parametrize("approval", ("word", "html", "cancel"))
def test_explicit_word_confirmation_reaches_real_docx(
    qapp, monkeypatch, tmp_path, language, approval,
):
    workspace, session, receiver, dataset, key, target = _prepare(
        qapp, monkeypatch, tmp_path, language, approval,
    )
    try:
        selected = workspace._gis_word_selection
        assert (selected is not None) == (approval == "word")
        assert workspace._geology_word_evidence == ()
        assert workspace._geology_pdf_evidence == ()
        assert workspace._geology_excel_evidence == ()
        assert workspace._geology_print_evidence == ()
        before = dataset.curves[key].values.copy()
        errors = []
        monkeypatch.setattr(workspace, "_show_export_error", errors.append)
        workspace._export_docx()
        assert errors == []
        with ZipFile(target) as archive:
            content = " ".join(ET.fromstring(archive.read("word/document.xml")).itertext())
        if selected is not None:
            projection = gis_interval_evidence_table(selected.evidence, language)
            assert projection.title in content and projection.notice in content
            assert "word-lith" in content
            for row in projection.rows:
                for cell in row:
                    assert cell in content
        else:
            assert "word-lith" not in content
        assert receiver.curves == {}
        np.testing.assert_array_equal(dataset.curves[key].values, before)
        assert session.current_dataset is dataset
    finally:
        workspace.close()


@pytest.mark.parametrize("change", ("curve", "gas", "geology", "candidate"))
def test_changed_word_approval_cannot_replace_existing_file(qapp, monkeypatch, tmp_path, change):
    workspace, session, _, dataset, key, target = _prepare(
        qapp, monkeypatch, tmp_path, AppLanguage.EN, "word",
    )
    try:
        assert workspace._gis_word_selection is not None
        target.write_bytes(b"previous approved document")
        original = workspace._select_report_identity

        def mutate(report):
            if change == "curve":
                dataset.curves[key].values[1] = 1.5
            elif change == "gas":
                dataset.curves["c1"].values[0] = 99.0
            elif change == "geology":
                session.current_well.lithology = [LithologyInterval("changed-lith", 100.0, 102.0, "sandstone")]
            else:
                workspace._geology_evidence_dialog.findChild(
                    QComboBox, "interpretation-geology-evidence-select",
                ).setCurrentIndex(1)
            return original(report)

        monkeypatch.setattr(workspace, "_select_report_identity", mutate)
        errors = []
        monkeypatch.setattr(workspace, "_show_export_error", errors.append)
        workspace._export_docx()
        assert len(errors) == 1
        assert target.read_bytes() == b"previous approved document"
        assert workspace._gis_word_selection is None
    finally:
        workspace.close()


def test_separate_geology_approval_replaces_combined_word_approval(qapp, monkeypatch, tmp_path):
    workspace, _, _, _, _, _ = _prepare(qapp, monkeypatch, tmp_path, AppLanguage.EN, "word")
    try:
        assert workspace._gis_word_selection is not None
        workspace._geology_evidence_dialog.findChild(
            QPushButton, "interpretation-geology-include-in-word",
        ).click()
        assert workspace._gis_word_selection is None
        assert len(workspace._geology_word_evidence) == 1
    finally:
        workspace.close()
