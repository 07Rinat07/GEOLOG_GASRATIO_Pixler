from __future__ import annotations

from dataclasses import dataclass, field

from geoworkbench.tablet.interaction_router import (
    InputEventKind,
    InteractionResponse,
    PointerButton,
    TabletInputEvent,
    TabletInteractionRouter,
)


@dataclass
class FakeHandler:
    handler_id: str
    responses: list[InteractionResponse]
    events: list[InputEventKind] = field(default_factory=list)
    cancellations: list[str] = field(default_factory=list)

    def handle(self, event: TabletInputEvent) -> InteractionResponse:
        self.events.append(event.kind)
        return self.responses.pop(0) if self.responses else InteractionResponse.ignored()

    def cancel(self, reason: str) -> None:
        self.cancellations.append(reason)


def test_router_dispatches_in_priority_order() -> None:
    router = TabletInteractionRouter()
    first = FakeHandler("first", [InteractionResponse.ignored()])
    second = FakeHandler("second", [InteractionResponse.consumed()])
    router.register(first)
    router.register(second)

    response = router.route(
        TabletInputEvent(InputEventKind.POINTER_PRESS, button=PointerButton.LEFT)
    )

    assert response.consume is True
    assert first.events == [InputEventKind.POINTER_PRESS]
    assert second.events == [InputEventKind.POINTER_PRESS]


def test_capture_is_owned_by_router_and_released_on_pointer_release() -> None:
    router = TabletInteractionRouter()
    handler = FakeHandler(
        "drag",
        [
            InteractionResponse.consumed(capture=True),
            InteractionResponse.consumed(capture=True),
            InteractionResponse.consumed(release_capture=True),
        ],
    )
    fallback = FakeHandler("fallback", [InteractionResponse.consumed()])
    router.register(handler)
    router.register(fallback)

    router.route(TabletInputEvent(InputEventKind.POINTER_PRESS, button=PointerButton.LEFT))
    assert router.active_handler_id == "drag"
    router.route(
        TabletInputEvent(
            InputEventKind.POINTER_MOVE,
            pressed_buttons=frozenset({PointerButton.LEFT}),
        )
    )
    assert fallback.events == []
    router.route(TabletInputEvent(InputEventKind.POINTER_RELEASE, button=PointerButton.LEFT))

    assert router.has_active_capture is False
    assert handler.events == [
        InputEventKind.POINTER_PRESS,
        InputEventKind.POINTER_MOVE,
        InputEventKind.POINTER_RELEASE,
    ]


def test_cancel_active_never_leaves_stale_capture() -> None:
    router = TabletInteractionRouter()
    handler = FakeHandler("drag", [InteractionResponse.consumed(capture=True)])
    router.register(handler)
    router.route(TabletInputEvent(InputEventKind.POINTER_PRESS, button=PointerButton.LEFT))

    assert router.cancel_active("window_deactivated") is True
    assert router.has_active_capture is False
    assert handler.cancellations == ["window_deactivated"]


def test_track_selection_can_pass_through_to_legacy_curve_selection() -> None:
    router = TabletInteractionRouter()
    selector = FakeHandler("track", [InteractionResponse.pass_through()])
    router.register(selector)

    response = router.route(
        TabletInputEvent(
            InputEventKind.POINTER_PRESS,
            track_id="gas",
            button=PointerButton.LEFT,
        )
    )

    assert response.recognized is True
    assert response.consume is False
