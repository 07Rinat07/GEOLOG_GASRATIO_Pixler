import numpy as np
import pytest

from geoworkbench.domain.models import CurveData, CurveMetadata
from geoworkbench.services.edit_history import (
    CommandHistory,
    CurveEditCommand,
    CurveEditConflictError,
    CurveEditHistory,
)


def make_curve() -> CurveData:
    return CurveData(
        CurveMetadata("curve-1", "ROP", "ROP", "m/h", None, "dataset-1"),
        np.array([10.0, 20.0, 30.0, 40.0]),
    )


def test_history_executes_undoes_and_redoes_curve_edit() -> None:
    curve = make_curve()
    history = CurveEditHistory()
    command = CurveEditCommand.create(
        curve,
        np.array([1, 2]),
        np.array([25.0, 35.0]),
        description="Карандаш ROP",
    )

    history.execute(command)
    np.testing.assert_allclose(curve.values, [10.0, 25.0, 35.0, 40.0])
    assert curve.version == 2
    assert history.can_undo is True
    assert history.can_redo is False

    assert history.undo() is command
    np.testing.assert_allclose(curve.values, [10.0, 20.0, 30.0, 40.0])
    assert curve.version == 3
    assert history.can_redo is True

    assert history.redo() is command
    np.testing.assert_allclose(curve.values, [10.0, 25.0, 35.0, 40.0])
    assert curve.version == 4


def test_new_command_clears_redo_stack() -> None:
    curve = make_curve()
    history = CurveEditHistory()
    history.execute(CurveEditCommand.create(curve, np.array([0]), np.array([11.0])))
    history.undo()

    history.execute(CurveEditCommand.create(curve, np.array([3]), np.array([44.0])))

    assert history.can_redo is False
    with pytest.raises(RuntimeError, match="Нет команд"):
        history.redo()


def test_command_detects_external_curve_change_before_undo() -> None:
    curve = make_curve()
    history = CurveEditHistory()
    history.execute(CurveEditCommand.create(curve, np.array([1]), np.array([22.0])))
    curve.values[1] = 999.0

    with pytest.raises(CurveEditConflictError, match="вне истории"):
        history.undo()

    assert history.can_undo is True


@pytest.mark.parametrize(
    ("indices", "values", "error"),
    [
        (np.array([], dtype=np.int64), np.array([]), ValueError),
        (np.array([1, 1]), np.array([2.0, 3.0]), ValueError),
        (np.array([1, 2]), np.array([2.0]), ValueError),
        (np.array([-1]), np.array([2.0]), IndexError),
        (np.array([99]), np.array([2.0]), IndexError),
    ],
)
def test_command_rejects_invalid_edits(indices, values, error) -> None:
    with pytest.raises(error):
        CurveEditCommand.create(make_curve(), indices, values)


def test_history_rejects_invalid_limit_and_empty_operations() -> None:
    with pytest.raises(ValueError):
        CurveEditHistory(max_commands=0)

    history = CurveEditHistory()
    with pytest.raises(RuntimeError, match="отмены"):
        history.undo()
    with pytest.raises(RuntimeError, match="повтора"):
        history.redo()


class _ValueCommand:
    def __init__(self, state: list[int], before: int, after: int, domain: str) -> None:
        self.state = state
        self.before = before
        self.after = after
        self.description = f"{domain}: {before}->{after}"
        self.history_domain = domain
        self.applied = False

    def execute(self) -> None:
        if self.state[0] != self.before:
            raise RuntimeError("unexpected before state")
        self.state[0] = self.after
        self.applied = True

    def undo(self) -> None:
        if self.state[0] != self.after:
            raise RuntimeError("unexpected after state")
        self.state[0] = self.before
        self.applied = False


def test_shared_history_preserves_cross_domain_chronology_and_branching() -> None:
    state = [0]
    history = CommandHistory()
    first = _ValueCommand(state, 0, 1, "curve")
    second = _ValueCommand(state, 1, 2, "header")

    history.execute(first)
    history.execute(second)

    assert history.next_undo is second
    assert history.undo() is second
    assert state == [1]
    assert history.undo() is first
    assert state == [0]

    replacement = _ValueCommand(state, 0, 3, "header")
    history.execute(replacement)

    assert state == [3]
    assert history.can_redo is False
    assert history.next_undo is replacement


def test_history_keeps_stacks_intact_when_undo_conflicts() -> None:
    state = [0]
    history = CommandHistory()
    command = _ValueCommand(state, 0, 1, "header")
    history.execute(command)
    state[0] = 99

    with pytest.raises(RuntimeError, match="unexpected after"):
        history.undo()

    assert history.next_undo is command
    assert history.can_redo is False


def test_history_notifies_listener_after_successful_transitions_only() -> None:
    state = [0]
    history = CommandHistory()
    observed: list[tuple[bool, bool]] = []
    history.add_listener(lambda: observed.append((history.can_undo, history.can_redo)))
    command = _ValueCommand(state, 0, 1, "curve")

    history.execute(command)
    history.undo()
    history.redo()
    history.clear()

    assert observed == [
        (True, False),
        (False, True),
        (True, False),
        (False, False),
    ]



def test_history_checkpoint_restores_redo_branch_after_external_transaction_rollback() -> None:
    state = [0]
    history = CommandHistory()
    first = _ValueCommand(state, 0, 1, "curve")
    history.execute(first)
    history.undo()
    checkpoint = history.checkpoint()
    observed: list[tuple[bool, bool]] = []
    history.add_listener(lambda: observed.append((history.can_undo, history.can_redo)))

    second = _ValueCommand(state, 0, 2, "dataset_merge")
    state[0] = 2
    second.applied = True
    history.record_applied(second)

    assert history.can_redo is False
    assert history.next_undo is second

    state[0] = 0
    history.restore(checkpoint)

    assert history.can_undo is False
    assert history.next_redo is first
    assert observed == [(True, False), (False, True)]

    history.redo()
    assert state == [1]


def test_history_checkpoint_rejects_checkpoint_from_another_history() -> None:
    first = CommandHistory()
    second = CommandHistory()
    checkpoint = first.checkpoint()

    with pytest.raises(ValueError, match="другой истории"):
        second.restore(checkpoint)



def test_history_commands_since_returns_identity_suffix() -> None:
    state = [0]
    history = CommandHistory()
    first = _ValueCommand(state, 0, 1, "curve")
    history.execute(first)
    checkpoint = history.checkpoint()
    second = _ValueCommand(state, 1, 2, "report_annotation")
    history.execute(second)

    assert history.commands_since(checkpoint) == (second,)


def test_history_commands_since_rejects_divergence_and_foreign_checkpoint() -> None:
    state = [0]
    history = CommandHistory()
    first = _ValueCommand(state, 0, 1, "curve")
    history.execute(first)
    checkpoint = history.checkpoint()
    history.undo()

    with pytest.raises(RuntimeError, match="разошлась"):
        history.commands_since(checkpoint)

    foreign = CommandHistory().checkpoint()
    with pytest.raises(ValueError, match="другой истории"):
        history.commands_since(foreign)
