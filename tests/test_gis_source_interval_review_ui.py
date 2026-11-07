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
