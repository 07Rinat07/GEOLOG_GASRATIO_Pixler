from __future__ import annotations

import pytest

from geoworkbench.tablet.curve_scale import format_scale_value, scale_value_at_fraction
from geoworkbench.tablet.models import XScale


def test_linear_header_scale_matches_normalized_grid_fraction() -> None:
    assert scale_value_at_fraction(0.0, 100.0, XScale.LINEAR, 0.2) == pytest.approx(20.0)
    assert scale_value_at_fraction(0.0, 100.0, XScale.LINEAR, 0.8) == pytest.approx(80.0)


def test_logarithmic_header_scale_matches_normalized_grid_fraction() -> None:
    assert scale_value_at_fraction(0.001, 100.0, XScale.LOGARITHMIC, 0.0) == pytest.approx(0.001)
    assert scale_value_at_fraction(0.001, 100.0, XScale.LOGARITHMIC, 1.0) == pytest.approx(100.0)
    assert scale_value_at_fraction(0.001, 100.0, XScale.LOGARITHMIC, 0.6) == pytest.approx(1.0)


def test_logarithmic_header_scale_rejects_non_positive_minimum() -> None:
    with pytest.raises(ValueError, match="positive"):
        scale_value_at_fraction(0.0, 100.0, XScale.LOGARITHMIC, 0.5)


def test_header_scale_value_formatter_is_compact() -> None:
    assert format_scale_value(20.0) == "20"
    assert format_scale_value(0.0001) == "1.00e-04"
    assert format_scale_value(123456.0) == "1.23e+05"
