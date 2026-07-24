from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OverlayGeometry:
    """Integer geometry for an overlay constrained to its parent widget."""

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


def constrain_overlay_geometry(
    *,
    parent_width: int,
    parent_height: int,
    requested_x: int,
    requested_y: int,
    requested_width: int,
    requested_height: int,
    margin: int = 8,
    minimum_width: int = 260,
    minimum_height: int = 220,
) -> OverlayGeometry:
    """Clamp an overlay fully inside its parent rectangle.

    The function deliberately works with plain integers so the geometry policy
    can be exhaustively tested without Qt or a display server.
    """

    parent_width = max(1, int(parent_width))
    parent_height = max(1, int(parent_height))
    margin = max(0, int(margin))

    available_width = max(1, parent_width - margin * 2)
    available_height = max(1, parent_height - margin * 2)

    lower_width = min(max(1, int(minimum_width)), available_width)
    lower_height = min(max(1, int(minimum_height)), available_height)
    width = min(available_width, max(lower_width, int(requested_width)))
    height = min(available_height, max(lower_height, int(requested_height)))

    maximum_x = max(margin, parent_width - margin - width)
    maximum_y = max(margin, parent_height - margin - height)
    x = min(max(margin, int(requested_x)), maximum_x)
    y = min(max(margin, int(requested_y)), maximum_y)
    return OverlayGeometry(x=x, y=y, width=width, height=height)


def right_anchored_overlay_geometry(
    *,
    parent_width: int,
    parent_height: int,
    preferred_width: int = 370,
    preferred_height: int = 720,
    margin: int = 8,
    top_offset: int = 8,
    minimum_width: int = 260,
    minimum_height: int = 220,
) -> OverlayGeometry:
    """Return a screen-independent right-anchored child-overlay geometry."""

    return constrain_overlay_geometry(
        parent_width=parent_width,
        parent_height=parent_height,
        requested_x=int(parent_width) - int(margin) - int(preferred_width),
        requested_y=max(int(margin), int(top_offset)),
        requested_width=preferred_width,
        requested_height=preferred_height,
        margin=margin,
        minimum_width=minimum_width,
        minimum_height=minimum_height,
    )
