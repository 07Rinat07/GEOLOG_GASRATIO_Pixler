from geoworkbench.tablet.interaction_router import (
    InputEventKind,
    PointerButton,
    TabletInputEvent,
)
from geoworkbench.tablet.track_edit_tool import TrackEditInteractionHandler


def test_track_click_selects_column_without_consuming_curve_click() -> None:
    selected: list[str] = []
    edited: list[str] = []
    handler = TrackEditInteractionHandler(
        select_track=selected.append,
        edit_track=edited.append,
    )
    handler.set_enabled(True)

    response = handler.handle(
        TabletInputEvent(
            InputEventKind.POINTER_PRESS,
            track_id="gas",
            button=PointerButton.LEFT,
        )
    )

    assert selected == ["gas"]
    assert edited == []
    assert response.recognized is True
    assert response.consume is False


def test_double_click_opens_track_editor() -> None:
    selected: list[str] = []
    edited: list[str] = []
    handler = TrackEditInteractionHandler(
        select_track=selected.append,
        edit_track=edited.append,
        can_edit_track=lambda track_id: track_id == "gas",
    )
    handler.set_enabled(True)

    response = handler.handle(
        TabletInputEvent(
            InputEventKind.POINTER_DOUBLE_CLICK,
            track_id="gas",
            button=PointerButton.LEFT,
        )
    )

    assert selected == ["gas"]
    assert edited == ["gas"]
    assert response.consume is True


def test_annotation_creation_suspends_track_editor_only_temporarily() -> None:
    selected: list[str] = []
    handler = TrackEditInteractionHandler(
        select_track=selected.append,
        edit_track=lambda _track_id: None,
    )
    handler.set_enabled(True)
    handler.set_suspended(True)

    ignored = handler.handle(
        TabletInputEvent(
            InputEventKind.POINTER_PRESS,
            track_id="gas",
            button=PointerButton.LEFT,
        )
    )
    assert ignored.recognized is False
    assert selected == []

    handler.set_suspended(False)
    handler.handle(
        TabletInputEvent(
            InputEventKind.POINTER_PRESS,
            track_id="gas",
            button=PointerButton.LEFT,
        )
    )
    assert selected == ["gas"]
