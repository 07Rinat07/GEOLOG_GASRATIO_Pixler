from __future__ import annotations

from dataclasses import dataclass
from enum import IntFlag, auto


class DirtyReason(IntFlag):
    NONE = 0
    DATA = auto()
    STYLE = auto()
    LAYOUT = auto()
    STATIC = auto()
    VIEWPORT = auto()


@dataclass(frozen=True, slots=True)
class DirtyRenderStats:
    invalidations: int
    partial_updates: int
    full_updates: int
    pending_tracks: int


class TrackDirtyRegistry:
    """Track-level dirty state used to avoid rebuilding the complete tablet."""

    def __init__(self) -> None:
        self._dirty: dict[str, DirtyReason] = {}
        self._invalidations = 0
        self._partial_updates = 0
        self._full_updates = 0

    def mark(self, track_id: str, reason: DirtyReason) -> None:
        if not track_id or reason is DirtyReason.NONE:
            return
        self._dirty[track_id] = self._dirty.get(track_id, DirtyReason.NONE) | reason
        self._invalidations += 1

    def mark_many(self, track_ids: list[str] | tuple[str, ...], reason: DirtyReason) -> None:
        for track_id in track_ids:
            self.mark(track_id, reason)

    def consume(self) -> dict[str, DirtyReason]:
        dirty = dict(self._dirty)
        self._dirty.clear()
        return dirty

    def clear(self) -> None:
        self._dirty.clear()

    def record_partial_update(self, count: int = 1) -> None:
        self._partial_updates += max(0, int(count))

    def record_full_update(self) -> None:
        self._full_updates += 1
        self._dirty.clear()

    def stats(self) -> DirtyRenderStats:
        return DirtyRenderStats(
            invalidations=self._invalidations,
            partial_updates=self._partial_updates,
            full_updates=self._full_updates,
            pending_tracks=len(self._dirty),
        )
