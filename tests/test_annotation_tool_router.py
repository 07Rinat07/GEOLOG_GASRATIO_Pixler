from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.tablet.annotation_tool import (
    AnnotationGeometryChange,
    AnnotationInteractionHandler,
    AnnotationSurfaceHit,
)
from geoworkbench.tablet.interaction_router import (
    InputEventKind,
    PointerButton,
    TabletInputEvent,
)


@dataclass
class FakeSurface:
    hit: AnnotationSurfaceHit | None = None
    selected_annotation_id: str | None = None
    interaction_active: bool = False
    updates: int = 0
    cancelled: int = 0

    def hit_test(self, x: float, y: float) -> AnnotationSurfaceHit | None:
        del x, y
        return self.hit

    def hover_cursor(self, x: float, y: float) -> str | None:
        del x, y
        return "size_all" if self.hit is not None else None

    def select_annotation(self, annotation_id: str | None) -> None:
        self.selected_annotation_id = annotation_id

    def begin_interaction(
        self, hit: AnnotationSurfaceHit, x: float, y: float
    ) -> bool:
        del hit, x, y
        self.interaction_active = True
        return True

    def update_interaction(self, x: float, y: float) -> None:
        del x, y
        self.updates += 1

    def finish_interaction(self, *, commit: bool) -> AnnotationGeometryChange | None:
        self.interaction_active = False
        if not commit:
            return None
        return AnnotationGeometryChange("a1", 10.0, 20.0, 200.0, 80.0)

    def cancel_interaction(self) -> None:
        self.interaction_active = False
        self.cancelled += 1


def _handler(surface: FakeSurface, calls: dict[str, list[object]]) -> AnnotationInteractionHandler:
    return AnnotationInteractionHandler(
        surface,
        create_requested=lambda event, tool: calls["create"].append((event, tool)) or True,
        edit_requested=lambda annotation_id: calls["edit"].append(annotation_id),
        delete_requested=lambda annotation_id: calls["delete"].append(annotation_id),
        context_requested=lambda annotation_id, x, y: calls["context"].append(
            (annotation_id, x, y)
        ),
        geometry_changed=lambda change: calls["geometry"].append(change),
    )


def _calls() -> dict[str, list[object]]:
    return {name: [] for name in ("create", "edit", "delete", "context", "geometry")}


def test_existing_annotation_has_priority_over_active_creation_tool() -> None:
    surface = FakeSurface(hit=AnnotationSurfaceHit("a1"))
    calls = _calls()
    handler = _handler(surface, calls)
    handler.set_enabled(True)
    handler.set_creation_tool("comment")

    response = handler.handle(
        TabletInputEvent(
            InputEventKind.POINTER_PRESS,
            x=100,
            y=200,
            track_id="gas",
            button=PointerButton.LEFT,
        )
    )

    assert response.consume is True
    assert response.capture is True
    assert surface.selected_annotation_id == "a1"
    assert calls["create"] == []


def test_empty_plot_click_creates_annotation_only_when_tool_is_selected() -> None:
    surface = FakeSurface()
    calls = _calls()
    handler = _handler(surface, calls)
    handler.set_enabled(True)

    ignored = handler.handle(
        TabletInputEvent(
            InputEventKind.POINTER_PRESS,
            track_id="gas",
            button=PointerButton.LEFT,
        )
    )
    assert ignored.consume is False

    handler.set_creation_tool("callout")
    created = handler.handle(
        TabletInputEvent(
            InputEventKind.POINTER_PRESS,
            track_id="gas",
            button=PointerButton.LEFT,
        )
    )
    assert created.consume is True
    assert len(calls["create"]) == 1


def test_drag_emits_one_geometry_change_on_release() -> None:
    surface = FakeSurface(hit=AnnotationSurfaceHit("a1"))
    calls = _calls()
    handler = _handler(surface, calls)
    handler.set_enabled(True)
    handler.handle(
        TabletInputEvent(InputEventKind.POINTER_PRESS, button=PointerButton.LEFT)
    )

    handler.handle(
        TabletInputEvent(
            InputEventKind.POINTER_MOVE,
            pressed_buttons=frozenset({PointerButton.LEFT}),
        )
    )
    handler.handle(
        TabletInputEvent(InputEventKind.POINTER_RELEASE, button=PointerButton.LEFT)
    )

    assert surface.updates == 1
    assert len(calls["geometry"]) == 1
    assert calls["geometry"][0].annotation_id == "a1"


def test_double_click_and_right_click_are_independent_actions() -> None:
    surface = FakeSurface(hit=AnnotationSurfaceHit("a1"))
    calls = _calls()
    handler = _handler(surface, calls)
    handler.set_enabled(True)

    handler.handle(
        TabletInputEvent(
            InputEventKind.POINTER_DOUBLE_CLICK,
            button=PointerButton.LEFT,
        )
    )
    handler.handle(
        TabletInputEvent(
            InputEventKind.POINTER_PRESS,
            button=PointerButton.RIGHT,
            global_x=44,
            global_y=55,
        )
    )

    assert calls["edit"] == ["a1"]
    assert calls["context"] == [("a1", 44, 55)]


def test_double_click_after_second_press_cancels_drag_and_opens_editor() -> None:
    surface = FakeSurface(hit=AnnotationSurfaceHit("a1"))
    calls = _calls()
    handler = _handler(surface, calls)
    handler.set_enabled(True)
    handler.handle(
        TabletInputEvent(InputEventKind.POINTER_PRESS, button=PointerButton.LEFT)
    )
    assert surface.interaction_active is True

    response = handler.handle(
        TabletInputEvent(
            InputEventKind.POINTER_DOUBLE_CLICK,
            button=PointerButton.LEFT,
        )
    )

    assert response.release_capture is True
    assert surface.interaction_active is False
    assert calls["edit"] == ["a1"]
