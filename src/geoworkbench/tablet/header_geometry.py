from __future__ import annotations

CURVE_HEADER_ROW_HEIGHT = 58
CURVE_HEADER_MAX_VISIBLE_ROWS = 6
CURVE_HEADER_BOTTOM_CLEARANCE = 2


def curve_header_content_height(
    row_count: int,
    *,
    row_height: int = CURVE_HEADER_ROW_HEIGHT,
    bottom_clearance: int = CURVE_HEADER_BOTTOM_CLEARANCE,
) -> int:
    """Return exact content height for whole curve-header rows.

    The bottom clearance keeps the last row border above the graph body when the
    scroll area is at its maximum position.  Negative counts are treated as an
    empty header so malformed external layouts cannot produce negative geometry.
    """

    rows = max(0, int(row_count))
    height = max(1, int(row_height))
    clearance = max(0, int(bottom_clearance))
    return rows * height + (clearance if rows else 0)


def curve_header_viewport_height(
    row_count: int,
    *,
    row_height: int = CURVE_HEADER_ROW_HEIGHT,
    max_visible_rows: int = CURVE_HEADER_MAX_VISIBLE_ROWS,
) -> int:
    """Return a viewport height containing only complete parameter rows."""

    rows = max(0, int(row_count))
    height = max(1, int(row_height))
    visible_rows = min(rows, max(1, int(max_visible_rows)))
    return visible_rows * height


def align_curve_header_band_height(
    requested_height: int,
    *,
    row_height: int = CURVE_HEADER_ROW_HEIGHT,
) -> int:
    """Snap a synchronized band down to a whole number of header rows.

    A non-integral row height is the direct cause of the bottom parameter being
    shown only partially.  The common band remains aligned between tracks, while
    dense tracks expose additional rows through their internal scrollbar.
    """

    requested = max(0, int(requested_height))
    if requested == 0:
        return 0
    height = max(1, int(row_height))
    return max(height, requested // height * height)


def curve_header_overflows(
    row_count: int,
    *,
    max_visible_rows: int = CURVE_HEADER_MAX_VISIBLE_ROWS,
) -> bool:
    return max(0, int(row_count)) > max(1, int(max_visible_rows))
