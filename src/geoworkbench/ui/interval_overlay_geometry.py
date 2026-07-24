from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OverlayRect:
    """Toolkit-independent rectangle used for floating statistics geometry."""

    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height


def calculate_interval_statistics_overlay_geometry(
    *,
    main_window: OverlayRect,
    available_screen: OverlayRect,
    preferred_width: int = 380,
    preferred_height: int = 680,
    minimum_width: int = 320,
    minimum_height: int = 300,
    screen_margin: int = 10,
    main_top_offset: int = 94,
    main_right_inset: int = 16,
) -> OverlayRect:
    """Return a screen-safe overlay rectangle anchored over the tablet's right edge.

    The function deliberately does not depend on Qt, which makes the placement
    contract testable in a headless environment.  The overlay may cover the
    tablet, but it never increases the main-window minimum width and never
    leaves the active monitor work area.
    """

    screen_width = max(1, available_screen.width)
    screen_height = max(1, available_screen.height)
    margin = max(
        0,
        min(
            int(screen_margin),
            max(0, (screen_width - 1) // 2),
            max(0, (screen_height - 1) // 2),
        ),
    )
    safe_x = available_screen.x + margin
    safe_y = available_screen.y + margin
    safe_width = max(1, screen_width - margin * 2)
    safe_height = max(1, screen_height - margin * 2)

    requested_width = max(int(minimum_width), int(preferred_width))
    requested_height = max(int(minimum_height), int(preferred_height))
    width = min(requested_width, safe_width)
    height = min(requested_height, safe_height)

    target_x = main_window.x + main_window.width - width - int(main_right_inset)
    target_y = main_window.y + int(main_top_offset)
    max_x = safe_x + safe_width - width
    max_y = safe_y + safe_height - height
    x = min(max(target_x, safe_x), max_x)
    y = min(max(target_y, safe_y), max_y)
    return OverlayRect(x=x, y=y, width=width, height=height)
