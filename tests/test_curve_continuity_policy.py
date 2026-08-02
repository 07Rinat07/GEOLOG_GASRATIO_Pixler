from __future__ import annotations

import numpy as np

from geoworkbench.calculations.curve_continuity import (
    CurveContinuityPolicy,
    build_segment_connect_mask,
    estimate_short_gap_limit,
    interpolate_bounded_gaps,
)
from geoworkbench.calculations.gas_conditioning import GasConditioningPolicy


def test_gas_conditioning_and_rendering_share_one_policy_type() -> None:
    assert GasConditioningPolicy is CurveContinuityPolicy


def test_common_policy_fills_sparse_cadence_and_keeps_long_outage() -> None:
    axis = np.arange(0.0, 31.0)
    values = np.full(axis.shape, np.nan)
    values[[0, 3, 6, 30]] = (10.0, 13.0, 16.0, 30.0)

    limit = estimate_short_gap_limit(axis, values)
    assert limit is not None
    conditioned, interpolated = interpolate_bounded_gaps(
        axis,
        values,
        max_gap=limit,
    )

    np.testing.assert_allclose(conditioned[:7], np.arange(10.0, 17.0))
    assert interpolated[1]
    assert interpolated[5]
    assert np.isnan(conditioned[15])
    assert not interpolated[15]


def test_segment_mask_joins_only_adjacent_finite_points() -> None:
    axis = np.arange(0.0, 7.0)
    values = np.array([1.0, 2.0, 3.0, np.nan, 5.0, 6.0, np.nan])

    connect = build_segment_connect_mask(axis, values)

    np.testing.assert_array_equal(
        connect,
        [True, True, False, False, True, False, False],
    )
    assert connect.dtype == np.bool_


def test_explicit_zero_remains_a_finite_linear_sample() -> None:
    axis = np.arange(0.0, 5.0)
    values = np.array([1.0, np.nan, 0.0, np.nan, 5.0])

    conditioned, mask = interpolate_bounded_gaps(axis, values, max_gap=3.0)

    assert conditioned[2] == 0.0
    assert not mask[2]
    assert conditioned[1] == 0.5
    assert conditioned[3] == 2.5
