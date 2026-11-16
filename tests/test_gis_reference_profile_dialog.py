"""Explicit calibrated profile UI: original rows, QC and source safety."""

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from geoworkbench.services.gis_reference_calibration import (
    GisProfileRowLimitExceeded, evaluate_gis_reference_profile,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui import gis_reference_dialog as reference
from geoworkbench.ui.gis_reference_dialog import GisReferenceDialog
from geoworkbench.ui.gis_reference_profile_dialog import GisReferenceProfileDialog
from test_gis_reference_dialog import _dataset, _fill
from test_gis_reference_calibration import _calibration


@pytest.mark.parametrize("language", tuple(AppLanguage))
@pytest.mark.parametrize("density", (False, True))
def test_profile_preview_uses_actual_rows_even_when_scalar_row_is_missing(qapp, monkeypatch, language, density):
    dataset = _dataset(density)
    before = dataset.curves["selected"].values.copy()
    axis_before = dataset.active_index.values.copy()
    dialog = GisReferenceDialog(dataset, language=language)
    seen = []

    def inspect(preview):
        profile = preview.profile
        assert profile.sample_count == 3
        assert profile.estimated_count == 2 and profile.missing_count == 1
        model = preview.model
        assert model.rowCount() == 3 and model.columnCount() == 5
        assert model.data(model.index(0, 0)) == "1"
        assert model.data(model.index(1, 1)) == "101"
        assert model.data(model.index(1, 2)) == "—"
        assert model.data(model.index(1, 3)) == "—"
        assert model.data(model.index(1, 4)) == dialog._t("profile_missing_source")
        assert float(model.data(model.index(0, 3))) == pytest.approx(
            (2.71 - 2.42) / 1.71 if density else 0.4,
        )
        assert model.data(model.index(2, 4)) == dialog._t(
            "outside_physical_range" if density else "outside_reference_range",
        )
        assert not model.flags(model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable
        assert model.headerData(2, Qt.Orientation.Horizontal) == dialog._t(
            "profile_source", unit="g/cm3" if density else "API",
        )
        seen.append(True)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(GisReferenceProfileDialog, "exec", inspect)
    try:
        _fill(dialog, density)
        dialog.row.setValue(2)
        dialog.calculate_profile.click()
        assert seen == [True]
        assert dialog.sample is None and not dialog.save_parameters.isEnabled()
        np.testing.assert_array_equal(dataset.curves["selected"].values, before)
        np.testing.assert_array_equal(dataset.active_index.values, axis_before)
    finally:
        dialog.close()


@pytest.mark.parametrize("change", ("curve", "axis", "parameters", "limit"))
def test_unavailable_profile_never_opens_partial_preview(qapp, monkeypatch, change):
    dataset = _dataset()
    dialog = GisReferenceDialog(dataset, language=AppLanguage.EN)
    monkeypatch.setattr(GisReferenceProfileDialog, "exec", lambda *_: pytest.fail("Unexpected preview"))
    try:
        _fill(dialog)
        if change == "curve":
            dataset.curves["selected"].values[:] = np.nan
        elif change == "axis":
            dataset.active_index.values[:] = [100, 100, 102]
        elif change == "parameters":
            dialog.parameters[1].setText("20")
        else:
            monkeypatch.setattr(reference, "MAX_PROFILE_PREVIEW_ROWS", 2)
        dialog.calculate_profile.click()
        expected = dialog._t("profile_limit", limit=2) if change == "limit" else dialog._t("profile_invalid")
        assert dialog.result_label.text() == expected
        assert dialog.sample is None
    finally:
        dialog.close()


def test_modal_source_change_revokes_existing_sample(qapp, monkeypatch):
    dataset = _dataset()
    dialog = GisReferenceDialog(dataset)
    try:
        _fill(dialog)
        dialog.calculate.click()
        assert dialog.sample is not None

        def inspect(preview):
            assert preview.profile.sample_count == 3
            dataset.curves["selected"].values[0] = 90.0
            return QDialog.DialogCode.Rejected

        monkeypatch.setattr(GisReferenceProfileDialog, "exec", inspect)
        dialog.calculate_profile.click()
        assert dialog.sample is None
        assert not dialog.save_parameters.isEnabled()
        assert dialog.result_label.text() == dialog._t("profile_invalid")
    finally:
        dialog.close()


def test_profile_does_not_replace_valid_scalar_sample(qapp, monkeypatch):
    dialog = GisReferenceDialog(_dataset())
    monkeypatch.setattr(GisReferenceProfileDialog, "exec", lambda *_: QDialog.DialogCode.Rejected)
    try:
        _fill(dialog)
        dialog.calculate.click()
        sample, result = dialog.sample, dialog.result_label.text()
        assert sample is not None
        dialog.calculate_profile.click()
        assert dialog.sample is sample and dialog.save_parameters.isEnabled()
        assert dialog.result_label.text() == result
    finally:
        dialog.close()


@pytest.mark.parametrize("descending", (False, True))
def test_row_budget_rejects_full_interval_without_truncation(descending):
    dataset = _dataset()
    if descending:
        dataset.active_index.values[:] = [102, 101, 100]
    calibration = _calibration(dataset)
    with pytest.raises(GisProfileRowLimitExceeded):
        evaluate_gis_reference_profile(dataset, calibration, md_top_m=100, md_base_m=102, max_rows=2)
    full = evaluate_gis_reference_profile(dataset, calibration, md_top_m=100, md_base_m=102, max_rows=3)
    assert full.sample_count == 3


@pytest.mark.parametrize("limit", (0, -1, True, 2.0))
def test_invalid_row_budget_is_rejected(limit):
    dataset = _dataset()
    with pytest.raises(ValueError, match="row budget"):
        evaluate_gis_reference_profile(dataset, _calibration(dataset), md_top_m=100, md_base_m=102, max_rows=limit)
