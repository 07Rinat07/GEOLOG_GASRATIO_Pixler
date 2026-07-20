from __future__ import annotations

import numpy as np

from geoworkbench.tablet.models import XScale


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
    result[valid] = (transformed[valid] - lower) / span
    return np.clip(result, 0.0, 1.0)
