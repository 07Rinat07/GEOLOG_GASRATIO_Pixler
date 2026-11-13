"""Independent Word approval from an actual combined GIS review."""
from dataclasses import replace

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from geoworkbench.services.interpretation_gis_evidence_handoff import (
    confirm_gis_geology_selection, verified_gis_geology_handoff,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.gis_geology_evidence_dialog import GisGeologyEvidenceDialog
from test_gis_interval_compare_ui import _wait_review
from test_interpretation_gis_evidence_handoff import _reviewed


@pytest.mark.parametrize("language", tuple(AppLanguage))
@pytest.mark.parametrize("action", ("word", "html", "changed", "wrong-target", "uncheck", "cancel"))
def test_combined_confirmation_is_explicit_and_target_specific(
    qapp, monkeypatch, tmp_path, language, action,
):
    session, receiver, dataset, key, report, _, _ = _reviewed(monkeypatch, tmp_path)
    before = dataset.curves[key].values.copy()
    dirty = session.dirty
    source_key = ("word-preview", report.dataset_id)

    def confirm_html(evidence, snapshot):
        return confirm_gis_geology_selection(
            session, report, replace(report), evidence, snapshot, source_key=source_key, target="html",
        )

    def confirm_word(evidence, snapshot):
        return confirm_gis_geology_selection(
            session, report, replace(report), evidence, snapshot, source_key=source_key,
            target="html" if action == "wrong-target" else "word",
        )

    dialog = GisGeologyEvidenceDialog(
        session, dataset, (100.0, 102.0), lambda: (100.0, 102.0),
        language=language, confirm_html=confirm_html, confirm_word=confirm_word,
    )
    try:
        assert not dialog.confirm_word_button.isHidden()
        assert not dialog.confirm_word_button.isEnabled()
        assert not dialog.confirm_html_button.isEnabled()
        item = next(
            dialog.curves.item(i) for i in range(dialog.curves.count())
            if dialog.curves.item(i).data(Qt.ItemDataRole.UserRole) == key
        )
        item.setCheckState(Qt.CheckState.Checked)
        dialog.review.click()
        _wait_review(qapp, dialog)
        assert dialog.confirm_word_button.isEnabled()
        assert dialog.confirm_html_button.isEnabled()
        assert dialog.confirmed_word_selection is None
        if action == "changed":
            dataset.curves[key].values[1] = 1.5
        if action == "uncheck":
            item.setCheckState(Qt.CheckState.Unchecked)
            assert not dialog.confirm_word_button.isEnabled()
        elif action == "cancel":
            dialog.reject()
        elif action == "html":
            dialog.confirm_html_button.click()
        else:
            dialog.confirm_word_button.click()
        if action == "word":
            selected = dialog.confirmed_word_selection
            assert selected is not None and selected.target == "word"
            assert dialog.confirmed_html_selection is None
            assert dialog.result() == QDialog.DialogCode.Accepted
            assert verified_gis_geology_handoff(
                session, report, replace(report), selected, source_key=source_key, target="word",
            ) == selected.evidence
        elif action == "html":
            assert dialog.confirmed_html_selection is not None
            assert dialog.confirmed_word_selection is None
        else:
            assert dialog.confirmed_word_selection is None
            assert dialog.confirmed_html_selection is None
            assert dialog.result() != QDialog.DialogCode.Accepted
            if action in ("changed", "wrong-target", "uncheck"):
                assert not dialog.confirm_word_button.isEnabled()
        if action != "changed":
            np.testing.assert_array_equal(dataset.curves[key].values, before)
        assert session.dirty == dirty and receiver.curves == {}
    finally:
        if dialog._worker is not None:
            _wait_review(qapp, dialog)
        dialog.close()


def test_word_confirmation_not_available_without_explicit_callback(qapp, monkeypatch, tmp_path):
    session, _, dataset, _, _, _, _ = _reviewed(monkeypatch, tmp_path)
    dialog = GisGeologyEvidenceDialog(
        session, dataset, (100.0, 102.0), lambda: (100.0, 102.0),
    )
    try:
        assert dialog.confirm_word_button.isHidden()
        assert not dialog.confirm_word_button.isEnabled()
    finally:
        dialog.close()
