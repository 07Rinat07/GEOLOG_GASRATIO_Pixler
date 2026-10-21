"""A missing measurement must not become an uninterrupted gas-show interval."""

from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.services.hydrocarbon_interpretation_legacy import (
    _detect_candidates,
)


def _series(
    gap_value: float,
    *,
    descending: bool = False,
    unit: str = "%vol",
) -> tuple[Dataset, np.ndarray]:
    depths = np.arange(1000.0, 1100.0, dtype=np.float64)
    values = 0.02 + 0.001 * np.sin(np.linspace(0.0, 7.0, depths.size))
    values[40] = 0.18
    values[41] = gap_value
    values[42] = 0.16
    if unit == "ppm":
        values *= 10_000.0
    if descending:
        depths = depths[::-1].copy()
        values = values[::-1].copy()
    dataset = Dataset(
        f"qc-gap-{descending}-{unit}",
        "Missing sample interval regression",
        DatasetKind.GTI,
        DepthDomain.MD,
        depths,
    )
    dataset.upsert_curve(
        "TG", values, unit=unit, description="Measured total gas",
        provenance="source:qc-boundary-fixture",
    )
    return dataset, values.copy()


@pytest.mark.parametrize("missing", [np.nan, np.inf, -1.0])
@pytest.mark.parametrize("descending", [False, True])
@pytest.mark.parametrize("unit", ["%vol", "ppm"])
def test_missing_or_invalid_gas_sample_splits_two_anomaly_intervals(
    missing: float, descending: bool, unit: str,
) -> None:
    dataset, original = _series(missing, descending=descending, unit=unit)
    candidates, median, scale, warning = _detect_candidates(dataset, "TG", 4.0)

    assert warning is None
    assert median is not None and scale is not None
    assert len(candidates) == 2
    assert [item.sample_count for item in candidates] == [1, 1]
    assert candidates[0].bottom_depth < 1041.0
    assert candidates[1].top_depth > 1041.0
    assert [item.max_primary_value for item in candidates] == pytest.approx(
        [0.18, 0.16] if unit == "%vol" else [1800.0, 1600.0],
    )
    np.testing.assert_array_equal(
        dataset.curve_by_mnemonic("TG").values, original, strict=True,
    )


@pytest.mark.parametrize("middle_value", [0.0, 0.02])
def test_valid_measured_dip_retains_existing_short_gap_policy(middle_value: float) -> None:
    dataset, _ = _series(middle_value)
    candidates, _, _, warning = _detect_candidates(dataset, "TG", 4.0)
    assert warning is None
    assert len(candidates) == 1
    assert candidates[0].sample_count == 2
    assert candidates[0].top_depth < 1041.0 < candidates[0].bottom_depth
