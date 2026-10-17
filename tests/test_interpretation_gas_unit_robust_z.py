"""Unit-consistent gas anomaly screening without rewriting original LAS values."""

from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.services.hydrocarbon_interpretation_legacy import (
    _detect_candidates,
)


def _gas_dataset(unit: str, multiplier: float) -> tuple[Dataset, np.ndarray]:
    depth = np.arange(1000.0, 1100.0, dtype=np.float64)
    physical_percent = 0.02 + 0.002 * np.sin(np.linspace(0, 6 * np.pi, depth.size))
    physical_percent[40:44] = 0.16
    physical_percent[6] = np.nan
    physical_percent[17] = 0.0
    source_values = physical_percent * multiplier
    dataset = Dataset(
        f"gas-unit-{unit}", f"Gas unit {unit}", DatasetKind.GTI, DepthDomain.MD, depth,
    )
    dataset.upsert_curve(
        "TG", source_values, unit=unit, description="Measured total gas",
        provenance="source:unit-regression",
    )
    return dataset, source_values.copy()


@pytest.mark.parametrize(
    ("unit", "multiplier"),
    (
        ("%vol", 1.0),
        ("ppm", 10000.0),
        ("ppb", 1.0e7),
        ("fraction", 0.01),
    ),
)
def test_robust_z_anomaly_is_invariant_across_physical_gas_units(
    unit, multiplier,
):
    reference, _ = _gas_dataset("%vol", 1.0)
    dataset, source_copy = _gas_dataset(unit, multiplier)

    expected, reference_median, reference_scale, reference_warning = _detect_candidates(
        reference, "TG", 4.0,
    )
    actual, median, scale, warning = _detect_candidates(dataset, "TG", 4.0)
    assert reference_warning is None
    assert warning is None
    assert len(expected) == len(actual) == 1
    assert median == pytest.approx(reference_median, abs=1.0e-11)
    assert scale == pytest.approx(reference_scale, abs=1.0e-11)
    assert actual[0].top_depth == expected[0].top_depth
    assert actual[0].bottom_depth == expected[0].bottom_depth
    assert actual[0].max_robust_z == pytest.approx(expected[0].max_robust_z)
    assert actual[0].max_primary_value == pytest.approx(
        expected[0].max_primary_value * multiplier,
    )
    # No mutation, including the NaN/missing sample and the physical 0 reading.
    np.testing.assert_array_equal(
        dataset.curve_by_mnemonic("TG").values, source_copy, strict=True,
    )


def test_unmapped_vendor_gas_unit_uses_legacy_detector_scale_without_guesswork():
    dataset, original = _gas_dataset("vendor-relative-gas", 17.0)
    _, median, scale, warning = _detect_candidates(dataset, "TG", 4.0)
    valid = np.isfinite(original) & (original >= 0.0)
    expected_median = float(np.median(np.log1p(original[valid])))
    assert median == pytest.approx(expected_median)
    assert scale is not None
    assert warning is None
    np.testing.assert_array_equal(
        dataset.curve_by_mnemonic("TG").values, original, strict=True,
    )
