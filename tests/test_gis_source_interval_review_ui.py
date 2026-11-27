from dataclasses import replace

import numpy as np
import pytest

from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.gis_reference_dialog import GisReferenceDialog
from test_gis_input_inventory import _dataset


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("mnemonic,unit", [("NPHI", "%"), ("DT", "us/ft"), ("RT", "ohm.m")])
def test_raw_review_requires_only_explicit_curve_and_preserves_units(qapp, language, mnemonic, unit):
    dataset = _dataset(mnemonic, unit)
    dialog = GisReferenceDialog(dataset, language=language)
    try:
        dialog.channel.setCurrentIndex(dialog.channel.findData(mnemonic))
        dialog.fields["top"].setText("100")
        dialog.fields["base"].setText("102")
        assert dialog.method.currentData() is None
        dialog.review_source_interval.click()
        text = dialog.interval_review_label.text()
        assert dialog._t("source_interval_notice") in text
        assert dialog._t("interval_summary", total=3, finite=2, missing=1) in text
        assert dialog._t("interval_value_bounds", minimum="10", maximum="30", unit=unit) in text
        assert dialog.sample is None and not dialog.save_parameters.isEnabled()
    finally:
        dialog.close()


def test_raw_review_rechecks_changed_metadata_and_does_not_reuse_result(qapp):
    dataset = _dataset("RT", "ohm.m")
    dialog = GisReferenceDialog(dataset)
    try:
        dialog.channel.setCurrentIndex(dialog.channel.findData("RT"))
        dialog.fields["top"].setText("100")
        dialog.fields["base"].setText("102")
        dialog.review_source_interval.click()
        assert dialog._t("source_interval_notice") in dialog.interval_review_label.text()
        curve = dataset.curves["RT"]
        curve.metadata = replace(curve.metadata, unit="unknown")
        dialog.review_source_interval.click()
        assert dialog.interval_review_label.text() == dialog._t("interval_invalid")
        assert dialog.sample is None
    finally:
        dialog.close()


def test_raw_review_reports_all_missing_samples(qapp):
    dataset = _dataset("RT", "ohm.m")
    dataset.curves["RT"].values[:] = np.nan
    dialog = GisReferenceDialog(dataset)
    try:
        dialog.channel.setCurrentIndex(dialog.channel.findData("RT"))
        dialog.fields["top"].setText("100")
        dialog.fields["base"].setText("102")
        dialog.review_source_interval.click()
        text = dialog.interval_review_label.text()
        assert dialog._t("interval_summary", total=3, finite=0, missing=3) in text
        assert dialog._t("interval_missing_depths", shown=3, total=3, depths="100, 101, 102") in text
        assert dialog._t("source_interval_notice") in text
        assert dialog.sample is None
    finally:
        dialog.close()


def test_raw_review_distinguishes_close_missing_depths_in_source_order(qapp):
    dataset = _dataset("RT", "ohm.m")
    depths = np.array([1500.0000004, 1500.0000002, 1500.0])
    values = np.array([np.nan, np.nan, 30.0])
    dataset.active_index.values[:] = depths
    dataset.curves["RT"].values[:] = values
    dialog = GisReferenceDialog(dataset, language=AppLanguage.EN)
    try:
        dialog.channel.setCurrentIndex(dialog.channel.findData("RT"))
        dialog.fields["top"].setText("1499")
        dialog.fields["base"].setText("1501")
        dialog.review_source_interval.click()

        lines = dialog.interval_review_label.text().splitlines()
        assert dialog._t("source_interval_notice") in lines
        assert dialog._t("interval_summary", total=3, finite=1, missing=2) in lines
        assert lines[-1] == dialog._t(
            "interval_missing_depths", shown=2, total=2, depths="1500.0000004, 1500.0000002",
        )
        assert dialog.sample is None and not dialog.save_parameters.isEnabled()
        np.testing.assert_array_equal(dataset.active_index.values, depths)
        np.testing.assert_array_equal(dataset.curves["RT"].values, values)
    finally:
        dialog.close()
