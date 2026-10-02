from __future__ import annotations

import numpy as np
import pytest

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


def test_ratio_scatter_keeps_only_factual_finite_observations() -> None:
    depth = np.arange(0.0, 31.0, dtype=np.float64)
    values = np.full(depth.shape, np.nan, dtype=np.float64)
    values[[0, 3, 30]] = (10.0, 13.0, 20.0)

    sampled_values, sampled_depth = CurveGeometryCache().get_or_build(
        _key(), depth, values
    )
    assert np.allclose(sampled_depth, np.asarray([0.0, 3.0, 30.0]))
    assert np.allclose(sampled_values, np.asarray([10.0, 13.0, 20.0]))
    assert np.all(np.isfinite(sampled_values))


def test_bl_data_like_sparse_pixler_points_remain_discrete_observations() -> None:
    depth = np.arange(1174.8, 1482.4001, 0.4, dtype=np.float64)
    values = np.full(depth.shape, np.nan, dtype=np.float64)
    positions = [0, 14, 74, 309, 573]
    values[positions] = [4.2, 8.0, 3.8, 9.5, 6.0]

    sampled_values, sampled_depth = CurveGeometryCache().get_or_build(
        CurveGeometryKey(
            curve_id="PIXLER_C1_C3",
            axis_id="depth",
            values_revision="bl-data",
            axis_revision="depth-04",
            top=float(depth[0]),
            bottom=float(depth[-1]),
            max_points=5000,
            positive_values_only=True,
        ),
        depth,
        values,
    )

    assert np.all(np.isfinite(sampled_values))
    np.testing.assert_allclose(sampled_depth, depth[positions])
    np.testing.assert_allclose(sampled_values, values[positions])


def test_logarithmic_ratio_scatter_omits_nonpositive_observations() -> None:
    depth = np.arange(0.0, 7.0, dtype=np.float64)
    values = np.asarray([1.0, 0.0, np.nan, -1.0, 10.0, 0.0, 100.0])

    sampled_values, sampled_depth = CurveGeometryCache().get_or_build(
        _key(positive_values_only=True), depth, values
    )
    assert np.allclose(sampled_depth, np.asarray([0.0, 4.0, 6.0]))
    assert np.allclose(sampled_values, np.asarray([1.0, 10.0, 100.0]))
    assert np.all(np.isfinite(sampled_values))


def test_ratio_scatter_does_not_insert_synthetic_outage_rows() -> None:
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
    assert np.all(np.isfinite(sampled_values))
    np.testing.assert_allclose(sampled_depth, depth)
    np.testing.assert_allclose(sampled_values, values)
