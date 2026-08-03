from __future__ import annotations

from collections.abc import Iterable

from geoworkbench.domain.models import IndexRole, IndexType
from geoworkbench.tablet.models import TrackDefinition, TrackKind


DATETIME_AXIS_MIN_TRACK_WIDTH = 156
RELATIVE_TIME_AXIS_MIN_TRACK_WIDTH = 124
DEFAULT_TRACK_SPACING = 2


def effective_track_width(
    definition: TrackDefinition,
    *,
    axis_role: IndexRole | None = None,
    axis_type: IndexType | None = None,
) -> int:
    """Return the real on-screen width used by one tablet track.

    Calendar and relative-time labels need more room than the persisted compact
    depth-column width. Keeping this rule in one pure helper prevents the Qt
    widget, scroll canvas and merged group headers from using different widths.
    """

    width = max(1, int(definition.width))
    if definition.kind is not TrackKind.DEPTH:
        return width
    if axis_type is IndexType.DATETIME:
        return max(width, DATETIME_AXIS_MIN_TRACK_WIDTH)
    if axis_role is IndexRole.TIME:
        return max(width, RELATIVE_TIME_AXIS_MIN_TRACK_WIDTH)
    return width


def horizontal_track_extent(
    widths: Iterable[int], *, spacing: int = DEFAULT_TRACK_SPACING
) -> int:
    """Return the exact width of a horizontal row of fixed-width tracks."""

    normalized = [max(1, int(width)) for width in widths]
    if not normalized:
        return 0
    gap = max(0, int(spacing))
    return sum(normalized) + gap * (len(normalized) - 1)
