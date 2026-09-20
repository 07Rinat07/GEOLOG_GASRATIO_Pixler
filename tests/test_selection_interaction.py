from dataclasses import dataclass
from pathlib import Path

import pytest

from geoworkbench.tablet.selection_interaction import (
    CommandStack,
    HitResult,
    InterpretationSelectionState,
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

def test_interpretation_selection_state_uses_selection_manager_for_interval() -> None:
    manager = SelectionManager()
    state = InterpretationSelectionState(manager)

    change = state.select_interval("interpretation-1", "interval-1")

    assert change.changed
    assert change.interpretation_changed
    assert change.interval_changed
    assert change.selection_changed
    assert state.interpretation_id == "interpretation-1"
    assert state.interval_id == "interval-1"
    assert manager.primary == SelectionRef(SelectableKind.INTERVAL, "interval-1")


def test_interpretation_selection_state_reuses_interval_without_duplicate_state() -> None:
    manager = SelectionManager()
    state = InterpretationSelectionState(manager, interpretation_id="interpretation-1")
    manager.select(SelectionRef(SelectableKind.INTERVAL, "interval-1"))

    change = state.select_interval("interpretation-1", "interval-1")

    assert not change.changed
    assert not change.selection_changed
    assert state.interval_id == "interval-1"


def test_interpretation_selection_state_clears_interval_when_context_changes() -> None:
    manager = SelectionManager()
    state = InterpretationSelectionState(manager)
    state.select_interval("interpretation-1", "interval-1")

    changed = state.retain_interval({"interval-2", "interval-3"})

    assert changed
    assert state.interval_id is None
    assert manager.snapshot().items == ()
    assert state.interpretation_id == "interpretation-1"


def test_interpretation_selection_state_keeps_valid_interval_and_other_context() -> None:
    manager = SelectionManager()
    state = InterpretationSelectionState(manager)
    state.select_interval("interpretation-1", "interval-1")

    assert not state.retain_interval({"interval-1"})
    assert state.interval_id == "interval-1"

    assert state.set_interpretation("interpretation-2")
    assert state.interpretation_id == "interpretation-2"
    assert state.interval_id == "interval-1"


def test_interpretation_selection_state_rejects_blank_ids() -> None:
    manager = SelectionManager()
    state = InterpretationSelectionState(manager)

    with pytest.raises(ValueError, match="interpretation_id"):
        state.set_interpretation("   ")

    with pytest.raises(ValueError, match="non-empty"):
        state.select_interval("interpretation-1", " ")


def test_tablet_view_has_no_parallel_selected_interval_storage() -> None:
    source = Path("src/geoworkbench/tablet/tablet_view.py").read_text(encoding="utf-8")

    assert "self._selected_interval_id: str | None =" not in source
    assert "self._selected_interpretation_id: str | None =" not in source
    assert "self._interpretation_selection = InterpretationSelectionState(" in source
    assert "return self._interpretation_selection.interval_id" in source
    assert "self._interpretation_selection.select_interval(" in source

