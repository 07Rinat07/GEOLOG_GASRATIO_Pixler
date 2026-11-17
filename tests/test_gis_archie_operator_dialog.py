"""Archie operator preview: exact input rows, source checks, no LAS mutation."""
from dataclasses import replace

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from geoworkbench.domain.models import DatasetKind
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.gis_archie_dialog import GisArchieDialog, GisArchieProfileDialog
from geoworkbench.ui.gis_reference_dialog import GisReferenceDialog
from test_gis_archie_source_profile import _dataset


def _fill(dialog):
    dialog.phi.setCurrentIndex(dialog.phi.findData("phi"))
    dialog.rt.setCurrentIndex(dialog.rt.findData("rt"))
    values = {
        "reviewer": "Expert", "applicability_reference": "Synthetic clean formation",
        "effective_porosity_reference": "Effective porosity review",
        "true_resistivity_reference": "True Rt review",
        "alignment_reference": "Exact same-run MD rows review",
        "water_resistivity_reference": "Synthetic Rw at formation temperature",
        "md_top_m": "100", "md_base_m": "103",
        "formation_water_resistivity_ohm_m": "0,1", "tortuosity_factor": "1",
        "cementation_exponent": "2", "saturation_exponent": "2",
    }
    for key, value in values.items():
        dialog.fields[key].setText(value)


@pytest.mark.parametrize("language", tuple(AppLanguage))
@pytest.mark.parametrize("descending", (False, True))
def test_explicit_operator_archie_preview_shows_exact_qc_and_preserves_source(
    qapp, monkeypatch, language, descending,
):
    dataset = _dataset(descending)
    before = {
        key: dataset.curves[key].values.copy() for key in ("phi", "rt")
    }
    old_md = dataset.active_index.values.copy()
    dlg = GisArchieDialog(dataset, language=language)
    captured = []
    def inspect(preview):
        captured.append(preview.profile)
        assert preview.table.objectName() == "gis-archie-profile-table"
        assert preview.model.rowCount() == 4
        assert preview.model.data(preview.model.index(0, 4)) == "0.5"
        assert preview.model.data(preview.model.index(1, 2)) == "—"
        assert preview.model.data(preview.model.index(1, 4)) == "—"
        assert float(preview.model.data(preview.model.index(2, 4))) > 1
        assert preview.model.data(preview.model.index(3, 3)) == "-1"
        assert preview.model.data(preview.model.index(3, 4)) == "—"
        assert preview.model.headerData(5, Qt.Orientation.Horizontal)
        assert "Exact same-run MD rows review" in preview.findChild(
            type(preview.layout().itemAt(0).widget())
        ).text()
        assert [row.md_m for row in preview.profile.rows] == list(old_md)
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(GisArchieProfileDialog, "exec", inspect)
    try:
        assert not dlg.fields["reviewer"].text()
        dlg.evaluate.click()
        assert not captured and dlg._t("invalid") in dlg.status.text()
        _fill(dlg)
        dlg.evaluate.click()
        assert len(captured) == 1
        assert dlg.status.text() == dlg._t("snapshot")
        for key in before:
            np.testing.assert_array_equal(dataset.curves[key].values, before[key])
        np.testing.assert_array_equal(dataset.active_index.values, old_md)
    finally:
        dlg.close()


@pytest.mark.parametrize("missing", (
    "effective_porosity_reference", "true_resistivity_reference",
    "alignment_reference", "water_resistivity_reference",
    "applicability_reference", "reviewer", "saturation_exponent",
))
def test_archie_operator_requires_all_evidence_and_coefficients(qapp, monkeypatch, missing):
    dlg = GisArchieDialog(_dataset())
    monkeypatch.setattr(
        GisArchieProfileDialog, "exec",
        lambda *_: pytest.fail("Invalid Archie inputs opened a result"),
    )
    try:
        _fill(dlg)
        dlg.fields[missing].clear()
        dlg.evaluate.click()
        assert dlg._t("invalid") in dlg.status.text()
    finally:
        dlg.close()


@pytest.mark.parametrize("change", (
    "curve", "axis", "metadata", "draft", "outside_interval",
))
def test_archie_preview_discarded_when_source_or_draft_changes(qapp, monkeypatch, change):
    dataset = _dataset()
    dlg = GisArchieDialog(dataset)
    def inspect(preview):
        if change == "curve":
            dataset.curves["phi"].values[0] = 0.3
        elif change == "axis":
            dataset.active_index.values[0] = 99.
        elif change == "metadata":
            curve = dataset.curves["rt"]
            curve.metadata = replace(curve.metadata, provenance="changed")
        elif change == "draft":
            dlg.fields["reviewer"].setText("Changed")
        else:
            dataset.curves["rt"].values[3] = 20.
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(GisArchieProfileDialog, "exec", inspect)
    try:
        _fill(dlg)
        if change == "outside_interval":
            dlg.fields["md_base_m"].setText("100")
        dlg.evaluate.click()
        assert dlg.status.text() == dlg._t("stale")
    finally:
        dlg.close()


def test_archie_operator_rejects_ineligible_source_and_no_default_curve(qapp, monkeypatch):
    dataset = _dataset()
    dlg = GisArchieDialog(dataset)
    monkeypatch.setattr(GisArchieProfileDialog, "exec",
                        lambda *_: pytest.fail("Ineligible source must not preview"))
    try:
        _fill(dlg)
        dlg.phi.setCurrentIndex(0)
        dlg.evaluate.click()
        assert dlg._t("invalid") in dlg.status.text()
        dlg.phi.setCurrentIndex(dlg.phi.findData("phi"))
        dlg.fields["md_top_m"].setText("not a number")
        dlg.evaluate.click()
        assert dlg._t("invalid") in dlg.status.text()
        dlg.fields["md_top_m"].setText("100")
        dataset.kind = DatasetKind.GTI
        dlg.evaluate.click()
        assert dlg._t("invalid") in dlg.status.text()
    finally:
        dlg.close()


@pytest.mark.parametrize("language", tuple(AppLanguage))
def test_archie_entrypoint_is_separate_and_does_not_mutate_igr_draft(qapp, monkeypatch, language):
    dataset = _dataset()
    dialog = GisReferenceDialog(dataset, language=language)
    visited = []
    def inspect(archie):
        visited.append(archie.dataset is dataset)
        assert not archie.fields["reviewer"].text()
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(GisArchieDialog, "exec", inspect)
    try:
        assert dialog.archie_button.isEnabled()
        dialog.archie_button.click()
        assert visited == [True]
        assert dialog.sample is None and dialog.tablet_request is None
        assert dialog.method.currentData() is None
    finally:
        dialog.close()
