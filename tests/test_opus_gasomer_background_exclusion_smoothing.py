"""Technological TotalGas must not leak into local background via smoothing."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from geoworkbench.calculations.opus_gasomer import (
    detect_opus_gasomer_intervals,
    load_opus_gasomer_detector_policy,
)


@pytest.mark.parametrize(
    ("unit", "multiplier", "lod"),
    [("%vol", 1.0, 0.001), ("ppm", 10000.0, 10.0)],
)
@pytest.mark.parametrize("descending", [False, True])
def test_background_exclusion_masks_source_smoothing_window_not_only_center(
    unit: str, multiplier: float, lod: float, descending: bool,
) -> None:
    depth = np.round(np.arange(0.0, 20.0, 0.2), 1)
    percent = np.full(depth.shape, 0.01)
    # A short confirmed technological spike, close to one missing source row.
    # The original signal smoother at 9.8 averages two 0.01 and two 0.20
    # measurements into a 0.105 %vol median, even though 9.8 is a real 0.01.
    percent[(depth >= 10.0) & (depth <= 10.6)] = 0.20
    percent[depth == 9.6] = np.nan
    source = percent * multiplier
    if descending:
        depth = depth[::-1].copy()
        source = source[::-1].copy()
    before = source.copy()
    policy = replace(
        load_opus_gasomer_detector_policy(),
        background_half_span=0.2,
    )

    unexcluded = detect_opus_gasomer_intervals(
        depth, source, unit=unit, total_gas_lod=lod, policy=policy,
    )
    excluded = detect_opus_gasomer_intervals(
        depth, source, unit=unit, total_gas_lod=lod, policy=policy,
        background_exclusion_intervals=((10.0, 10.6),),
    )

    adjacent = int(np.flatnonzero(depth == 9.8)[0])
    assert unexcluded.smoothed_total_gas[adjacent] == pytest.approx(0.105)
    # Signal smoothing remains the original measured + technological series.
    np.testing.assert_allclose(
        excluded.smoothed_total_gas,
        unexcluded.smoothed_total_gas,
        equal_nan=True,
    )
    # Only the *background* smoother excludes confirmed technological source
    # samples. The outside row must retain its true local 0.01 %vol baseline.
    assert excluded.local_background[adjacent] == pytest.approx(0.01)
    assert unexcluded.local_background[adjacent] > 0.05
    np.testing.assert_array_equal(excluded.input_states, unexcluded.input_states)
    np.testing.assert_array_equal(source, before)
    np.testing.assert_array_equal(
        excluded.total_gas_percent,
        percent if not descending else percent[::-1],
    )
