from __future__ import annotations

import colorsys
import re

PROFESSIONAL_CURVE_PALETTE: tuple[str, ...] = (
    "#1d4ed8",  # blue
    "#b91c1c",  # red
    "#047857",  # green
    "#7c3aed",  # violet
    "#b45309",  # ochre
    "#0e7490",  # cyan/teal
    "#475569",  # slate
    "#be185d",  # magenta
)


def professional_curve_color(index: int) -> str:
    return PROFESSIONAL_CURVE_PALETTE[int(index) % len(PROFESSIONAL_CURVE_PALETTE)]


def muted_screen_curve_color(color: str) -> str:
    """Return a restrained screen-only version of a configured curve colour.

    The persisted colour remains unchanged and is still used for print/export.
    Only the interactive tablet receives reduced saturation and bounded
    lightness, which avoids the saturated "rainbow" effect in multi-curve tracks.
    """

    if not isinstance(color, str) or re.fullmatch(r"#[0-9A-Fa-f]{6}", color) is None:
        color = "#1d4ed8"
    red = int(color[1:3], 16) / 255.0
    green = int(color[3:5], 16) / 255.0
    blue = int(color[5:7], 16) / 255.0
    hue, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)
    if saturation < 0.08:
        saturation = min(saturation, 0.05)
    else:
        saturation = min(saturation, 0.66)
    lightness = min(0.54, max(0.30, lightness))
    red, green, blue = colorsys.hls_to_rgb(hue, lightness, saturation)
    return f"#{round(red * 255):02x}{round(green * 255):02x}{round(blue * 255):02x}"


def screen_curve_width(configured_width: float, curve_count: int) -> float:
    """Reduce only ordinary thin pens when several curves share one track."""

    width = max(0.5, float(configured_width))
    count = max(1, int(curve_count))
    if width > 1.8:
        return width
    if count >= 5:
        return min(width, 1.10)
    if count >= 3:
        return min(width, 1.25)
    return min(width, 1.40)


def screen_grid_alpha(configured_alpha: float, *, major: bool) -> float:
    alpha = max(0.0, min(1.0, float(configured_alpha)))
    return alpha * (0.72 if major else 0.16)


def minor_grid_is_readable(
    viewport_pixels: int,
    major_divisions: int,
    minor_divisions: int,
    *,
    minimum_spacing_pixels: float = 7.0,
) -> bool:
    major = max(1, int(major_divisions))
    minor = max(1, int(minor_divisions))
    if minor <= 1:
        return False
    spacing = max(0, int(viewport_pixels)) / float(major * minor)
    return spacing >= float(minimum_spacing_pixels)
