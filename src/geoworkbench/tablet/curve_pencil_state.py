from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class CurvePencilMode(StrEnum):
    """How the user defines a replacement segment for the selected curve."""

    FREEHAND = "freehand"
    CONNECT_POINTS = "connect_points"


@dataclass(frozen=True, slots=True)
class CurvePencilPoint:
    """Renderer-neutral point collected by the curve-pencil gesture."""

    axis_value: float
    source_value: float
    display_x: float


@dataclass(slots=True)
class CurvePencilState:
    """Qt-independent mutable state for one curve-pencil editing session.

    The widget still owns presentation concerns such as cursors, hover labels and
    preview graphics. This component owns only editing state that must survive UI
    redraws and has deterministic transitions suitable for unit tests.
    """

    enabled: bool = False
    track_id: str | None = None
    mnemonic: str | None = None
    curve_id: str | None = None
    points: list[CurvePencilPoint] = field(default_factory=list)
    mode: CurvePencilMode = CurvePencilMode.FREEHAND
    commit_ack: bool | None = None
    commit_error: str = ""
    unsaved: bool = False
    can_undo: bool = False
    can_redo: bool = False

    @property
    def target(self) -> tuple[str, str] | None:
        if self.track_id is None or self.mnemonic is None:
            return None
        return self.track_id, self.mnemonic

    def select_target(self, track_id: str, mnemonic: str, curve_id: str) -> None:
        normalized_track = track_id.strip()
        normalized_mnemonic = mnemonic.strip()
        normalized_curve = curve_id.strip()
        if not normalized_track or not normalized_mnemonic or not normalized_curve:
            raise ValueError("Curve-pencil target identifiers must be non-empty")
        self.track_id = normalized_track
        self.mnemonic = normalized_mnemonic
        self.curve_id = normalized_curve

    def clear_target(self) -> None:
        self.track_id = None
        self.mnemonic = None
        self.curve_id = None

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        if not self.enabled:
            self.points.clear()
            self.commit_ack = None
            self.commit_error = ""
            self.clear_target()

    def set_mode(self, mode: CurvePencilMode) -> None:
        if not isinstance(mode, CurvePencilMode):
            raise TypeError("mode must be CurvePencilMode")
        if mode is self.mode:
            return
        self.mode = mode
        self.cancel_gesture()

    def cancel_gesture(self) -> None:
        self.points.clear()
        self.commit_ack = None
        self.commit_error = ""

    def acknowledge_commit(self, accepted: bool, error: str = "") -> None:
        self.commit_ack = bool(accepted)
        self.commit_error = error.strip()

    def set_history(self, *, can_undo: bool, can_redo: bool) -> None:
        self.can_undo = bool(can_undo)
        self.can_redo = bool(can_redo)

    def mark_unsaved(self) -> None:
        self.unsaved = True

    def clear_unsaved(self) -> None:
        self.unsaved = False


__all__ = [
    "CurvePencilMode",
    "CurvePencilPoint",
    "CurvePencilState",
]
