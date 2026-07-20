import numpy as np
import pytest

from geoworkbench.tablet.sampling import select_visible_samples


def test_select_visible_samples_filters_depth_and_invalid_values() -> None:
    depth = np.array([99.0, 100.0, 101.0, 102.0, np.nan])
    values = np.array([1.0, 2.0, np.nan, 4.0, 5.0])

    selected_values, selected_depth = select_visible_samples(depth, values, 100.0, 102.0)

    np.testing.assert_allclose(selected_depth, [100.0, 102.0])
    np.testing.assert_allclose(selected_values, [2.0, 4.0])


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

    np.testing.assert_allclose(selected_values, [1.0])
    np.testing.assert_allclose(selected_depth, [3.0])


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
