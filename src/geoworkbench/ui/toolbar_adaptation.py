from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class ToolbarAdaptation:
    """Responsive state for a horizontal application toolbar."""

    compact: bool
    ultra_compact: bool
    required_width: int
    fits_available_width: bool


def required_toolbar_width(
    item_widths: Iterable[int],
    *,
    spacing: int = 0,
    chrome_width: int = 0,
) -> int:
    """Return a conservative logical-pixel width for toolbar contents.

    Qt reports both window geometry and widget size hints in logical pixels, so
    this calculation remains valid at 100%, 125%, 150% and other Windows DPI
    scales.  ``chrome_width`` reserves toolbar padding, borders and a small
    safety allowance for platform-specific style metrics.
    """

    widths = [max(0, int(value)) for value in item_widths]
    gap = max(0, int(spacing))
    chrome = max(0, int(chrome_width))
    return sum(widths) + gap * max(0, len(widths) - 1) + chrome


def choose_toolbar_adaptation(
    available_width: int,
    expanded_width: int,
    compact_width: int,
    ultra_compact_width: int,
    *,
    currently_compact: bool = False,
    currently_ultra_compact: bool = False,
    restore_margin: int = 72,
    safety_margin: int = 20,
) -> ToolbarAdaptation:
    """Choose the smallest visual reduction needed for the measured toolbar.

    Unlike a fixed screen-width threshold, this function compares the actual
    size hints of the localized toolbar in all three modes.  That is important
    on Windows because a 1920-pixel monitor at 125% scaling has a different
    logical workspace and font metrics from a laptop at 100% scaling.

    A hysteresis margin is applied while restoring text labels so resizing or
    moving the window between monitors does not make the toolbar oscillate.
    """

    available = max(0, int(available_width))
    usable = max(0, available - max(0, int(safety_margin)))
    expanded = max(1, int(expanded_width))
    compact = max(1, min(expanded, int(compact_width)))
    ultra = max(1, min(compact, int(ultra_compact_width)))
    restore = max(0, int(restore_margin))

    expanded_requirement = expanded + (restore if currently_compact else 0)
    if usable >= expanded_requirement:
        return ToolbarAdaptation(False, False, expanded, expanded <= usable)

    compact_requirement = compact + (restore // 2 if currently_ultra_compact else 0)
    if usable >= compact_requirement:
        return ToolbarAdaptation(True, False, compact, compact <= usable)

    return ToolbarAdaptation(True, True, ultra, ultra <= usable)


def overflow_item_count(
    available_width: int,
    required_width: int,
    removable_widths: Iterable[int],
    *,
    overflow_button_width: int = 40,
    safety_margin: int = 12,
) -> int:
    """Return how many low-priority items must move into an overflow menu.

    Widths are expressed in Qt logical pixels.  The first item in
    ``removable_widths`` has the lowest priority.  The overflow button is
    charged only when at least one item is removed.  Returning the full item
    count is intentional when even ultra-compact buttons do not fit: the
    pinned right-side command must remain visible.
    """

    available = max(0, int(available_width))
    usable = max(0, available - max(0, int(safety_margin)))
    required = max(0, int(required_width))
    widths = [max(0, int(value)) for value in removable_widths]
    if required <= usable:
        return 0
    deficit = required + max(0, int(overflow_button_width)) - usable
    removed = 0
    reclaimed = 0
    for width in widths:
        removed += 1
        reclaimed += width
        if reclaimed >= deficit:
            return removed
    return len(widths)
