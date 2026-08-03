from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.calculations.curve_continuity import build_segment_connect_mask
from geoworkbench.tablet.geometry_cache import (
    CurveGeometryCache,
    CurveGeometryKey,
    is_derived_gas_curve_id,
)


@pytest.mark.parametrize(
    "mnemonic",
    (
        "PIXLER_C1_C2",
        "C1_C2",
        "C1_C4",
        "WH",
        "WETNESS",
        "IC4_NC4",
        "C2_REL",
        "TG_NORM",
    ),
)
def test_all_derived_gas_aliases_use_sparse_update_continuity(
    mnemonic: str,
) -> None:
    assert is_derived_gas_curve_id(mnemonic)


def test_raw_component_is_not_misclassified_as_derived() -> None:
    assert not is_derived_gas_curve_id("C1")


def _key(*, positive_values_only: bool = False) -> CurveGeometryKey:
    return CurveGeometryKey(
        curve_id="PIXLER_C1_C2",
        axis_id="depth",
        values_revision="values-1",
        axis_revision="axis-1",
        top=0.0,
        bottom=40.0,
        max_points=5000,
        positive_values_only=positive_values_only,
    )


def test_derived_null_rows_bridge_nearby_updates_but_break_long_silence() -> None:
    depth = np.arange(0.0, 31.0, dtype=np.float64)
    values = np.full(depth.shape, np.nan, dtype=np.float64)
    values[[0, 3, 30]] = (10.0, 13.0, 20.0)

    sampled_values, sampled_depth = CurveGeometryCache().get_or_build(
        _key(), depth, values
    )
    connect = build_segment_connect_mask(sampled_depth, sampled_values)

    assert np.allclose(
        sampled_depth,
        np.asarray([0.0, 3.0, 16.5, 30.0]),
    )
    assert np.allclose(
        sampled_values[[0, 1, 3]],
        np.asarray([10.0, 13.0, 20.0]),
    )
    assert np.isnan(sampled_values[2])
    assert np.array_equal(connect, np.asarray([True, False, False, False]))


def test_regular_sparse_gas_cadence_remains_connected() -> None:
    depth = np.arange(0.0, 21.0, dtype=np.float64)
    values = np.full(depth.shape, np.nan, dtype=np.float64)
    values[[0, 10, 20]] = (10.0, 12.0, 14.0)

    sampled_values, sampled_depth = CurveGeometryCache().get_or_build(
        _key(), depth, values
    )
    connect = build_segment_connect_mask(sampled_depth, sampled_values)

    assert np.allclose(sampled_depth, np.asarray([0.0, 10.0, 20.0]))
    assert np.allclose(sampled_values, np.asarray([10.0, 12.0, 14.0]))
    assert np.array_equal(connect, np.asarray([True, True, False]))


def test_two_isolated_derived_updates_do_not_create_a_long_diagonal() -> None:
    depth = np.arange(0.0, 31.0, dtype=np.float64)
    values = np.full(depth.shape, np.nan, dtype=np.float64)
    values[[0, 30]] = (10.0, 20.0)

    sampled_values, sampled_depth = CurveGeometryCache().get_or_build(
        _key(), depth, values
    )
    connect = build_segment_connect_mask(sampled_depth, sampled_values)

    assert np.isnan(sampled_values[1])
    assert np.allclose(sampled_depth, np.asarray([0.0, 15.0, 30.0]))
    assert not np.any(connect)


def test_logarithmic_derived_curve_omits_nonpositive_rows_without_point_islands() -> None:
    depth = np.arange(0.0, 7.0, dtype=np.float64)
    values = np.asarray([1.0, 0.0, np.nan, -1.0, 10.0, 0.0, 100.0])

    sampled_values, sampled_depth = CurveGeometryCache().get_or_build(
        _key(positive_values_only=True), depth, values
    )
    connect = build_segment_connect_mask(sampled_depth, sampled_values)

    assert np.allclose(sampled_depth, np.asarray([0.0, 4.0, 6.0]))
    assert np.allclose(sampled_values, np.asarray([1.0, 10.0, 100.0]))
    assert np.array_equal(connect, np.asarray([True, True, False]))


def test_real_source_axis_outage_remains_a_hard_break() -> None:
    depth = np.concatenate(
        (
            np.arange(0.0, 4.0, dtype=np.float64),
            np.arange(30.0, 34.0, dtype=np.float64),
        )
    )
    values = np.arange(depth.size, dtype=np.float64) + 1.0

    sampled_values, sampled_depth = CurveGeometryCache().get_or_build(
        _key(), depth, values
    )
    connect = build_segment_connect_mask(sampled_depth, sampled_values)

    separator = np.flatnonzero(~np.isfinite(sampled_values))
    assert separator.size == 1
    assert 3.0 < sampled_depth[separator[0]] < 30.0
    assert np.count_nonzero(connect) == 6
