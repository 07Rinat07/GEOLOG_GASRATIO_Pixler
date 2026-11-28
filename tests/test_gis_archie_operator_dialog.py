"""Archie operator preview: exact input rows, source checks, no LAS mutation."""
from dataclasses import replace

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from geoworkbench.domain.models import DatasetKind
from geoworkbench.services.gis_archie_profile import ArchieRowStatus
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
        assert preview.track.profile is preview.profile
        assert preview.track.projection.value_bounds[1] > 1
        assert preview.track.projection.points[1].value_fraction is None
        preview.table.setCurrentIndex(preview.model.index(2, 4))
        assert preview.track.selected_row == 2
        assert preview.parameters_label.objectName() == "gis-archie-profile-coefficients"
        assert "0.1" in preview.parameters_label.text()
        assert "a=1" in preview.parameters_label.text()
        assert "m=2" in preview.parameters_label.text()
        assert "n=2" in preview.parameters_label.text()
        assert preview.profile.coefficients.formation_water_resistivity_ohm_m == 0.1
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


def test_archie_preview_distinguishes_adjacent_source_values(qapp, monkeypatch):
    dataset = _dataset(descending=True)
    phi, rt = 0.2345678901234567, 12.345678901234567
    next_phi, next_rt = float(np.nextafter(phi, np.inf)), float(np.nextafter(rt, np.inf))
    dataset.curves["phi"].values[::2] = (phi, next_phi)
    dataset.curves["rt"].values[::2] = (rt, next_rt)
    depths = dataset.active_index.values.copy()
    source_values = {key: dataset.curves[key].values.copy() for key in ("phi", "rt")}
    captured = []

    def inspect(preview):
        model = preview.model
        display = tuple(
            tuple(model.data(model.index(row, col)) for col in range(5))
            for row in range(model.rowCount())
        )
        tooltips = tuple(
            tuple(model.data(model.index(row, col), Qt.ItemDataRole.ToolTipRole) for col in (2, 3))
            for row in (0, 2)
        )
        headers = tuple(model.headerData(col, Qt.Orientation.Horizontal) for col in (2, 3))
        captured.append((preview.profile, display, tooltips, headers))
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(GisArchieProfileDialog, "exec", inspect)
    dlg = GisArchieDialog(dataset, language=AppLanguage.EN)
    try:
        _fill(dlg)
        dlg.evaluate.click()
        (profile, display, tooltips, headers), = captured
        assert dlg.status.text() == dlg._t("snapshot")
        assert headers == ("φ, v/v", "Rt, ohm·m")
        assert tuple(row[:2] for row in display) == (
            ("1", "103"), ("2", "102"), ("3", "101"), ("4", "100"),
        )
        pairs = ((str(phi), str(rt)), (str(next_phi), str(next_rt)))
        assert (display[0][2:4], display[2][2:4]) == pairs
        assert tooltips == pairs
        assert display[1][2:] == ("—", "10", "—")
        assert display[3][2:] == ("0.2", "-1", "—")
        assert profile.rows[1].status is ArchieRowStatus.MISSING_INPUT
        assert profile.rows[3].status is ArchieRowStatus.INVALID_INPUT
        for index, inputs in zip((0, 2), ((phi, rt), (next_phi, next_rt)), strict=True):
            estimate = profile.rows[index].estimate
            assert estimate is not None
            measured_phi, measured_rt = inputs
            assert estimate.value == pytest.approx((0.1 / (measured_phi**2 * measured_rt))**0.5)
            assert display[index][4] == format(estimate.value, ".12g")
        np.testing.assert_array_equal(dataset.active_index.values, depths)
        for key, values in source_values.items():
            np.testing.assert_array_equal(dataset.curves[key].values, values)
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
