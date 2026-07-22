from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class AnnotationModePort(Protocol):
    """Minimal annotation-tool interface required by the mode coordinator."""

    def set_enabled(self, enabled: bool) -> None: ...

    def set_creation_tool(self, tool: object | None) -> None: ...


class TrackEditModePort(Protocol):
    """Minimal track-edit interface required by the mode coordinator."""

    def set_enabled(self, enabled: bool) -> None: ...

    def set_suspended(self, suspended: bool) -> None: ...


@dataclass(frozen=True, slots=True)
class TabletEditModeState:
    """Immutable snapshot of the complete F4 interaction mode."""

    form_edit_enabled: bool
    annotation_tool: object | None
    track_edit_enabled: bool
    track_edit_suspended: bool


class TabletEditModeCoordinator:
    """Single owner of F4 mode invariants.

    The old implementation distributed edit flags among the tablet, the
    transparent overlay and individual track widgets.  One missed reset could
    therefore disable both annotation and track editing.  This coordinator is
    the only class allowed to arm an annotation creation tool or suspend direct
    track editing.

    Invariants:
    * both handlers are enabled together while F4 is active;
    * track editing is suspended only while a creation tool is armed;
    * disabling F4 always disarms the tool and restores track editing state.
    """

    def __init__(
        self,
        annotation_mode: AnnotationModePort,
        track_edit_mode: TrackEditModePort,
    ) -> None:
        self._annotation_mode = annotation_mode
        self._track_edit_mode = track_edit_mode
        self._form_edit_enabled = False
        self._annotation_tool: object | None = None
        self._apply()

    @property
    def state(self) -> TabletEditModeState:
        suspended = self._form_edit_enabled and self._annotation_tool is not None
        return TabletEditModeState(
            form_edit_enabled=self._form_edit_enabled,
            annotation_tool=self._annotation_tool,
            track_edit_enabled=self._form_edit_enabled,
            track_edit_suspended=suspended,
        )

    def set_form_edit_enabled(self, enabled: bool) -> TabletEditModeState:
        self._form_edit_enabled = bool(enabled)
        if not self._form_edit_enabled:
            self._annotation_tool = None
        self._apply()
        return self.state

    def set_annotation_tool(self, tool: object | None) -> TabletEditModeState:
        self._annotation_tool = tool if self._form_edit_enabled else None
        self._apply()
        return self.state

    def cancel_annotation_tool(self) -> TabletEditModeState:
        return self.set_annotation_tool(None)

    def _apply(self) -> None:
        enabled = self._form_edit_enabled
        tool = self._annotation_tool if enabled else None
        self._annotation_mode.set_enabled(enabled)
        self._annotation_mode.set_creation_tool(tool)
        self._track_edit_mode.set_enabled(enabled)
        self._track_edit_mode.set_suspended(enabled and tool is not None)
