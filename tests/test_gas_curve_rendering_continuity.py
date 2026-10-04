from __future__ import annotations

import numpy as np

from geoworkbench.tablet.geometry_cache import (
    CurveGeometryCache,
    CurveGeometryKey,
    is_gas_curve_id,
)
from geoworkbench.tablet.relative_gas import build_relative_gas_stack
from geoworkbench.tablet.sampling import select_visible_samples
from geoworkbench.services.gas_curve_presentation import (
    GAS_SCATTER_VERTICAL_SPACING,
    GAS_SCREEN_POINT_SIZE_PX,
    gas_scatter_point_budget,
    is_gas_point_mnemonic,
    select_gas_scatter_samples,
)
from geoworkbench.tablet.tablet_view import CurveHeaderLabel


def _geometry_key(
    curve_id: str,
    top: float,
    bottom: float,
    *,
    positive_values_only: bool = False,
) -> CurveGeometryKey:
    return CurveGeometryKey(
        curve_id=curve_id,
        axis_id="depth",
        values_revision="values-v1",
        axis_revision="axis-v1",
        top=top,
        bottom=bottom,
        max_points=256,
        positive_values_only=positive_values_only,
    )


def _value_at(
    sampled_axis: np.ndarray, sampled_values: np.ndarray, axis_value: float
) -> float:
    matches = np.flatnonzero(np.isclose(sampled_axis, axis_value))
    assert matches.size == 1
    return float(sampled_values[int(matches[0])])


def test_gas_point_presentation_is_limited_to_ratios_and_interpretation() -> None:
    for mnemonic in (
        "WH",
        "BH",
        "CH",
        "WETNESS",
        "C1_C2",
        "C1_C4",
        "IC4_NC4",
        "PIXLER_C1_C3",
        "OPUS3",
        "OPUS_K1_3",
        "OPUS_GM_1",
        "OPUS_GM_5",
    ):
        assert is_gas_point_mnemonic(mnemonic)

    for mnemonic in (
        "C1",
        "NC5",
        "TG",
        "TG_CALC",
        "C1_NORM",
        "C1_NORM_REF",
        "OPUS_TG_PCT",
        "C1_REL",
        "ROP",
        "DEXP",
    ):
        assert not is_gas_point_mnemonic(mnemonic)


def test_gas_scatter_budget_and_marker_are_compact() -> None:
    assert GAS_SCREEN_POINT_SIZE_PX < 2.0
    assert GAS_SCATTER_VERTICAL_SPACING <= 1.5
    assert gas_scatter_point_budget(180.0) == int(
        180.0 / GAS_SCATTER_VERTICAL_SPACING
    )
    assert gas_scatter_point_budget(900.0) == int(
        900.0 / GAS_SCATTER_VERTICAL_SPACING
    )


def test_gas_scatter_sampling_groups_dense_buckets_in_constant_flatnonzero_calls(
    monkeypatch,
) -> None:
    import geoworkbench.services.gas_curve_presentation as presentation

    original_flatnonzero = presentation.np.flatnonzero
    calls = 0

    def counted_flatnonzero(values):
        nonlocal calls
        calls += 1
        return original_flatnonzero(values)

    monkeypatch.setattr(presentation.np, "flatnonzero", counted_flatnonzero)
    axis = np.linspace(0.0, 1_000.0, 200_001, dtype=np.float64)
    values = 2.0 + np.sin(axis * 0.2)

    sampled_values, sampled_axis = presentation.select_gas_scatter_samples(
        axis,
        values,
        0.0,
        1_000.0,
        max_points=1_200,
    )

    assert 0 < sampled_values.size <= 1_200
    assert sampled_values.size == sampled_axis.size
    # One call selects factual rows; one identifies monotonic bucket boundaries.
    assert calls <= 3


def test_gas_scatter_sampling_keeps_sparse_points_and_bounds_dense_cloud() -> None:
    axis = np.arange(3_601, dtype=np.float64)
    sparse = np.full(axis.shape, np.nan, dtype=np.float64)
    sparse[1_235] = 2.5

    sparse_values, sparse_axis = select_gas_scatter_samples(
        axis,
        sparse,
        0.0,
        3_600.0,
        max_points=72,
    )

    np.testing.assert_allclose(sparse_values, [2.5])
    np.testing.assert_allclose(sparse_axis, [1_235.0])

    dense = 2.0 + np.sin(axis / 7.0)
    dense_values, dense_axis = select_gas_scatter_samples(
        axis,
        dense,
        0.0,
        3_600.0,
        max_points=72,
    )

    assert 1 < dense_values.size <= 72
    assert dense_values.size == dense_axis.size
    assert np.all(np.diff(dense_axis) >= 0.0)
    assert float(np.min(dense_values)) < 1.2
    assert float(np.max(dense_values)) > 2.8


def test_sparse_continuity_policy_is_limited_to_gas_curves() -> None:
    gas_ids = (
        "C1",
        "IC4",
        "TOTAL_GAS",
        "TG_CALC",
        "C1_REL",
        "C1_NORM_REF",
        "WETNESS",
        "IC4_NC4",
        "PIXLER_C1_C2",
    )

    assert all(is_gas_curve_id(curve_id) for curve_id in gas_ids)
    assert not is_gas_curve_id("ROP")
    assert not is_gas_curve_id("GR")
    assert not is_gas_curve_id("DEXP")


def test_geometry_cache_honors_explicit_point_series_for_vendor_alias() -> None:
    axis = np.linspace(0.0, 100.0, 2_001)
    values = 2.0 + np.sin(axis)
    cache = CurveGeometryCache()
    key = CurveGeometryKey(
        curve_id="VENDOR_RATIO_17",
        axis_id="depth",
        values_revision="vendor-values",
        axis_revision="vendor-axis",
        top=0.0,
        bottom=100.0,
        max_points=80,
        positive_values_only=False,
        point_series=True,
    )

    sampled_values, sampled_axis = cache.get_or_build(key, axis, values)

    assert 0 < sampled_values.size <= 80
    assert sampled_values.size == sampled_axis.size
    assert np.all(np.isfinite(sampled_values))
    assert np.all(np.diff(sampled_axis) >= 0.0)


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


def test_logarithmic_raw_gas_keeps_explicit_zero_as_a_break() -> None:
    axis = np.arange(0.0, 5.0)
    values = np.array([1.0, np.nan, 0.0, np.nan, 100.0])
    cache = CurveGeometryCache()

    sampled_values, sampled_axis = cache.get_or_build(
        _geometry_key("C1", 0.0, 4.0, positive_values_only=True),
        axis,
        values,
    )

    assert np.isnan(_value_at(sampled_axis, sampled_values, 2.0))
    assert np.isfinite(_value_at(sampled_axis, sampled_values, 1.0))
    assert np.isfinite(_value_at(sampled_axis, sampled_values, 3.0))


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
