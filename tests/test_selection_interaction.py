from dataclasses import dataclass

import pytest

from geoworkbench.tablet.selection_interaction import (
    CommandStack,
    HitResult,
    SelectableKind,
    SelectionManager,
    SelectionRef,
    choose_best_hit,
)


def test_choose_best_hit_uses_priority_then_distance() -> None:
    track = SelectionRef(SelectableKind.TRACK, "track-1")
    curve = SelectionRef(SelectableKind.CURVE, "curve-1", "track-1")
    result = choose_best_hit(
        [
            HitResult(track, priority=10, distance_px=0),
            HitResult(curve, priority=20, distance_px=4),
            HitResult(SelectionRef(SelectableKind.CURVE, "curve-2"), priority=20, distance_px=2),
        ]
    )
    assert result is not None
    assert result.target.object_id == "curve-2"


def test_selection_manager_single_additive_toggle_and_kind_clear() -> None:
    manager = SelectionManager()
    track = SelectionRef(SelectableKind.TRACK, "track-1")
    curve = SelectionRef(SelectableKind.CURVE, "curve-1", "track-1")

    assert manager.select(track) is True
    assert manager.primary == track
    assert manager.select(curve, additive=True) is True
    assert manager.snapshot().items == (track, curve)
    assert manager.select(curve, additive=True, toggle=True) is True
    assert manager.snapshot().items == (track,)
    assert manager.clear(kind=SelectableKind.TRACK) is True
    assert manager.snapshot().items == ()


def test_selection_replace_requires_primary_inside_set() -> None:
    manager = SelectionManager()
    item = SelectionRef(SelectableKind.TRACK, "a")
    with pytest.raises(ValueError):
        manager.replace([item], primary=SelectionRef(SelectableKind.TRACK, "b"))


@dataclass
class _SetValue:
    state: dict[str, int]
    old: int
    new: int
    description: str = "set value"

    def redo(self) -> None:
        self.state["value"] = self.new

    def undo(self) -> None:
        self.state["value"] = self.old


def test_command_stack_execute_undo_redo() -> None:
    state = {"value": 1}
    stack = CommandStack()
    stack.execute(_SetValue(state, old=1, new=2))
    assert state["value"] == 2
    assert stack.undo() is True
    assert state["value"] == 1
    assert stack.redo() is True
    assert state["value"] == 2
