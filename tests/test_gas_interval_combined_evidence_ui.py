"""Production gas interval handoff to explicit combined evidence preview."""

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QListWidgetItem, QMessageBox, QPushButton

from geoworkbench.domain.models import LithologyInterval
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.gis_geology_evidence_dialog import GisGeologyEvidenceDialog
from test_gas_interval_gis_review_ui import _with_inserted_gis
from test_interpretation_geology_evidence_operator_ui import _workspace


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("selected_index", (0, 1))
def test_combined_preview_is_explicit_same_md_and_read_only(
    qapp, monkeypatch, tmp_path, language, selected_index,
):
    workspace, session, receiver, dataset = _with_inserted_gis(monkeypatch, tmp_path, language)
    session.current_well.lithology = [LithologyInterval("lith-test", 100.0, 102.0, "limestone")]
    key = next(key for key, curve in dataset.curves.items() if curve.metadata.original_mnemonic == "GR")
    dataset.curves[key].values[1] = np.nan
    before = dataset.curves[key].values.copy()
    dirty = session.dirty
    seen = []

    def inspect(dialog):
        assert dialog.dataset is dataset
        assert dialog.bounds == ((100.0, 102.0) if selected_index == 0 else (101.0, 102.0))
        assert dialog.viewer.toPlainText() == ""
        dialog.review.click()
        assert dialog.status.text() == dialog.words[3]
        choice = next(
            dialog.curves.item(i) for i in range(dialog.curves.count())
            if dialog.curves.item(i).data(Qt.ItemDataRole.UserRole) == key
        )
        choice.setCheckState(Qt.CheckState.Checked)
        dialog.review.click()
        content = dialog.viewer.toPlainText()
        assert "lith-test" in content and key in content and "API" in content
        expected_bounds = "0.0–2.0" if selected_index == 0 else "2.0–2.0"
        assert expected_bounds in content
        choice.setCheckState(Qt.CheckState.Unchecked)
        assert dialog.viewer.toPlainText() == ""
        seen.append(True)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(GisGeologyEvidenceDialog, "exec", inspect)
    try:
        workspace.geology_evidence_button.click()
        parent = workspace._geology_evidence_dialog
        parent.findChild(QComboBox, "interpretation-geology-evidence-select").setCurrentIndex(selected_index)
        parent.findChild(QPushButton, "interpretation-geology-combined-gis").click()
        assert seen == [True]
        assert receiver.curves == {} and session.dirty == dirty
        assert workspace._geology_pdf_evidence == () and workspace._geology_word_evidence == ()
        np.testing.assert_array_equal(dataset.curves[key].values, before)
        assert QApplication.overrideCursor() is None
    finally:
        workspace.close()


def test_combined_preview_rejects_changed_gas_candidate_after_open(qapp, monkeypatch, tmp_path):
    workspace, _, _, dataset = _with_inserted_gis(monkeypatch, tmp_path, AppLanguage.EN)
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: messages.append(args[2]))

    def inspect(dialog):
        dialog.curves.item(0).setCheckState(Qt.CheckState.Checked)
        dataset.curves["c1"].values[0] = 99.0
        dialog.review.click()
        assert not dialog.viewer.toPlainText()
        assert dialog.status.text() == dialog.words[4]
        assert messages and "changed" in messages[-1]
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(GisGeologyEvidenceDialog, "exec", inspect)
    try:
        workspace.geology_evidence_button.click()
        workspace._geology_evidence_dialog.findChild(
            QPushButton, "interpretation-geology-combined-gis",
        ).click()
        assert messages
    finally:
        workspace.close()


def test_combined_preview_hidden_without_eligible_gis(qapp, monkeypatch):
    workspace, _ = _workspace(monkeypatch)
    try:
        workspace.geology_evidence_button.click()
        assert workspace._geology_evidence_dialog.findChild(
            QPushButton, "interpretation-geology-combined-gis",
        ).isHidden()
    finally:
        workspace.close()


def test_preview_rejects_more_than_eight_selected_curves(qapp, monkeypatch, tmp_path):
    from geoworkbench.ui import gis_geology_evidence_dialog as module

    workspace, session, _, dataset = _with_inserted_gis(monkeypatch, tmp_path, AppLanguage.EN)
    preview = GisGeologyEvidenceDialog(
        session, dataset, (100.0, 102.0), lambda: (100.0, 102.0),
        language=AppLanguage.EN,
    )
    monkeypatch.setattr(
        module, "review_gas_geology_gis_interval",
        lambda *args, **kwargs: pytest.fail("Invalid selection must not run the review"),
    )
    try:
        for i in range(9):
            item = QListWidgetItem(f"extra-{i}")
            item.setData(Qt.ItemDataRole.UserRole, f"extra-{i}")
            item.setCheckState(Qt.CheckState.Checked)
            preview.curves.addItem(item)
        preview.review.click()
        assert preview.status.text() == preview.words[3]
        assert not preview.viewer.toPlainText()
    finally:
        preview.close()
        workspace.close()


def test_preview_drops_completed_result_when_candidate_changes_during_review(
    qapp, monkeypatch, tmp_path,
):
    from geoworkbench.ui import gis_geology_evidence_dialog as module

    workspace, session, _, dataset = _with_inserted_gis(monkeypatch, tmp_path, AppLanguage.EN)
    valid = [True]
    preview = GisGeologyEvidenceDialog(
        session, dataset, (100.0, 102.0),
        lambda: (100.0, 102.0) if valid[0] else None,
        language=AppLanguage.EN,
    )
    original = module.review_gas_geology_gis_interval

    def change_candidate(*args, **kwargs):
        result = original(*args, **kwargs)
        valid[0] = False
        return result

    monkeypatch.setattr(module, "review_gas_geology_gis_interval", change_candidate)
    try:
        preview.curves.item(0).setCheckState(Qt.CheckState.Checked)
        preview.review.click()
        assert preview.status.text() == preview.words[4]
        assert not preview.viewer.toPlainText()
        assert QApplication.overrideCursor() is None
    finally:
        preview.close()
        workspace.close()
