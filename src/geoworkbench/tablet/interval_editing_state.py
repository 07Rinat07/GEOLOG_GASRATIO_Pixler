from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from geoworkbench.tablet.interval_interaction import IntervalEditMode, IntervalEdge


@dataclass(slots=True)
class IntervalGesture:
    """Qt-independent gesture state for interpretation interval editing."""

    track_id: str
    interpretation_id: str
    mode: IntervalEditMode
    lane: int
    interval_type: str
    start_depth: float
    current_depth: float
    interval_id: str | None = None
    edge: IntervalEdge | None = None
    original_top: float | None = None
    original_bottom: float | None = None


@dataclass(slots=True)
class IntervalEditingState:
    """Editing-session state owned outside TabletView.

    Rendering, cursor changes, signal emission and preview graphics remain Qt
    concerns. This state owns only the active edit mode, default interval type
    and in-progress interpretation gesture.
    """

    mode: IntervalEditMode = IntervalEditMode.SELECT
    creation_type: str = ""
    gesture: IntervalGesture | None = None

    def set_mode(self, mode: IntervalEditMode | str) -> bool:
        requested = mode if isinstance(mode, IntervalEditMode) else IntervalEditMode(mode)
        if requested is self.mode:
            return False
        self.mode = requested
        return True

    def set_creation_type(self, interval_type: str) -> bool:
        normalized = interval_type.strip()
        if not normalized or normalized == self.creation_type:
            return False
        self.creation_type = normalized
        return True

    def begin_gesture(self, gesture: IntervalGesture) -> None:
        if gesture.mode is IntervalEditMode.SELECT:
            raise ValueError("SELECT mode cannot own an interval editing gesture")
        if not gesture.track_id.strip() or not gesture.interpretation_id.strip():
            raise ValueError("Interval gesture identifiers must be non-empty")
        if gesture.lane < 0:
            raise ValueError("Interval gesture lane must be non-negative")
        if not isfinite(gesture.start_depth) or not isfinite(gesture.current_depth):
            raise ValueError("Interval gesture depths must be finite")
        self.gesture = gesture

    def update_current_depth(self, depth: float) -> bool:
        if self.gesture is None:
            return False
        value = float(depth)
        if not isfinite(value):
            raise ValueError("Interval gesture depth must be finite")
        self.gesture.current_depth = value
        return True

    def cancel_gesture(self) -> IntervalGesture | None:
        gesture = self.gesture
        self.gesture = None
        return gesture


__all__ = [
    "IntervalEditingState",
    "IntervalGesture",
]
