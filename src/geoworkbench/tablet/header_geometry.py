from __future__ import annotations


CURVE_HEADER_ROW_HEIGHT = 44
CURVE_HEADER_PRINT_ROW_HEIGHT = 52
CURVE_HEADER_MAX_VISIBLE_ROWS = 7
# The last ruler paints labels and a bottom border very close to the row edge.
# A real trailing band prevents QScrollArea and PDF clipping from cutting those
# glyphs at the graph boundary.
CURVE_HEADER_BOTTOM_CLEARANCE = 8


def curve_header_content_height(
    row_count: int,
    *,
    row_height: int = CURVE_HEADER_ROW_HEIGHT,
    bottom_clearance: int = CURVE_HEADER_BOTTOM_CLEARANCE,
) -> int:
    """Return exact content height for complete parameter rows and clearance."""

    rows = max(0, int(row_count))
    height = max(1, int(row_height))
    clearance = max(0, int(bottom_clearance))
    return rows * height + (clearance if rows else 0)


def curve_header_viewport_height(
    row_count: int,
    *,
    row_height: int = CURVE_HEADER_ROW_HEIGHT,
    max_visible_rows: int = CURVE_HEADER_MAX_VISIBLE_ROWS,
    bottom_clearance: int = CURVE_HEADER_BOTTOM_CLEARANCE,
) -> int:
    """Return a viewport containing whole rows plus the trailing safety band."""

    rows = max(0, int(row_count))
    height = max(1, int(row_height))
    visible_rows = min(rows, max(1, int(max_visible_rows)))
    clearance = max(0, int(bottom_clearance))
    return visible_rows * height + (clearance if visible_rows else 0)


def align_curve_header_band_height(
    requested_height: int,
    *,
    row_height: int = CURVE_HEADER_ROW_HEIGHT,
    bottom_clearance: int = CURVE_HEADER_BOTTOM_CLEARANCE,
) -> int:
    """Round a synchronized band upward without losing the trailing clearance.

    The former implementation rounded downward and removed the last pixels of
    the final parameter row. Every track then clipped its bottom ruler at the
    same graph boundary. Rounding upward is the only safe synchronization rule:
    columns may receive a few empty pixels, but no parameter row is partial.
    """

    requested = max(0, int(requested_height))
    if requested == 0:
        return 0
    height = max(1, int(row_height))
    clearance = max(0, int(bottom_clearance))
    payload = max(1, requested - min(clearance, requested))
    rows = max(1, (payload + height - 1) // height)
    return rows * height + clearance


def curve_header_overflows(
    row_count: int,
    *,
    max_visible_rows: int = CURVE_HEADER_MAX_VISIBLE_ROWS,
) -> bool:
    return max(0, int(row_count)) > max(1, int(max_visible_rows))


# Screen-only policy; paper rendering continues to use every configured row.
TABLET_COMPACT_HEIGHT = 760
TABLET_COMPACT_WIDTH = 1000
TABLET_COMPACT_MAX_ROWS = 2


def tablet_compact_screen(mode: str, width: int, height: int) -> bool:
    """Choose density from the actual logical tablet size, not monitor pixels."""
    if mode == "compact":
        return True
    if mode == "full":
        return False
    return width < TABLET_COMPACT_WIDTH or height < TABLET_COMPACT_HEIGHT


def compact_curve_header_rows(
    viewport_height: int, title_height: int, *, minimum_plot_height: int = 240,
) -> int:
    """Budget whole parameter rows; keep the first row scrollable on small screens."""
    free = viewport_height - title_height - minimum_plot_height - CURVE_HEADER_BOTTOM_CLEARANCE
    return max(1, min(TABLET_COMPACT_MAX_ROWS, free // CURVE_HEADER_ROW_HEIGHT))
