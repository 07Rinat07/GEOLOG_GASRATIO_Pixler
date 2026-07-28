import numpy as np
import pytest

from geoworkbench.tablet.sampling import (
    select_visible_samples,
    snap_viewport_to_axis_samples,
)


def test_select_visible_samples_filters_depth_and_invalid_values() -> None:
    depth = np.array([99.0, 100.0, 101.0, 102.0, np.nan])
    values = np.array([1.0, 2.0, np.nan, 4.0, 5.0])

    selected_values, selected_depth = select_visible_samples(depth, values, 100.0, 102.0)

    # One source sample immediately above the viewport is retained so the
    # first visible line segment is not clipped during wheel scrolling.
    np.testing.assert_allclose(selected_depth, [99.0, 100.0, 101.0, 102.0])
    np.testing.assert_allclose(selected_values, [1.0, 2.0, np.nan, 4.0], equal_nan=True)


def test_select_visible_samples_decimates_and_preserves_interval_edges() -> None:
    depth = np.arange(20_000, dtype=np.float64)
    values = depth * 2.0

    selected_values, selected_depth = select_visible_samples(
        depth,
        values,
        0.0,
        19_999.0,
        max_points=1000,
    )

    assert len(selected_depth) == 1000
    assert selected_depth[0] == 0.0
    assert selected_depth[-1] == 19_999.0
    assert selected_values[0] == 0.0
    assert selected_values[-1] == 39_998.0


def test_select_visible_samples_can_require_positive_values() -> None:
    depth = np.array([1.0, 2.0, 3.0])
    values = np.array([-1.0, 0.0, 1.0])

    selected_values, selected_depth = select_visible_samples(
        depth,
        values,
        1.0,
        3.0,
        positive_values_only=True,
    )

    np.testing.assert_allclose(selected_values, [np.nan, np.nan, 1.0], equal_nan=True)
    np.testing.assert_allclose(selected_depth, [1.0, 2.0, 3.0])


def test_select_visible_samples_preserves_narrow_peaks_and_valleys() -> None:
    depth = np.arange(100_000, dtype=np.float64)
    values = np.zeros_like(depth)
    values[12_345] = 900.0
    values[67_890] = -700.0

    selected_values, selected_depth = select_visible_samples(
        depth, values, 0.0, 99_999.0, max_points=1000
    )

    assert selected_depth.size <= 1000
    assert np.max(selected_values) == 900.0
    assert np.min(selected_values) == -700.0
    assert 12_345.0 in selected_depth
    assert 67_890.0 in selected_depth


def test_select_visible_samples_rejects_invalid_input() -> None:
    with pytest.raises(ValueError, match="одинаковую форму"):
        select_visible_samples(np.array([1.0]), np.array([1.0, 2.0]), 0.0, 2.0)
    with pytest.raises(ValueError, match="минимум две"):
        select_visible_samples(np.array([1.0]), np.array([1.0]), 0.0, 2.0, max_points=1)


def test_select_visible_samples_sorts_depth_and_collapses_duplicates() -> None:
    depth = np.array([102.0, 100.0, 101.0, 101.0, 103.0])
    values = np.array([20.0, 10.0, 30.0, 50.0, 40.0])

    selected_values, selected_depth = select_visible_samples(depth, values, 100.0, 103.0)

    np.testing.assert_allclose(selected_depth, [100.0, 101.0, 102.0, 103.0])
    np.testing.assert_allclose(selected_values, [10.0, 40.0, 20.0, 40.0])


def test_select_visible_samples_skips_sort_for_monotonic_axis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    depth = np.arange(10_000, dtype=np.float64)
    values = depth * 2.0

    def fail_if_sorted(*_args: object, **_kwargs: object) -> np.ndarray:
        raise AssertionError("monotonic axes must not allocate a sort permutation")

    monkeypatch.setattr(np, "argsort", fail_if_sorted)

    selected_values, selected_depth = select_visible_samples(
        depth,
        values,
        100.0,
        200.0,
    )

    assert selected_depth[0] == 98.0
    assert selected_depth[-1] == 202.0
    assert selected_values[0] == 196.0


def test_select_visible_samples_keeps_real_zero_and_breaks_null_interval() -> None:
    depth = np.array([100.0, 101.0, 102.0, 103.0])
    values = np.array([4.0, 0.0, np.nan, 7.0])

    selected_values, selected_depth = select_visible_samples(depth, values, 100.0, 103.0)

    np.testing.assert_allclose(selected_depth, depth)
    np.testing.assert_allclose(selected_values, values, equal_nan=True)
    assert selected_values[1] == 0.0
    assert np.isnan(selected_values[2])


def test_select_visible_samples_inserts_break_for_large_axis_hole() -> None:
    depth = np.array([100.0, 101.0, 102.0, 120.0, 121.0])
    values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

    selected_values, selected_depth = select_visible_samples(depth, values, 100.0, 121.0)

    gap_indexes = np.flatnonzero(np.isnan(selected_values))
    assert gap_indexes.size == 1
    assert 102.0 < selected_depth[gap_indexes[0]] < 120.0


def test_select_visible_samples_keeps_curve_visible_between_source_rows() -> None:
    axis = np.array([0.0, 10.0, 20.0, 30.0])
    values = np.array([1.0, 2.0, 3.0, 4.0])

    selected_values, selected_axis = select_visible_samples(
        axis, values, 12.0, 18.0
    )

    assert selected_axis[0] <= 10.0
    assert selected_axis[-1] >= 20.0
    assert np.all(np.isfinite(selected_values))


def test_select_visible_samples_does_not_bridge_real_gap_when_viewport_is_inside_it() -> None:
    axis = np.array([0.0, 1.0, 2.0, 100.0, 101.0, 102.0])
    values = np.arange(axis.size, dtype=np.float64)

    selected_values, selected_axis = select_visible_samples(
        axis, values, 40.0, 60.0
    )

    gap_positions = np.flatnonzero(np.isnan(selected_values))
    assert gap_positions.size == 1
    assert 2.0 < selected_axis[gap_positions[0]] < 100.0


def test_empty_time_viewport_snaps_to_nearest_recorded_window() -> None:
    axis = np.array([0.0, 1.0, 2.0, 100.0, 101.0, 102.0])

    top, bottom = snap_viewport_to_axis_samples(axis, 40.0, 60.0)

    assert bottom - top == pytest.approx(20.0)
    assert np.any((axis >= top) & (axis <= bottom))


def test_nonempty_viewport_is_not_moved() -> None:
    axis = np.array([0.0, 1.0, 2.0, 100.0])

    assert snap_viewport_to_axis_samples(axis, 0.5, 1.5) == pytest.approx((0.5, 1.5))
