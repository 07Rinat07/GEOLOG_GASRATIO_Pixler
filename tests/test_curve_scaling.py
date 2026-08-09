import numpy as np

from geoworkbench.tablet.curve_scaling import (
    automatic_curve_range,
    normalize_curve_values,
    normalize_curve_values_for_plot,
)
from geoworkbench.tablet.models import XScale


def test_linear_values_are_normalized_to_track_width() -> None:
    result = normalize_curve_values(np.array([0.0, 50.0, 100.0]), XScale.LINEAR, 0.0, 100.0)
    assert np.allclose(result, [0.0, 0.5, 1.0])


def test_values_outside_manual_range_are_clipped() -> None:
    result = normalize_curve_values(np.array([-5.0, 5.0, 15.0]), XScale.LINEAR, 0.0, 10.0)
    assert np.allclose(result, [0.0, 0.5, 1.0])


def test_plotting_preserves_off_scale_samples_for_viewport_clipping() -> None:
    result = normalize_curve_values_for_plot(
        np.array([-5.0, 0.0, 5.0, 10.0, 15.0]),
        XScale.LINEAR,
        0.0,
        10.0,
    )

    assert np.allclose(result, [-0.5, 0.0, 0.5, 1.0, 1.5])


def test_plotting_bounds_extreme_outliers_outside_the_visible_track() -> None:
    result = normalize_curve_values_for_plot(
        np.array([-1e308, 5.0, 1e308]),
        XScale.LINEAR,
        0.0,
        1e-308,
    )

    assert np.allclose(result, [-1.0, 2.0, 2.0])


def test_plotting_preserves_logarithmic_samples_outside_selected_decades() -> None:
    result = normalize_curve_values_for_plot(
        np.array([0.01, 0.1, 1.0, 10.0, 100.0]),
        XScale.LOGARITHMIC,
        0.1,
        10.0,
    )

    assert np.allclose(result, [-0.5, 0.0, 0.5, 1.0, 1.5])


def test_plotting_keeps_only_real_invalid_values_as_gaps() -> None:
    result = normalize_curve_values_for_plot(
        np.array([-1.0, 0.0, 1.0, np.nan, 10.0]),
        XScale.LOGARITHMIC,
        0.1,
        10.0,
    )

    assert np.isnan(result[0])
    assert np.isnan(result[1])
    assert result[2] == 0.5
    assert np.isnan(result[3])
    assert result[4] == 1.0


def test_logarithmic_values_are_normalized_by_decades() -> None:
    result = normalize_curve_values(
        np.array([0.1, 1.0, 10.0, 100.0]), XScale.LOGARITHMIC, 0.1, 100.0
    )
    assert np.allclose(result, [0.0, 1 / 3, 2 / 3, 1.0])


def test_logarithmic_non_positive_values_are_hidden() -> None:
    result = normalize_curve_values(np.array([-1.0, 0.0, 1.0]), XScale.LOGARITHMIC, 0.1, 10.0)
    assert np.isnan(result[0])
    assert np.isnan(result[1])
    assert np.isfinite(result[2])


def test_automatic_range_ignores_outlier_edges() -> None:
    values = np.concatenate([np.linspace(0.0, 100.0, 1000), np.array([1e9])])
    minimum, maximum = automatic_curve_range(values, XScale.LINEAR)
    assert minimum >= 0.0
    assert maximum < 1e9
