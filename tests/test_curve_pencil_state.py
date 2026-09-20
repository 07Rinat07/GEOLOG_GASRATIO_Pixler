from __future__ import annotations

import pytest

from geoworkbench.tablet.curve_pencil_state import (
    CurvePencilMode,
    CurvePencilPoint,
    CurvePencilState,
)


def test_curve_pencil_state_target_and_disable_transition() -> None:
    state = CurvePencilState()
    state.select_target("track-1", "GR", "curve-1")
    state.enabled = True
    state.points.append(CurvePencilPoint(1000.0, 12.5, 0.4))
    state.acknowledge_commit(False, "write rejected")

    state.set_enabled(False)

    assert not state.enabled
    assert state.target is None
    assert state.curve_id is None
    assert state.points == []
    assert state.commit_ack is None
    assert state.commit_error == ""


def test_curve_pencil_state_mode_change_cancels_pending_gesture() -> None:
    state = CurvePencilState(
        enabled=True,
        points=[CurvePencilPoint(1000.0, 10.0, 0.2)],
        commit_ack=False,
        commit_error="retry",
    )

    state.set_mode(CurvePencilMode.CONNECT_POINTS)

    assert state.mode is CurvePencilMode.CONNECT_POINTS
    assert state.points == []
    assert state.commit_ack is None
    assert state.commit_error == ""


def test_curve_pencil_state_history_and_dirty_flags_are_independent() -> None:
    state = CurvePencilState()

    state.set_history(can_undo=True, can_redo=False)
    state.mark_unsaved()

    assert state.can_undo
    assert not state.can_redo
    assert state.unsaved

    state.clear_unsaved()

    assert state.can_undo
    assert not state.unsaved


def test_curve_pencil_state_rejects_invalid_target_or_mode() -> None:
    state = CurvePencilState()

    with pytest.raises(ValueError, match="non-empty"):
        state.select_target("", "GR", "curve-1")

    with pytest.raises(TypeError, match="CurvePencilMode"):
        state.set_mode("freehand")  # type: ignore[arg-type]
