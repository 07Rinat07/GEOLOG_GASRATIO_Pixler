import pytest

from geoworkbench.domain.stratigraphy_presentation import (
    stratigraphy_text_angle,
    stratigraphy_text_position_fraction,
)


def test_stratigraphy_text_angles_follow_reading_direction() -> None:
    assert stratigraphy_text_angle("horizontal") == 0.0
    assert stratigraphy_text_angle("vertical_bottom_to_top") == -90.0
    assert stratigraphy_text_angle("vertical_top_to_bottom") == 90.0


def test_stratigraphy_text_positions_keep_center_as_default() -> None:
    assert stratigraphy_text_position_fraction(None) == 0.5
    assert stratigraphy_text_position_fraction("top") < 0.5
    assert stratigraphy_text_position_fraction("bottom") > 0.5


def test_stratigraphy_text_presentation_rejects_unknown_values() -> None:
    with pytest.raises(ValueError):
        stratigraphy_text_angle("diagonal")
    with pytest.raises(ValueError):
        stratigraphy_text_position_fraction("outside")
