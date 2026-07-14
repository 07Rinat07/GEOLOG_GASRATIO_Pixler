from __future__ import annotations

from dataclasses import dataclass


MIN_TRACK_WIDTH = 80
MAX_TRACK_WIDTH = 2000


@dataclass(frozen=True, slots=True)
class TrackResizeGesture:
    initial_width: int
    initial_global_x: int
    minimum_width: int = MIN_TRACK_WIDTH
    maximum_width: int = MAX_TRACK_WIDTH

    def width_at(self, global_x: int) -> int:
        requested = self.initial_width + global_x - self.initial_global_x
        return max(self.minimum_width, min(requested, self.maximum_width))
