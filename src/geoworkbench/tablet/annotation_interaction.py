from __future__ import annotations


RESIZE_HANDLES = frozenset({"nw", "n", "ne", "e", "se", "s", "sw", "w"})
CATALOG_SYMBOL_MINIMUM_DIMENSION = 2.0


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
    preserve_aspect: bool = False,
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
    original_width = max(float(width), minimum_width)
    original_height = max(float(height), minimum_height)
    right = left + original_width
    bottom = top + original_height
    if preserve_aspect:
        return _resize_with_aspect_ratio(
            left,
            top,
            right,
            bottom,
            handle,
            float(dx),
            float(dy),
            minimum_width=minimum_width,
            minimum_height=minimum_height,
        )
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


def _resize_with_aspect_ratio(
    left: float,
    top: float,
    right: float,
    bottom: float,
    handle: str,
    dx: float,
    dy: float,
    *,
    minimum_width: float,
    minimum_height: float,
) -> tuple[float, float, float, float]:
    """Resize while preserving the starting width/height ratio.

    Corner handles keep the opposite corner fixed. Side handles use the dragged
    edge as the primary dimension and expand/contract the perpendicular
    dimension around its centre. This gives symbols a predictable CAD-style
    Shift modifier without changing the normal free-stretch behaviour.
    """

    original_width = right - left
    original_height = bottom - top
    ratio = original_width / original_height
    minimum_scale = max(
        float(minimum_width) / original_width,
        float(minimum_height) / original_height,
    )

    if handle in {"e", "w"}:
        candidate_width = original_width + (dx if handle == "e" else -dx)
        scale = max(minimum_scale, candidate_width / original_width)
        new_width = original_width * scale
        new_height = original_height * scale
        center_y = (top + bottom) / 2.0
        top = center_y - new_height / 2.0
        bottom = center_y + new_height / 2.0
        if handle == "e":
            right = left + new_width
        else:
            left = right - new_width
        return left, top, right - left, bottom - top

    if handle in {"n", "s"}:
        candidate_height = original_height + (dy if handle == "s" else -dy)
        scale = max(minimum_scale, candidate_height / original_height)
        new_width = original_width * scale
        new_height = original_height * scale
        center_x = (left + right) / 2.0
        left = center_x - new_width / 2.0
        right = center_x + new_width / 2.0
        if handle == "s":
            bottom = top + new_height
        else:
            top = bottom - new_height
        return left, top, right - left, bottom - top

    candidate_width = original_width + (dx if "e" in handle else -dx)
    candidate_height = original_height + (dy if "s" in handle else -dy)
    scale_x = candidate_width / original_width
    scale_y = candidate_height / original_height
    scale = scale_x if abs(scale_x - 1.0) >= abs(scale_y - 1.0) else scale_y
    scale = max(minimum_scale, scale)
    new_width = original_width * scale
    new_height = original_height * scale

    if "w" in handle:
        left = right - new_width
    else:
        right = left + new_width
    if "n" in handle:
        top = bottom - new_height
    else:
        bottom = top + new_height
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
