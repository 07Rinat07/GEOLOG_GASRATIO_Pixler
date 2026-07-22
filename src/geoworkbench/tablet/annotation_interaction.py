from __future__ import annotations


RESIZE_HANDLES = frozenset({"nw", "n", "ne", "e", "se", "s", "sw", "w"})


def resize_annotation_geometry(
    offset_x: float,
    offset_y: float,
    width: float,
    height: float,
    handle: str,
    dx: float,
    dy: float,
    *,
    minimum_width: float = 48.0,
    minimum_height: float = 28.0,
) -> tuple[float, float, float, float]:
    """Resize an annotation from any edge or corner.

    The opposite edge stays fixed, matching the interaction model used by
    professional drawing/CAD applications.  Geometry is returned in the same
    anchor-relative coordinate system that is persisted in the project.
    """

    if handle not in RESIZE_HANDLES:
        raise ValueError(f"Unknown annotation resize handle: {handle}")
    if minimum_width <= 0 or minimum_height <= 0:
        raise ValueError("Minimum annotation dimensions must be positive")

    left = float(offset_x)
    top = float(offset_y)
    right = left + max(float(width), minimum_width)
    bottom = top + max(float(height), minimum_height)
    if "w" in handle:
        left += float(dx)
    if "e" in handle:
        right += float(dx)
    if "n" in handle:
        top += float(dy)
    if "s" in handle:
        bottom += float(dy)
    if right - left < minimum_width:
        if "w" in handle:
            left = right - minimum_width
        else:
            right = left + minimum_width
    if bottom - top < minimum_height:
        if "n" in handle:
            top = bottom - minimum_height
        else:
            bottom = top + minimum_height
    return left, top, right - left, bottom - top


def keep_annotation_reachable(
    anchor_x: float,
    anchor_y: float,
    offset_x: float,
    offset_y: float,
    width: float,
    height: float,
    canvas_width: float,
    canvas_height: float,
    *,
    visible_margin: float = 20.0,
) -> tuple[float, float]:
    """Keep a small draggable part of a freely positioned box on the canvas."""

    margin = max(1.0, float(visible_margin))
    left = float(anchor_x) + float(offset_x)
    top = float(anchor_y) + float(offset_y)
    right_limit = max(margin, float(canvas_width) - margin)
    bottom_limit = max(margin, float(canvas_height) - margin)
    left = min(max(left, -float(width) + margin), right_limit)
    top = min(max(top, -float(height) + margin), bottom_limit)
    return left - float(anchor_x), top - float(anchor_y)
