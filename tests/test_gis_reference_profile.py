"""Calibrated IGR/density profiles use actual MD rows, never interpolated values."""
from dataclasses import FrozenInstanceError, replace

import numpy as np
import pytest

from geoworkbench.services import gis_reference_calibration as service
from geoworkbench.services.gis_reference_calibration import (
    GisProfileRowStatus, evaluate_gis_reference_profile, evaluate_gis_reference_sample,
)
from geoworkbench.services.petrophysical_reference_models import PetrophysicalQuality
from test_gis_reference_calibration import _calibration, _dataset


@pytest.mark.parametrize("density", (False, True))
@pytest.mark.parametrize("descending", (False, True))
def test_profile_preserves_exact_source_rows_and_scalar_qc(density, descending):
    dataset = _dataset(density)
    depths = dataset.active_index.values
    values = dataset.curves["selected"].values
    if descending:
        depths[:] = depths[::-1].copy()
    before_depths, before_values = depths.copy(), values.copy()
    calibration = _calibration(dataset, density)
    profile = evaluate_gis_reference_profile(
        dataset, calibration, md_top_m=100, md_base_m=102,
    )
    assert profile.calibration is calibration
    assert profile.md_bounds == (100.0, 102.0)
    assert profile.sample_count == 3
    assert profile.estimated_count == 2 and profile.missing_count == 1 and profile.invalid_count == 0
    assert tuple(row.sample_index for row in profile.rows) == (0, 1, 2)
    assert tuple(row.md_m for row in profile.rows) == tuple(depths)
    for index in (0, 2):
        row = profile.rows[index]
        scalar = evaluate_gis_reference_sample(dataset, calibration, sample_index=index)
        assert row.status is GisProfileRowStatus.ESTIMATED
        assert row.estimate == scalar.estimate and row.source_value == scalar.source_value
    missing = profile.rows[1]
    assert missing.status is GisProfileRowStatus.MISSING_SOURCE
    assert missing.source_value is None and missing.estimate is None
    assert profile.rows[2].estimate is not None
    assert profile.rows[2].estimate.quality is (
        PetrophysicalQuality.OUTSIDE_PHYSICAL_RANGE if density
        else PetrophysicalQuality.OUTSIDE_REFERENCE_RANGE
    )
    assert not profile.rows[2].estimate.usable_as_fraction
    assert dataset.active_index.values is depths and dataset.curves["selected"].values is values
    np.testing.assert_array_equal(depths, before_depths)
    np.testing.assert_array_equal(values, before_values)
    with pytest.raises(FrozenInstanceError):
        profile.rows[0].md_m = 99.0


@pytest.mark.parametrize("descending", (False, True))
def test_closed_bounds_no_rows_and_missing_only_are_not_zero_estimates(descending):
    dataset = _dataset()
    if descending:
        dataset.active_index.values[:] = [102.0, 101.0, 100.0]
    calibration = _calibration(dataset)
    def profile(top, base):
        return evaluate_gis_reference_profile(dataset, calibration, md_top_m=top, md_base_m=base)
    single = profile(100, 100)
    assert single.sample_count == 1
    assert single.rows[0].sample_index == (2 if descending else 0)
    assert single.rows[0].md_m == 100.0
    empty = profile(100.1, 100.9)
    assert empty.rows == () and empty.sample_count == empty.estimated_count == empty.missing_count == 0
    missing = profile(101, 101)
    assert missing.sample_count == missing.missing_count == 1 and missing.estimated_count == 0
    assert missing.rows[0].estimate is None


def test_density_invalid_measurement_is_not_zero_porosity():
    dataset = _dataset(True)
    dataset.curves["selected"].values[:] = [0.0, np.inf, 2.71]
    calibration = _calibration(dataset, True)
    profile = evaluate_gis_reference_profile(dataset, calibration, md_top_m=100, md_base_m=102)
    invalid, missing, zero = profile.rows
    assert invalid.status is GisProfileRowStatus.INVALID_MEASUREMENT
    assert invalid.source_value == 0.0 and invalid.estimate is None and invalid.issue
    assert missing.status is GisProfileRowStatus.MISSING_SOURCE and missing.estimate is None
    assert zero.status is GisProfileRowStatus.ESTIMATED
    assert zero.estimate is not None and zero.estimate.value == 0.0
    assert zero.estimate.usable_as_fraction
    assert profile.invalid_count == profile.missing_count == profile.estimated_count == 1


@pytest.mark.parametrize("top,base", ((102, 100), (99, 102), (100, 103), (np.nan, 102), (True, 102)))
def test_profile_refuses_invalid_or_outside_scope(top, base):
    dataset = _dataset()
    with pytest.raises(ValueError):
        evaluate_gis_reference_profile(dataset, _calibration(dataset), md_top_m=top, md_base_m=base)


def test_profile_does_not_extend_calibration_scope():
    dataset = _dataset()
    calibration = _calibration(dataset, md_top_m=100, md_base_m=101)
    with pytest.raises(ValueError, match="scope"):
        evaluate_gis_reference_profile(dataset, calibration, md_top_m=100, md_base_m=102)


@pytest.mark.parametrize("change", ("values", "outside_interval", "axis", "unit", "array", "evidence"))
def test_stale_calibration_blocks_profile_even_when_selected_rows_unchanged(change):
    dataset = _dataset()
    calibration = _calibration(dataset)
    curve = dataset.curves["selected"]
    if change == "values":
        curve.values[0] = 70.0
    elif change == "outside_interval":
        curve.values[2] = 150.0
    elif change == "axis":
        dataset.active_index.values[1] = 101.5
    elif change == "unit":
        curve.metadata = replace(curve.metadata, unit="uR/h")
    elif change == "array":
        curve.values = curve.values.copy()
    else:
        dataset.active_index.evidence = ("changed",)
    with pytest.raises(ValueError):
        evaluate_gis_reference_profile(dataset, calibration, md_top_m=100, md_base_m=100)


def test_profile_revalidates_after_calculation_and_does_not_publish_partial_result(monkeypatch):
    dataset = _dataset()
    calibration = _calibration(dataset)
    estimate = service._estimate
    calls = []
    def changed(method, params, value):
        result = estimate(method, params, value)
        calls.append(value)
        if len(calls) == 2:
            dataset.curves["selected"].values[2] = 150.0
        return result
    monkeypatch.setattr(service, "_estimate", changed)
    with pytest.raises(ValueError, match="curve sample values changed"):
        evaluate_gis_reference_profile(dataset, calibration, md_top_m=100, md_base_m=102)
    assert len(calls) >= 2


def test_profile_validates_source_twice_not_once_per_row(monkeypatch):
    dataset = _dataset()
    calibration = _calibration(dataset)
    validate = service.validate_gis_reference_calibration
    calls = []
    def counted(source, current):
        calls.append(current)
        validate(source, current)
    monkeypatch.setattr(service, "validate_gis_reference_calibration", counted)
    result = evaluate_gis_reference_profile(dataset, calibration, md_top_m=100, md_base_m=102)
    assert result.sample_count == 3 and calls == [calibration, calibration]
