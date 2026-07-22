from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from geoworkbench.tablet.interaction_router import (
    InputEventKind,
    InteractionResponse,
    PointerButton,
    TabletInputEvent,
)


@dataclass(frozen=True, slots=True)
class AnnotationSurfaceHit:
    annotation_id: str
    locked: bool = False
    resize_handle: str | None = None
    movable: bool = True


@dataclass(frozen=True, slots=True)
class AnnotationGeometryChange:
    annotation_id: str
    offset_x: float
    offset_y: float
    width: float
    height: float


class AnnotationInteractionSurface(Protocol):
    """Rendering-agnostic port used by the annotation editing tool."""

    @property
    def interaction_active(self) -> bool: ...

    @property
    def selected_annotation_id(self) -> str | None: ...

    def hit_test(self, x: float, y: float) -> AnnotationSurfaceHit | None: ...

    def hover_cursor(self, x: float, y: float) -> str | None: ...

    def select_annotation(self, annotation_id: str | None) -> None: ...

    def begin_interaction(
        self,
        hit: AnnotationSurfaceHit,
        x: float,
        y: float,
    ) -> bool: ...

    def update_interaction(self, x: float, y: float) -> None: ...

    def finish_interaction(self, *, commit: bool) -> AnnotationGeometryChange | None: ...

    def cancel_interaction(self) -> None: ...


CreateCallback = Callable[[TabletInputEvent, object], bool]
IdCallback = Callable[[str], None]
ContextCallback = Callable[[str, int, int], None]
GeometryCallback = Callable[[AnnotationGeometryChange], None]
SelectionCallback = Callable[[str | None], None]
ToolCancelledCallback = Callable[[], None]


class AnnotationInteractionHandler:
    """Selection, creation, move, resize and editing of annotations.

    This class owns the complete annotation gesture state.  The overlay is only
    a paint/hit-test surface and cannot intercept unrelated track events.
    """

    handler_id = "annotation"

    def __init__(
        self,
        surface: AnnotationInteractionSurface,
        *,
        create_requested: CreateCallback,
        edit_requested: IdCallback,
        delete_requested: IdCallback,
        context_requested: ContextCallback,
        geometry_changed: GeometryCallback,
        selection_changed: SelectionCallback | None = None,
        creation_tool_cancelled: ToolCancelledCallback | None = None,
    ) -> None:
        self._surface = surface
        self._create_requested = create_requested
        self._edit_requested = edit_requested
        self._delete_requested = delete_requested
        self._context_requested = context_requested
        self._geometry_changed = geometry_changed
        self._selection_changed = selection_changed
        self._creation_tool_cancelled = creation_tool_cancelled
        self._enabled = False
        self._creation_tool: object | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def creation_tool(self) -> object | None:
        return self._creation_tool

    def set_enabled(self, enabled: bool) -> None:
        normalized = bool(enabled)
        if normalized == self._enabled:
            return
        self._enabled = normalized
        if not normalized:
            self.cancel("edit_mode_disabled")
            self._set_selection(None)

    def set_creation_tool(self, tool: object | None) -> None:
        self._creation_tool = tool

    def handle(self, event: TabletInputEvent) -> InteractionResponse:
        if not self._enabled:
            return InteractionResponse.ignored()

        if event.kind is InputEventKind.CANCEL:
            self.cancel("cancel_event")
            return InteractionResponse.consumed(release_capture=True)

        if self._surface.interaction_active:
            return self._handle_active_gesture(event)

        if event.kind is InputEventKind.KEY_PRESS:
            return self._handle_key(event)

        hit = self._surface.hit_test(event.x, event.y)
        cursor = self._surface.hover_cursor(event.x, event.y)

        if event.kind is InputEventKind.POINTER_MOVE:
            return InteractionResponse.ignored(cursor=cursor)

        if event.kind is InputEventKind.POINTER_DOUBLE_CLICK:
            if event.button is PointerButton.LEFT and hit is not None:
                self._set_selection(hit.annotation_id)
                self._edit_requested(hit.annotation_id)
                return InteractionResponse.consumed(cursor=cursor)
            return InteractionResponse.ignored(cursor=cursor)

        if event.kind is not InputEventKind.POINTER_PRESS:
            return InteractionResponse.ignored(cursor=cursor)

        if event.button is PointerButton.RIGHT:
            if hit is None:
                return InteractionResponse.ignored(cursor=cursor)
            self._set_selection(hit.annotation_id)
            self._context_requested(
                hit.annotation_id,
                int(event.global_x),
                int(event.global_y),
            )
            return InteractionResponse.consumed(cursor=cursor)

        if event.button is not PointerButton.LEFT:
            return InteractionResponse.ignored(cursor=cursor)

        if hit is not None:
            self._set_selection(hit.annotation_id)
            if hit.locked or not hit.movable:
                return InteractionResponse.consumed(cursor=cursor)
            if self._surface.begin_interaction(hit, event.x, event.y):
                return InteractionResponse.consumed(capture=True, cursor=cursor)
            return InteractionResponse.consumed(cursor=cursor)

        if self._creation_tool is not None and event.track_id is not None:
            created = self._create_requested(event, self._creation_tool)
            if created:
                return InteractionResponse.consumed(cursor="cross")

        # Empty space belongs to the track/curve editor. Clear annotation
        # selection but deliberately pass the click through.
        self._set_selection(None)
        return InteractionResponse.ignored(cursor=cursor)

    def cancel(self, reason: str) -> None:
        del reason
        self._surface.cancel_interaction()

    def _handle_active_gesture(self, event: TabletInputEvent) -> InteractionResponse:
        if event.kind is InputEventKind.POINTER_DOUBLE_CLICK:
            selected = self._surface.selected_annotation_id
            self._surface.finish_interaction(commit=False)
            if selected is not None:
                self._edit_requested(selected)
            return InteractionResponse.consumed(release_capture=True)

        if event.kind is InputEventKind.POINTER_MOVE:
            if PointerButton.LEFT not in event.pressed_buttons:
                change = self._surface.finish_interaction(commit=True)
                self._emit_geometry(change)
                return InteractionResponse.consumed(release_capture=True)
            self._surface.update_interaction(event.x, event.y)
            return InteractionResponse.consumed(capture=True)

        if event.kind is InputEventKind.POINTER_RELEASE:
            change = self._surface.finish_interaction(commit=True)
            self._emit_geometry(change)
            return InteractionResponse.consumed(release_capture=True)

        if event.kind is InputEventKind.KEY_PRESS and event.key == "escape":
            self._surface.finish_interaction(commit=False)
            return InteractionResponse.consumed(release_capture=True)

        if event.kind is InputEventKind.CANCEL:
            self._surface.finish_interaction(commit=True)
            return InteractionResponse.consumed(release_capture=True)

        return InteractionResponse.consumed(capture=True)

    def _handle_key(self, event: TabletInputEvent) -> InteractionResponse:
        selected = self._surface.selected_annotation_id
        if event.key == "escape":
            if self._creation_tool is not None:
                if self._creation_tool_cancelled is not None:
                    self._creation_tool_cancelled()
                else:
                    self._creation_tool = None
                return InteractionResponse.consumed()
            if selected is not None:
                self._set_selection(None)
                return InteractionResponse.consumed()
            return InteractionResponse.ignored()
        if selected is None:
            return InteractionResponse.ignored()
        if event.key in {"enter", "return", "f2"}:
            self._edit_requested(selected)
            return InteractionResponse.consumed()
        if event.key in {"delete", "backspace"}:
            self._delete_requested(selected)
            return InteractionResponse.consumed()
        return InteractionResponse.ignored()

    def _set_selection(self, annotation_id: str | None) -> None:
        before = self._surface.selected_annotation_id
        self._surface.select_annotation(annotation_id)
        after = self._surface.selected_annotation_id
        if self._selection_changed is not None and before != after:
            self._selection_changed(after)

    def _emit_geometry(self, change: AnnotationGeometryChange | None) -> None:
        if change is not None:
            self._geometry_changed(change)
