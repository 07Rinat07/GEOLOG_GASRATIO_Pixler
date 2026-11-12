"""Explicit UI confirmation transfers only verified combined HTML."""

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QPushButton, QTextBrowser

from geoworkbench.domain.models import LithologyInterval
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.gis_geology_evidence_dialog import GisGeologyEvidenceDialog
from test_gas_interval_gis_review_ui import _with_inserted_gis
from test_gis_interval_compare_ui import _wait_review


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("change", ("none", "before-confirm", "after-confirm", "cancel"))
def test_explicit_combined_html_handoff(qapp, monkeypatch, tmp_path, language, change):
    workspace, session, receiver, dataset = _with_inserted_gis(monkeypatch, tmp_path, language)
    session.current_well.lithology = [LithologyInterval("html-lith", 100, 102, "limestone")]
    key = next(key for key, curve in dataset.curves.items() if curve.metadata.original_mnemonic == "GR")
    source = dataset.curves[key].values.copy()
    dirty = session.dirty
    seen = []

    def inspect(preview):
        assert not preview.confirm_html_button.isEnabled()
        choice = next(preview.curves.item(i) for i in range(preview.curves.count())
                      if preview.curves.item(i).data(Qt.ItemDataRole.UserRole) == key)
        choice.setCheckState(Qt.CheckState.Checked)
        preview.review.click()
        _wait_review(qapp, preview)
        assert preview.confirm_html_button.isEnabled()
        if change == "cancel":
            return QDialog.DialogCode.Rejected
        if change == "before-confirm":
            dataset.curves[key].values[1] = 1.5
        preview.confirm_html_button.click()
        if change == "before-confirm":
            assert preview.confirmed_html_selection is None
            assert not preview.confirm_html_button.isEnabled()
            return QDialog.DialogCode.Rejected
        assert preview.confirmed_html_selection is not None
        if change == "after-confirm":
            dataset.curves[key].values[1] = 1.5
        seen.append(True)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(GisGeologyEvidenceDialog, "exec", inspect)
    try:
        workspace.geology_evidence_button.click()
        parent = workspace._geology_evidence_dialog
        viewer = parent.findChild(QTextBrowser, "interpretation-geology-evidence-content")
        before = viewer.toPlainText()
        parent.findChild(QPushButton, "interpretation-geology-combined-gis").click()
        if change == "none":
            assert seen == [True]
            assert key in viewer.toPlainText() and "API" in viewer.toPlainText()
            assert "html-lith" in viewer.toPlainText()
            np.testing.assert_array_equal(dataset.curves[key].values, source)
        elif change == "after-confirm":
            assert seen == [True]
            assert key not in viewer.toPlainText()
        else:
            assert not seen and viewer.toPlainText() == before
        assert workspace._geology_pdf_evidence == ()
        assert workspace._geology_word_evidence == ()
        assert workspace._geology_excel_evidence == ()
        assert workspace._geology_print_evidence == ()
        assert receiver.curves == {} and session.dirty == dirty
    finally:
        workspace.close()
