"""LOD-censored source gas cannot become a measured OPUS candidate via smoothing."""

from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.calculations.opus_gasomer import (
    OpusGasomerValueState,
    detect_opus_gasomer_intervals,
)


@pytest.mark.parametrize(
    ("unit", "factor", "source_lod"),
    [
        ("%vol", 1.0, 0.001),
        ("ppm", 10_000.0, 10.0),
    ],
)
@pytest.mark.parametrize("descending", [False, True])
def test_below_lod_source_row_is_not_opus_show_even_with_high_smoothing(
    unit: str, factor: float, source_lod: float, descending: bool,
) -> None:
    depth = np.arange(0.0, 40.0, 0.2)
    gas_percent = np.full(depth.shape, 0.01)
    gas_percent[50:59] = 0.05
    gas_percent[54] = 0.0005  # positive reading strictly below LOD
    raw = gas_percent * factor
    if descending:
        depth = depth[::-1].copy()
        raw = raw[::-1].copy()
    original = raw.copy()
    result = detect_opus_gasomer_intervals(
        depth, raw, unit=unit, total_gas_lod=source_lod,
    )
    center = int(np.flatnonzero(np.isclose(depth, 10.8))[0])
    assert result.input_states[center] == int(OpusGasomerValueState.BELOW_LOD)
    # The median is high only because neighboring source rows are high.
    assert result.smoothed_total_gas[center] > 0.03
    assert result.robust_z[center] > 3.0
    assert not result.raw_candidate_mask[center]
    assert not result.candidate_mask[center]
    assert result.raw_candidate_mask.any()
    assert result.candidate_mask.any()
    np.testing.assert_array_equal(raw, original)


@pytest.mark.parametrize("unit,factor,lod", [("%vol", 1.0, 0.001), ("ppm", 10_000.0, 10.0)])
def test_exact_lod_remains_available_without_redefining_detection_limit(
    unit: str, factor: float, lod: float,
) -> None:
    depth = np.arange(0.0, 40.0, 0.2)
    values = np.full(depth.shape, 0.01)
    values[50:59] = 0.05
    values[54] = 0.001  # exactly LOD: neither missing nor below LOD
    result = detect_opus_gasomer_intervals(
        depth, values * factor, unit=unit, total_gas_lod=lod,
    )
    assert result.input_states[54] == int(OpusGasomerValueState.AVAILABLE)
