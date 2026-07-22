from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class InputEventKind(StrEnum):
    """Platform-neutral input phases understood by tablet edit tools."""

    POINTER_PRESS = "pointer_press"
    POINTER_MOVE = "pointer_move"
    POINTER_RELEASE = "pointer_release"
    POINTER_DOUBLE_CLICK = "pointer_double_click"
    KEY_PRESS = "key_press"
    CANCEL = "cancel"


class PointerButton(StrEnum):
    NONE = "none"
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


@dataclass(frozen=True, slots=True)
class TabletInputEvent:
    """A small, testable event DTO detached from Qt widget ownership.

    ``x``/``y`` are expressed in the complete tablet canvas coordinate system,
    not in one individual track.  ``payload`` may carry the original Qt objects
    for an adapter callback, but interaction tools do not depend on them.
    """

    kind: InputEventKind
    x: float = 0.0
    y: float = 0.0
    track_id: str | None = None
    button: PointerButton = PointerButton.NONE
    pressed_buttons: frozenset[PointerButton] = field(default_factory=frozenset)
    key: str | None = None
    global_x: int = 0
    global_y: int = 0
    payload: object | None = None


@dataclass(frozen=True, slots=True)
class InteractionResponse:
    """Result returned by one interaction handler.

    ``recognized`` stops dispatch to lower-priority OOP handlers.  ``consume``
    tells the Qt adapter whether the original event must be accepted.  They are
    intentionally separate: selecting a track is a valid side effect but the
    same click may still continue to normal curve selection.
    """

    recognized: bool = False
    consume: bool = False
    capture: bool = False
    release_capture: bool = False
    cursor: str | None = None

    @classmethod
    def ignored(cls, *, cursor: str | None = None) -> InteractionResponse:
        return cls(cursor=cursor)

    @classmethod
    def pass_through(cls, *, cursor: str | None = None) -> InteractionResponse:
        return cls(recognized=True, consume=False, cursor=cursor)

    @classmethod
    def consumed(
        cls,
        *,
        capture: bool = False,
        release_capture: bool = False,
        cursor: str | None = None,
    ) -> InteractionResponse:
        return cls(
            recognized=True,
            consume=True,
            capture=capture,
            release_capture=release_capture,
            cursor=cursor,
        )


class TabletInteractionHandler(Protocol):
    """Interface implemented by every independent tablet editing tool."""

    @property
    def handler_id(self) -> str: ...

    def handle(self, event: TabletInputEvent) -> InteractionResponse: ...

    def cancel(self, reason: str) -> None: ...


class TabletInteractionRouter:
    """Priority router with explicit, self-healing pointer capture.

    Only the router owns capture state.  Rendering widgets never call
    ``grabMouse()`` and therefore cannot leave a transparent full-screen layer
    blocking the application.  A captured handler receives all subsequent move,
    release and cancellation events until it explicitly releases capture.
    """

    def __init__(self) -> None:
        self._handlers: list[TabletInteractionHandler] = []
        self._active_handler: TabletInteractionHandler | None = None

    @property
    def active_handler_id(self) -> str | None:
        return (
            self._active_handler.handler_id
            if self._active_handler is not None
            else None
        )

    @property
    def has_active_capture(self) -> bool:
        return self._active_handler is not None

    def register(self, handler: TabletInteractionHandler) -> None:
        if any(current.handler_id == handler.handler_id for current in self._handlers):
            raise ValueError(f"Interaction handler already registered: {handler.handler_id}")
        self._handlers.append(handler)

    def route(self, event: TabletInputEvent) -> InteractionResponse:
        active = self._active_handler
        if active is not None:
            response = active.handle(event)
            should_release = (
                response.release_capture
                or event.kind
                in {
                    InputEventKind.POINTER_RELEASE,
                    InputEventKind.CANCEL,
                }
            )
            if should_release:
                self._active_handler = None
            return response

        inherited_cursor: str | None = None
        for handler in self._handlers:
            response = handler.handle(event)
            if inherited_cursor is None and response.cursor is not None:
                inherited_cursor = response.cursor
            if not response.recognized:
                continue
            if response.capture:
                self._active_handler = handler
            if response.cursor is None and inherited_cursor is not None:
                response = InteractionResponse(
                    recognized=response.recognized,
                    consume=response.consume,
                    capture=response.capture,
                    release_capture=response.release_capture,
                    cursor=inherited_cursor,
                )
            return response
        return InteractionResponse.ignored(cursor=inherited_cursor)

    def cancel_active(self, reason: str = "cancelled") -> bool:
        active = self._active_handler
        if active is None:
            return False
        self._active_handler = None
        active.cancel(reason)
        return True

    def reset(self, reason: str = "reset") -> None:
        active = self._active_handler
        self._active_handler = None
        if active is not None:
            active.cancel(reason)
        for handler in self._handlers:
            if handler is active:
                continue
            handler.cancel(reason)
