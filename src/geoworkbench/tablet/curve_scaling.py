from __future__ import annotations

import numpy as np

from geoworkbench.tablet.models import XScale


def _normalized_curve_coordinates(
    values: np.ndarray,
    scale: XScale,
    minimum: float,
    maximum: float,
) -> np.ndarray:
    source = np.asarray(values, dtype=float)
    result = np.full(source.shape, np.nan, dtype=np.float64)
    valid = np.isfinite(source)
    if scale is XScale.LOGARITHMIC:
        valid &= source > 0
        lower = np.log10(minimum)
        upper = np.log10(maximum)
        transformed = np.full(source.shape, np.nan, dtype=np.float64)
        transformed[valid] = np.log10(source[valid])
    else:
        lower = minimum
        upper = maximum
        transformed = source
    span = upper - lower
    if not np.isfinite(span) or span <= 0:
        return result
    with np.errstate(over="ignore", invalid="ignore"):
        result[valid] = (transformed[valid] - lower) / span
    return result


def automatic_curve_range(values: np.ndarray, scale: XScale) -> tuple[float, float]:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if scale is XScale.LOGARITHMIC:
        finite = finite[finite > 0]
    if not finite.size:
        return (0.1, 100.0) if scale is XScale.LOGARITHMIC else (0.0, 1.0)
    if finite.size >= 10:
        minimum, maximum = (float(value) for value in np.nanpercentile(finite, [1.0, 99.0]))
    else:
        minimum, maximum = float(np.min(finite)), float(np.max(finite))
    if scale is XScale.LOGARITHMIC:
        minimum = max(minimum, float(np.min(finite)))
    if minimum == maximum:
        padding = max(abs(minimum) * 0.05, 0.1)
        minimum -= padding
        maximum += padding
        if scale is XScale.LOGARITHMIC:
            minimum = max(minimum, float(np.min(finite)) * 0.95)
    return minimum, maximum


def normalize_curve_values(
    values: np.ndarray,
    scale: XScale,
    minimum: float,
    maximum: float,
) -> np.ndarray:
    return np.clip(
        _normalized_curve_coordinates(values, scale, minimum, maximum),
        0.0,
        1.0,
    )


def normalize_curve_values_for_plot(
    values: np.ndarray,
    scale: XScale,
    minimum: float,
    maximum: float,
) -> np.ndarray:
    """Return continuous, painter-safe coordinates for viewport clipping.

    Off-scale samples must stay in the polyline. Replacing each such sample with
    ``NaN`` breaks a valid curve into short strokes and isolated points whenever
    it crosses the configured range. The PlotWidget already clips its children
    to the 0..1 track viewport, so an off-screen overscan preserves the entry/exit
    segment without drawing an artificial plateau on the track edge. Bounding
    the overscan to one track width on either side also prevents extreme sensor
    outliers from producing unsafe painter coordinates. Invalid values (and
    non-positive logarithmic values) remain ``NaN`` and still create genuine
    data gaps.
    """

    result = _normalized_curve_coordinates(values, scale, minimum, maximum)
    result[np.isneginf(result)] = -1.0
    result[np.isposinf(result)] = 2.0
    finite = np.isfinite(result)
    result[finite] = np.clip(result[finite], -1.0, 2.0)
    return result
