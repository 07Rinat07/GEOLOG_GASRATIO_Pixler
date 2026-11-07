"""Explicit, read-only handoff from a gas interval to its GIS source review."""

from dataclasses import replace

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QMessageBox, QPushButton

from geoworkbench.domain.models import CurveData, CurveMetadata, LithologyInterval
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui import interpretation_report_workspace_legacy as legacy
from geoworkbench.ui.gis_reference_dialog import GisReferenceDialog
from test_gis_external_exact_review import _copy
from test_interpretation_geology_evidence_operator_ui import _candidate, _workspace


def _with_inserted_gis(monkeypatch, tmp_path, language):
    original_builder = legacy.build_hydrocarbon_interpretation_report
    workspace, _ = _workspace(monkeypatch, language)
    session, receiver, _, combined = _copy(monkeypatch, tmp_path)
    combined.curves["c1"] = CurveData(
        CurveMetadata("c1", "C1", "C1", "%", "Methane", combined.dataset_id, "source:las"),
        np.array([1.0, 2.0, 3.0]),
    )
    session.current_dataset_id = combined.dataset_id
    workspace.controller.session = session

    def with_candidates(active_session, **kwargs):
        report = original_builder(active_session, **kwargs)
        marker = float(active_session.current_dataset.curves["c1"].values[0])
        candidates = (
            replace(_candidate(100.0, 102.0), max_primary_value=marker),
            replace(_candidate(101.0, 102.0), max_primary_value=marker),
        )
        return replace(report, candidates=candidates)

    monkeypatch.setattr(legacy, "build_hydrocarbon_interpretation_report", with_candidates)
    return workspace, session, receiver, combined


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("selected_index", [0, 1])
def test_report_opens_inserted_gis_review_for_explicit_selected_interval(
    qapp, monkeypatch, tmp_path, language, selected_index,
):
    workspace, session, receiver, combined = _with_inserted_gis(monkeypatch, tmp_path, language)
    values = combined.curves["c1"].values.copy()
    seen = []

    def inspect(dialog):
        assert dialog.dataset is combined
        assert dialog.fields["top"].text() == ("100" if selected_index == 0 else "101")
        assert dialog.fields["base"].text() == "102"
        assert dialog.method.currentData() is None and dialog.channel.currentData() is None
        dialog.method.setCurrentIndex(1)
        key = next(key for key, curve in combined.curves.items() if curve.metadata.original_mnemonic == "GR")
        dialog.channel.setCurrentIndex(dialog.channel.findData(key))
        dialog.review_interval.click()
        count = 3 if selected_index == 0 else 2
        assert dialog._t("interval_summary", total=count, finite=count, missing=0) in dialog.interval_review_label.text()
        seen.append(True)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(GisReferenceDialog, "exec", inspect)
    try:
        workspace.geology_evidence_button.click()
        dialog = workspace._geology_evidence_dialog
        assert dialog is not None
        button = dialog.findChild(QPushButton, "interpretation-geology-review-gis")
        assert button is not None and not button.isHidden()
        selector = dialog.findChild(QComboBox, "interpretation-geology-evidence-select")
        selector.setCurrentIndex(selected_index)
        button.click()
        assert seen == [True]
        assert session.current_dataset is combined and receiver.curves == {}
        np.testing.assert_array_equal(combined.curves["c1"].values, values)
    finally:
        workspace.close()


def test_gis_action_hidden_without_eligible_source(qapp, monkeypatch):
    workspace, _ = _workspace(monkeypatch)
    try:
        workspace.geology_evidence_button.click()
        dialog = workspace._geology_evidence_dialog
        assert dialog is not None
        assert dialog.findChild(QPushButton, "interpretation-geology-review-gis").isHidden()
    finally:
        workspace.close()


def test_gis_action_hidden_when_insert_provenance_is_not_verified(qapp, monkeypatch, tmp_path):
    workspace, _, _, combined = _with_inserted_gis(monkeypatch, tmp_path, AppLanguage.EN)
    key = next(key for key in combined.parameters if key.startswith("EXTERNAL_LAS_IMPORT_"))
    combined.parameters[key] = "{}"
    try:
        workspace.geology_evidence_button.click()
        dialog = workspace._geology_evidence_dialog
        assert dialog is not None
        assert dialog.findChild(QPushButton, "interpretation-geology-review-gis").isHidden()
    finally:
        workspace.close()


def test_inplace_gas_change_rejects_old_candidate_without_opening_gis(qapp, monkeypatch, tmp_path):
    workspace, _, _, combined = _with_inserted_gis(monkeypatch, tmp_path, AppLanguage.EN)
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: messages.append(args[2]))
    monkeypatch.setattr(GisReferenceDialog, "exec", lambda _dialog: pytest.fail("stale GIS review"))
    try:
        workspace.geology_evidence_button.click()
        dialog = workspace._geology_evidence_dialog
        assert dialog is not None
        combined.curves["c1"].values[0] = 99.0
        dialog.findChild(QPushButton, "interpretation-geology-review-gis").click()
        assert len(messages) == 1 and "changed" in messages[0]
        assert QApplication.overrideCursor() is None
    finally:
        workspace.close()


@pytest.mark.parametrize("change", ["dataset", "axis_unit", "geology"])
def test_changed_dataset_axis_or_geology_is_rejected(qapp, monkeypatch, tmp_path, change):
    workspace, session, receiver, combined = _with_inserted_gis(monkeypatch, tmp_path, AppLanguage.EN)
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: messages.append(args[2]))
    monkeypatch.setattr(GisReferenceDialog, "exec", lambda _dialog: pytest.fail("foreign GIS review"))
    try:
        workspace.geology_evidence_button.click()
        dialog = workspace._geology_evidence_dialog
        assert dialog is not None
        if change == "dataset":
            session.current_dataset_id = receiver.dataset_id
        elif change == "axis_unit":
            combined.active_index.unit = "ft"
        else:
            session.current_well.lithology.append(LithologyInterval("new", 100.0, 102.0, "sandstone"))
        dialog.findChild(QPushButton, "interpretation-geology-review-gis").click()
        assert len(messages) == 1 and "changed" in messages[0]
    finally:
        workspace.close()


def test_opus_report_rechecks_opus_candidate_before_gis_review(qapp, monkeypatch, tmp_path):
    workspace, _, _, combined = _with_inserted_gis(monkeypatch, tmp_path, AppLanguage.EN)
    standard_builder = legacy.build_hydrocarbon_interpretation_report
    calls = []

    def opus_report(session, *, total_gas_lod=None, **kwargs):
        calls.append(total_gas_lod)
        return standard_builder(session, **kwargs)

    monkeypatch.setattr(legacy, "build_opus_interpretation_report", opus_report)
    seen = []
    monkeypatch.setattr(GisReferenceDialog, "exec", lambda dialog: seen.append(dialog.dataset) or 0)
    try:
        index = workspace.report_mode.findData("opus_text")
        assert index >= 0
        workspace.report_mode.setCurrentIndex(index)
        workspace.geology_evidence_button.click()
        dialog = workspace._geology_evidence_dialog
        assert dialog is not None
        before = len(calls)
        dialog.findChild(QPushButton, "interpretation-geology-review-gis").click()
        assert len(calls) == before + 1 and seen == [combined]
    finally:
        workspace.close()
