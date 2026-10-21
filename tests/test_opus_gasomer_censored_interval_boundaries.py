"""Source QC gaps separate OPUS shows even within permitted depth separation."""

from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.calculations.opus_gasomer import (
    OpusGasomerValueState,
    detect_opus_gasomer_intervals,
)


def _interrupted_show(
    gap: float, *, multiplier: float, descending: bool,
) -> tuple[np.ndarray, np.ndarray]:
    depth = np.arange(0.0, 40.0, 0.2)
    gas_percent = np.full(depth.shape, 0.01)
    gas_percent[50:61] = 0.20
    gas_percent[55] = gap
    source = gas_percent * multiplier
    if descending:
        depth = depth[::-1].copy()
        source = source[::-1].copy()
    return depth, source


@pytest.mark.parametrize(
    ("gap", "expected_state"),
    [
        (np.nan, OpusGasomerValueState.MISSING),
        (np.inf, OpusGasomerValueState.INVALID),
        (-0.1, OpusGasomerValueState.INVALID),
        (0.0005, OpusGasomerValueState.BELOW_LOD),
    ],
)
@pytest.mark.parametrize(("unit", "multiplier", "lod"), [
    ("%vol", 1.0, 0.001),
    ("ppm", 10_000.0, 10.0),
])
@pytest.mark.parametrize("descending", [False, True])
def test_censored_or_invalid_source_row_splits_two_opus_shows(
    gap: float, expected_state: OpusGasomerValueState,
    unit: str, multiplier: float, lod: float, descending: bool,
) -> None:
    depth, source = _interrupted_show(
        gap, multiplier=multiplier, descending=descending,
    )
    original_depth = depth.copy()
    original_source = source.copy()
    result = detect_opus_gasomer_intervals(
        depth, source, unit=unit, total_gas_lod=lod,
    )
    at_gap = int(np.flatnonzero(np.isclose(depth, 11.0))[0])
    assert result.input_states[at_gap] == int(expected_state)
    assert not result.raw_candidate_mask[at_gap]
    assert not result.candidate_mask[at_gap]
    assert len(result.intervals) == 2
    first, second = result.intervals
    assert first.bottom_depth < 11.0 < second.top_depth
    assert first.candidate_samples >= 3
    assert second.candidate_samples >= 3
    np.testing.assert_array_equal(depth, original_depth)
    np.testing.assert_array_equal(source, original_source)


@pytest.mark.parametrize("gap", [0.0, 0.01])
@pytest.mark.parametrize("descending", [False, True])
def test_real_zero_or_low_gas_preserves_existing_opus_short_gap_rule(
    gap: float, descending: bool,
) -> None:
    depth, source = _interrupted_show(gap, multiplier=1.0, descending=descending)
    result = detect_opus_gasomer_intervals(
        depth, source, total_gas_lod=0.001,
    )
    assert len(result.intervals) == 1
    assert result.intervals[0].top_depth < 11.0 < result.intervals[0].bottom_depth
    center = int(np.flatnonzero(np.isclose(depth, 11.0))[0])
    assert result.input_states[center] == int(
        OpusGasomerValueState.MEASURED_ZERO if gap == 0 else OpusGasomerValueState.AVAILABLE
    )
