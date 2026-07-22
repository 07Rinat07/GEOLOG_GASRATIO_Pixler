from __future__ import annotations

from typing import Callable

from geoworkbench.tablet.interaction_router import (
    InputEventKind,
    InteractionResponse,
    PointerButton,
    TabletInputEvent,
)


TrackCallback = Callable[[str], None]


class TrackEditInteractionHandler:
    """Column selection and direct opening of the selected track editor."""

    handler_id = "track_edit"

    def __init__(
        self,
        *,
        select_track: TrackCallback,
        edit_track: TrackCallback,
        can_edit_track: Callable[[str], bool] | None = None,
    ) -> None:
        self._select_track = select_track
        self._edit_track = edit_track
        self._can_edit_track = can_edit_track or (lambda _track_id: True)
        self._enabled = False
        self._suspended = False

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)

    def set_suspended(self, suspended: bool) -> None:
        self._suspended = bool(suspended)

    def handle(self, event: TabletInputEvent) -> InteractionResponse:
        if not self._enabled or self._suspended or event.track_id is None:
            return InteractionResponse.ignored()

        if (
            event.kind is InputEventKind.POINTER_PRESS
            and event.button is PointerButton.LEFT
        ):
            self._select_track(event.track_id)
            # Curve selection and point-value inspection may still use the same
            # click, so track selection is deliberately non-consuming.
            return InteractionResponse.pass_through()

        if (
            event.kind is InputEventKind.POINTER_DOUBLE_CLICK
            and event.button is PointerButton.LEFT
            and self._can_edit_track(event.track_id)
        ):
            self._select_track(event.track_id)
            self._edit_track(event.track_id)
            return InteractionResponse.consumed()

        return InteractionResponse.ignored()

    def cancel(self, reason: str) -> None:
        del reason
