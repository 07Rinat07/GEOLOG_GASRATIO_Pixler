from __future__ import annotations


def lithology_label_is_visible(
    interval_top: float,
    interval_bottom: float,
    visible_top: float,
    visible_bottom: float,
    viewport_height: int,
    *,
    minimum_pixels: int,
) -> bool:
    visible_span = visible_bottom - visible_top
    if visible_span <= 0 or viewport_height <= 0 or minimum_pixels < 0:
        return False
    midpoint = (interval_top + interval_bottom) / 2.0
    if midpoint < visible_top or midpoint > visible_bottom:
        return False
    pixel_height = (interval_bottom - interval_top) / visible_span * viewport_height
    return pixel_height >= minimum_pixels
