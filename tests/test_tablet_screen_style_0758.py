from geoworkbench.tablet.screen_style import (
    PROFESSIONAL_CURVE_PALETTE,
    minor_grid_is_readable,
    muted_screen_curve_color,
    professional_curve_color,
    screen_curve_width,
    screen_grid_alpha,
)


def test_professional_palette_is_deterministic_and_not_neon() -> None:
    assert professional_curve_color(0) == PROFESSIONAL_CURVE_PALETTE[0]
    assert professional_curve_color(len(PROFESSIONAL_CURVE_PALETTE)) == PROFESSIONAL_CURVE_PALETTE[0]
    assert "#00ff00" not in PROFESSIONAL_CURVE_PALETTE
    assert "#ff00ff" not in PROFESSIONAL_CURVE_PALETTE


def test_screen_colour_reduces_extreme_saturation_without_changing_persisted_value() -> None:
    assert muted_screen_curve_color("#00ffff") != "#00ffff"
    assert muted_screen_curve_color("#ff0000") != "#ff0000"
    assert muted_screen_curve_color("#475569") == "#475569"


def test_dense_tracks_use_thinner_screen_pens_but_keep_intentional_thick_lines() -> None:
    assert screen_curve_width(1.5, 6) == 1.10
    assert screen_curve_width(1.5, 3) == 1.25
    assert screen_curve_width(3.0, 8) == 3.0


def test_minor_grid_is_hidden_when_pixel_spacing_is_too_dense() -> None:
    assert minor_grid_is_readable(80, 5, 5) is False
    assert minor_grid_is_readable(300, 5, 5) is True
    assert screen_grid_alpha(0.2, major=True) == 0.144
    assert screen_grid_alpha(0.2, major=False) == 0.032
