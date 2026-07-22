from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.tablet.annotation_tool import (
    AnnotationGeometryChange,
    AnnotationInteractionHandler,
    AnnotationSurfaceHit,
)
from geoworkbench.tablet.edit_mode_coordinator import TabletEditModeCoordinator
from geoworkbench.tablet.interaction_router import (
    InputEventKind,
    PointerButton,
    TabletInputEvent,
    TabletInteractionRouter,
)
from geoworkbench.tablet.track_edit_tool import TrackEditInteractionHandler


@dataclass
class Surface:
    hit: AnnotationSurfaceHit | None = None
    selected_annotation_id: str | None = None
    interaction_active: bool = False

    def hit_test(self, x: float, y: float) -> AnnotationSurfaceHit | None:
        del x, y
        return self.hit

    def hover_cursor(self, x: float, y: float) -> str | None:
        del x, y
        return "size_all" if self.hit is not None else None

    def select_annotation(self, annotation_id: str | None) -> None:
        self.selected_annotation_id = annotation_id

    def begin_interaction(self, hit: AnnotationSurfaceHit, x: float, y: float) -> bool:
        del hit, x, y
        self.interaction_active = True
        return True

    def update_interaction(self, x: float, y: float) -> None:
        del x, y

    def finish_interaction(self, *, commit: bool) -> AnnotationGeometryChange | None:
        self.interaction_active = False
        return None

    def cancel_interaction(self) -> None:
        self.interaction_active = False


def _pipeline(surface: Surface):
    created: list[str] = []
    selected_tracks: list[str] = []
    edited_tracks: list[str] = []
    annotation = AnnotationInteractionHandler(
        surface,
        create_requested=lambda event, tool: created.append(f"{event.track_id}:{tool}") or True,
        edit_requested=lambda _annotation_id: None,
        delete_requested=lambda _annotation_id: None,
        context_requested=lambda _annotation_id, _x, _y: None,
        geometry_changed=lambda _change: None,
    )
    track = TrackEditInteractionHandler(
        select_track=selected_tracks.append,
        edit_track=edited_tracks.append,
    )
    modes = TabletEditModeCoordinator(annotation, track)
    router = TabletInteractionRouter()
    router.register(annotation)
    router.register(track)
    return router, modes, created, selected_tracks, edited_tracks


def test_empty_click_in_f4_selects_track_and_remains_available_to_curve_logic() -> None:
    router, modes, created, selected, _edited = _pipeline(Surface())
    modes.set_form_edit_enabled(True)

    response = router.route(
        TabletInputEvent(
            InputEventKind.POINTER_PRESS,
            track_id="technology",
            button=PointerButton.LEFT,
        )
    )

    assert created == []
    assert selected == ["technology"]
    assert response.consume is False


def test_armed_annotation_tool_creates_on_track_without_leaking_to_track_editor() -> None:
    router, modes, created, selected, _edited = _pipeline(Surface())
    modes.set_form_edit_enabled(True)
    modes.set_annotation_tool("comment")

    response = router.route(
        TabletInputEvent(
            InputEventKind.POINTER_PRESS,
            track_id="technology",
            button=PointerButton.LEFT,
        )
    )

    assert created == ["technology:comment"]
    assert selected == []
    assert response.consume is True


def test_existing_annotation_keeps_priority_even_when_creation_tool_is_armed() -> None:
    surface = Surface(hit=AnnotationSurfaceHit("annotation-1"))
    router, modes, created, selected, _edited = _pipeline(surface)
    modes.set_form_edit_enabled(True)
    modes.set_annotation_tool("callout")

    response = router.route(
        TabletInputEvent(
            InputEventKind.POINTER_PRESS,
            track_id="technology",
            button=PointerButton.LEFT,
        )
    )

    assert created == []
    assert selected == []
    assert surface.selected_annotation_id == "annotation-1"
    assert response.capture is True


def test_after_disarming_tool_track_editor_is_restored_without_rebuilding_router() -> None:
    router, modes, _created, selected, edited = _pipeline(Surface())
    modes.set_form_edit_enabled(True)
    modes.set_annotation_tool("comment")
    modes.cancel_annotation_tool()

    response = router.route(
        TabletInputEvent(
            InputEventKind.POINTER_DOUBLE_CLICK,
            track_id="gas",
            button=PointerButton.LEFT,
        )
    )

    assert selected == ["gas"]
    assert edited == ["gas"]
    assert response.consume is True
