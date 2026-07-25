from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolbarAdaptation:
    """Responsive state for a horizontal application toolbar."""

    compact: bool
    ultra_compact: bool


def choose_toolbar_adaptation(
    available_width: int,
    expanded_width: int,
    *,
    currently_compact: bool = False,
    restore_margin: int = 96,
    ultra_compact_width: int = 1040,
) -> ToolbarAdaptation:
    """Choose a stable toolbar mode without resize-threshold oscillation.

    ``expanded_width`` is the natural width of the toolbar with text labels.
    Once compact mode is active, a small margin is required before restoring
    labels.  This prevents continuous switching when the window is resized near
    the threshold.
    """

    available = max(0, int(available_width))
    required = max(1, int(expanded_width))
    margin = max(0, int(restore_margin))
    if currently_compact:
        compact = available < required + margin
    else:
        compact = available < required
    return ToolbarAdaptation(
        compact=compact,
        ultra_compact=available < max(320, int(ultra_compact_width)),
    )
