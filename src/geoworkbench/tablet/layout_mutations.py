from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.tablet.models import TabletLayout, TrackDefinition


@dataclass(slots=True)
class TabletLayoutMutationController:
    """Own low-level mutations of one tablet layout outside Qt widgets.

    ``TabletView`` keeps rendering and gesture state, but every change to the
    serializable :class:`TabletLayout` is committed through this headless
    boundary.  The application normally handles user requests through
    :class:`~geoworkbench.tablet.controller.TabletController`; this controller
    is also used as a deterministic fallback by standalone view tests and for
    non-user normalization during rendering.
    """

    layout: TabletLayout

    def bind(self, layout: TabletLayout) -> None:
        if not isinstance(layout, TabletLayout):
            raise TypeError("Ожидалась модель планшета")
        self.layout = layout

    def set_track_width(self, track_id: str, width: int) -> bool:
        track = self.layout.track_by_id(track_id)
        normalized = int(width)
        if track.width == normalized:
            return False
        self.layout.set_track_width(track_id, normalized)
        return True

    def move_track_to_index(self, track_id: str, target_index: int) -> bool:
        track = self.layout.track_by_id(track_id)
        current_index = self.layout.tracks.index(track)
        bounded = max(0, min(int(target_index), len(self.layout.tracks) - 1))
        if current_index == bounded:
            return False
        self.layout.move_track(track_id, bounded)
        return True

    def add_track(self, definition: TrackDefinition, index: int | None = None) -> None:
        self.layout.add_track(definition, index)

    def remove_track(self, track_id: str) -> TrackDefinition:
        return self.layout.remove_track(track_id)

    def set_visible_depth(self, top: float | None, bottom: float | None) -> bool:
        return self.layout.set_visible_depth(top, bottom)

    def set_vertical_index(self, index_id: str | None) -> bool:
        return self.layout.set_vertical_index(index_id)
