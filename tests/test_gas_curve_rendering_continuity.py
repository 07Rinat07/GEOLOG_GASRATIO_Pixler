from __future__ import annotations

import numpy as np

from geoworkbench.tablet.geometry_cache import (
    CurveGeometryCache,
    CurveGeometryKey,
)
from geoworkbench.tablet.relative_gas import build_relative_gas_stack
from geoworkbench.tablet.sampling import select_visible_samples
from geoworkbench.tablet.tablet_view import CurveHeaderLabel


def _geometry_key(curve_id: str, top: float, bottom: float) -> CurveGeometryKey:
    return CurveGeometryKey(
        curve_id=curve_id,
        axis_id="depth",
        values_revision="values-v1",
        axis_revision="axis-v1",
        top=top,
        bottom=bottom,
        max_points=256,
        positive_values_only=False,
    )


def _value_at(
    sampled_axis: np.ndarray, sampled_values: np.ndarray, axis_value: float
) -> float:
    matches = np.flatnonzero(np.isclose(sampled_axis, axis_value))
    assert matches.size == 1
    return float(sampled_values[int(matches[0])])


def test_relative_gas_print_header_uses_same_compact_font_as_rulers(qapp) -> None:
    label = CurveHeaderLabel(
        "C1_REL",
        "Метан C1\n0 … 100 % · Σ=100%",
        "#111827",
    )

    label.set_print_mode(True)

    assert "font-size: 10px" in label.styleSheet()
    assert "font-size: 16px" not in label.styleSheet()
    label.close()


def test_default_sampling_preserves_missing_rows() -> None:
    axis = np.arange(0.0, 31.0)
    values = np.full(axis.shape, np.nan)
    values[[0, 3, 30]] = (10.0, 13.0, 20.0)

    sampled_values, sampled_axis = select_visible_samples(
        axis, values, 0.0, 30.0, max_points=256
    )

    assert np.isnan(_value_at(sampled_axis, sampled_values, 1.0))
    assert np.isnan(_value_at(sampled_axis, sampled_values, 10.0))


def test_gas_geometry_bridges_short_sparse_updates_but_keeps_long_outage() -> None:
    axis = np.arange(0.0, 31.0)
    values = np.full(axis.shape, np.nan)
    values[[0, 3, 30]] = (10.0, 13.0, 20.0)
    cache = CurveGeometryCache()

    sampled_values, sampled_axis = cache.get_or_build(
        _geometry_key("C1", 0.0, 30.0), axis, values
    )

    assert _value_at(sampled_axis, sampled_values, 1.0) == 11.0
    assert _value_at(sampled_axis, sampled_values, 2.0) == 12.0
    assert np.isnan(_value_at(sampled_axis, sampled_values, 10.0))


def test_non_gas_geometry_keeps_the_original_gap_policy() -> None:
    axis = np.arange(0.0, 6.0)
    values = np.array([1.0, np.nan, np.nan, 4.0, 5.0, 6.0])
    cache = CurveGeometryCache()

    sampled_values, sampled_axis = cache.get_or_build(
        _geometry_key("GR", 0.0, 5.0), axis, values
    )

    assert np.isnan(_value_at(sampled_axis, sampled_values, 1.0))
    assert np.isnan(_value_at(sampled_axis, sampled_values, 2.0))


def test_gas_geometry_keeps_context_points_across_page_edges() -> None:
    axis = np.arange(0.0, 21.0)
    values = axis * 2.0
    cache = CurveGeometryCache()

    gas_values, gas_axis = cache.get_or_build(
        _geometry_key("TG_CALC", 10.1, 11.1), axis, values
    )
    generic_values, generic_axis = cache.get_or_build(
        _geometry_key("ROP", 10.1, 11.1), axis, values
    )

    assert gas_values.size == gas_axis.size
    assert generic_values.size == generic_axis.size
    assert gas_axis.min() < 10.1
    assert gas_axis.max() > 11.1
    assert gas_axis.size > generic_axis.size


def test_relative_gas_interpolates_short_rows_and_preserves_long_outage() -> None:
    axis = np.arange(0.0, 31.0)
    methane = np.full(axis.shape, np.nan)
    ethane = np.full(axis.shape, np.nan)
    methane[[0, 3, 30]] = (80.0, 70.0, 60.0)
    ethane[[0, 3, 30]] = (20.0, 30.0, 40.0)

    stack = build_relative_gas_stack(
        axis,
        {"C1_REL": methane, "C2_REL": ethane},
        0.0,
        30.0,
        max_points=256,
    )

    first_band = stack.bands[0]
    final_band = stack.bands[-1]
    index_one = int(np.flatnonzero(np.isclose(stack.depth, 1.0))[0])
    index_ten = int(np.flatnonzero(np.isclose(stack.depth, 10.0))[0])

    assert np.isfinite(first_band.upper[index_one])
    assert final_band.upper[index_one] == 100.0
    assert np.isnan(first_band.upper[index_ten])
    assert np.isnan(final_band.upper[index_ten])
