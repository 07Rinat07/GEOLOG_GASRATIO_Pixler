from __future__ import annotations

from math import isfinite, log10

from geoworkbench.tablet.models import XScale


def scale_value_at_fraction(
    minimum: float,
    maximum: float,
    scale: XScale,
    fraction: float,
) -> float:
    """Project one normalized grid position into a curve engineering scale."""

    low = float(minimum)
    high = float(maximum)
    position = max(0.0, min(1.0, float(fraction)))
    if not isfinite(low) or not isfinite(high) or low >= high:
        raise ValueError("Curve scale requires finite increasing limits")
    if scale is XScale.LOGARITHMIC:
        if low <= 0.0:
            raise ValueError("Logarithmic curve scale requires a positive minimum")
        return 10.0 ** (log10(low) + (log10(high) - log10(low)) * position)
    return low + (high - low) * position


def format_scale_value(value: float) -> str:
    """Compact engineering label suitable for narrow tablet headers."""

    number = float(value)
    absolute = abs(number)
    if absolute != 0.0 and (absolute >= 100_000.0 or absolute < 0.001):
        return f"{number:.2e}"
    if absolute >= 1_000.0:
        return f"{number:.0f}"
    if absolute >= 100.0:
        return f"{number:.1f}".rstrip("0").rstrip(".")
    if absolute >= 1.0:
        return f"{number:.2f}".rstrip("0").rstrip(".")
    return f"{number:.4f}".rstrip("0").rstrip(".") or "0"
