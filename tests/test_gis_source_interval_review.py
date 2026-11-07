"""Read-only review of verified GIS channels without petrophysical inference."""

from dataclasses import replace

import numpy as np
import pytest

from geoworkbench.domain.models import CalculationState, DatasetKind, IndexType
from geoworkbench.services.gis_interval_sample_review import review_gis_source_interval_samples
from test_gis_external_exact_review import _copy
from test_gis_input_inventory import _dataset


@pytest.mark.parametrize("mnemonic,unit", [
    ("GR", "API"), ("RHOB", "g/cm3"), ("NPHI", "%"),
    ("DT", "us/ft"), ("RT", "ohm.m"),
])
def test_raw_observations_preserve_unit_missing_values_and_source(mnemonic, unit):
    dataset = _dataset(mnemonic, unit)
    original = dataset.curves[mnemonic].values.copy()
    dataset.curves[mnemonic].values[0] = 0.0
    result = review_gis_source_interval_samples(
        dataset, curve_key=mnemonic, top_md_m=100, bottom_md_m=102,
    )
    assert (result.sample_count, result.finite_count, result.missing_count) == (3, 2, 1)
    assert result.finite_md_bounds == (100.0, 102.0)
    assert result.finite_value_bounds == (0.0, 30.0)
    assert result.missing_md_preview == (101.0,)
    assert result.source.unit == unit and result.source.provenance == "source:las"
    original[0] = 0.0
    np.testing.assert_array_equal(dataset.curves[mnemonic].values, original)


@pytest.mark.parametrize("change", ["axis", "unit", "semantic", "gas", "wrong_dataset", "stale"])
def test_invalid_or_unverified_sources_are_not_silently_accepted(change):
    dataset = _dataset("RT", "ohm.m")
    curve = dataset.curves["RT"]
    if change == "axis":
        dataset.active_index.index_type = IndexType.TVD
    elif change == "unit":
        curve.metadata = replace(curve.metadata, unit="unknown")
    elif change == "semantic":
        curve.metadata = replace(curve.metadata, semantic=None)
    elif change == "gas":
        dataset = _dataset("C1", "%")
        dataset.curves["RT"] = dataset.curves.pop("C1")
    elif change == "wrong_dataset":
        dataset.kind = DatasetKind.GTI
    else:
        curve.state = CalculationState.STALE
    with pytest.raises(ValueError, match="source review failed"):
        review_gis_source_interval_samples(dataset, curve_key="RT", top_md_m=100, bottom_md_m=102)


def test_empty_interval_does_not_claim_coverage():
    result = review_gis_source_interval_samples(
        _dataset("RT", "ohm.m"), curve_key="RT", top_md_m=110, bottom_md_m=120,
    )
    assert (result.sample_count, result.finite_md_bounds, result.finite_value_bounds) == (0, None, None)


def test_source_containing_only_missing_values_is_reported_without_calibration():
    dataset = _dataset("RT", "ohm.m")
    dataset.curves["RT"].values[:] = np.nan
    result = review_gis_source_interval_samples(
        dataset, curve_key="RT", top_md_m=100, bottom_md_m=102,
    )
    assert (result.sample_count, result.finite_count, result.missing_count) == (3, 0, 3)
    assert result.finite_md_bounds is None and result.finite_value_bounds is None
    assert result.missing_md_preview == (100.0, 101.0, 102.0)


def test_interpolated_external_curve_is_not_described_as_raw_observations(monkeypatch, tmp_path):
    _, _, _, combined = _copy(monkeypatch, tmp_path, source_depth=(100.0, 102.0))
    key = next(iter(combined.curves))
    with pytest.raises(ValueError, match="source review failed"):
        review_gis_source_interval_samples(combined, curve_key=key, top_md_m=100, bottom_md_m=102)
