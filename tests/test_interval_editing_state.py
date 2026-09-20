from __future__ import annotations

import math

import pytest

from geoworkbench.tablet.interval_editing_state import (
    IntervalEditingState,
    IntervalGesture,
)
from geoworkbench.tablet.interval_interaction import IntervalEditMode


def _gesture(mode: IntervalEditMode = IntervalEditMode.CREATE) -> IntervalGesture:
    return IntervalGesture(
        track_id="interpretation-track",
        interpretation_id="interpretation-1",
        mode=mode,
        lane=1,
        interval_type="Reservoir",
        start_depth=1000.0,
        current_depth=1000.0,
        interval_id="interval-1" if mode is IntervalEditMode.RESIZE else None,
        edge="bottom" if mode is IntervalEditMode.RESIZE else None,
    )


def test_interval_editing_state_tracks_mode_and_creation_type() -> None:
    state = IntervalEditingState(creation_type="Default")

    assert state.set_mode(IntervalEditMode.CREATE)
    assert state.mode is IntervalEditMode.CREATE
    assert not state.set_mode("create")

    assert state.set_creation_type("  Reservoir  ")
    assert state.creation_type == "Reservoir"
    assert not state.set_creation_type("Reservoir")
    assert not state.set_creation_type("   ")


def test_interval_editing_state_owns_gesture_lifecycle() -> None:
    state = IntervalEditingState(mode=IntervalEditMode.CREATE)
    gesture = _gesture()

    state.begin_gesture(gesture)
    assert state.gesture is gesture

    assert state.update_current_depth(1012.5)
    assert gesture.current_depth == pytest.approx(1012.5)

    cancelled = state.cancel_gesture()
    assert cancelled is gesture
    assert state.gesture is None
    assert not state.update_current_depth(1015.0)


def test_interval_editing_state_supports_resize_gesture() -> None:
    state = IntervalEditingState(mode=IntervalEditMode.RESIZE)
    gesture = _gesture(IntervalEditMode.RESIZE)

    state.begin_gesture(gesture)

    assert state.gesture is not None
    assert state.gesture.interval_id == "interval-1"
    assert state.gesture.edge == "bottom"


@pytest.mark.parametrize(
    "gesture, message",
    [
        (_gesture(IntervalEditMode.SELECT), "SELECT"),
        (
            IntervalGesture(
                track_id="",
                interpretation_id="interpretation-1",
                mode=IntervalEditMode.CREATE,
                lane=0,
                interval_type="Reservoir",
                start_depth=1000.0,
                current_depth=1000.0,
            ),
            "identifiers",
        ),
        (
            IntervalGesture(
                track_id="track-1",
                interpretation_id="interpretation-1",
                mode=IntervalEditMode.CREATE,
                lane=-1,
                interval_type="Reservoir",
                start_depth=1000.0,
                current_depth=1000.0,
            ),
            "lane",
        ),
    ],
)
def test_interval_editing_state_rejects_invalid_gesture(
    gesture: IntervalGesture, message: str
) -> None:
    state = IntervalEditingState()

    with pytest.raises(ValueError, match=message):
        state.begin_gesture(gesture)


def test_interval_editing_state_rejects_non_finite_depth_updates() -> None:
    state = IntervalEditingState()
    state.begin_gesture(_gesture())

    with pytest.raises(ValueError, match="finite"):
        state.update_current_depth(math.nan)


def test_tablet_view_delegates_interval_editing_state() -> None:
    source = open(
        "src/geoworkbench/tablet/tablet_view.py",
        encoding="utf-8",
    ).read()

    assert "IntervalEditingState(" in source
    assert "self._interval_editing.set_mode(requested)" in source
    assert "self._interval_editing.begin_gesture(" in source
    assert "self._interval_editing.update_current_depth(" in source
    assert "self._interval_editing.cancel_gesture()" in source
