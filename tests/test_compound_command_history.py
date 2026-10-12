import pytest

from geoworkbench.services.edit_history import CallbackCommand, CommandHistory, CompoundCommand


def _command(values, value, *, fail_execute=False, fail_undo=False):
    def execute():
        if fail_execute:
            raise RuntimeError("execute failure")
        values.append(value)
    def undo():
        if fail_undo:
            raise RuntimeError("undo failure")
        assert values[-1] == value
        values.pop()
    return CallbackCommand(str(value), "report_annotation", execute, undo)


def test_compound_is_one_chronological_entry_with_ordered_undo_redo():
    values = []
    history = CommandHistory()
    command = CompoundCommand("Batch", "report_annotation", tuple(_command(values, i) for i in range(20)))
    history.execute(command)
    assert values == list(range(20))
    assert history.next_undo is command
    history.undo()
    assert values == []
    assert not history.can_undo
    assert history.next_redo is command
    history.redo()
    assert values == list(range(20))
    assert not history.can_redo


def test_compound_failed_execute_rolls_back_completed_children_and_keeps_redo():
    values = []
    history = CommandHistory()
    previous = _command(values, 0)
    history.execute(previous)
    history.undo()
    compound = CompoundCommand("Batch", "report_annotation", (
        _command(values, 1), _command(values, 2), _command(values, 3, fail_execute=True),
    ))
    with pytest.raises(RuntimeError, match="execute failure"):
        history.execute(compound)
    assert values == []
    assert not history.can_undo
    assert history.next_redo is previous


def test_compound_failed_undo_reapplies_completed_children_and_keeps_stack():
    values = []
    history = CommandHistory()
    compound = CompoundCommand("Batch", "report_annotation", (
        _command(values, 1, fail_undo=True), _command(values, 2), _command(values, 3),
    ))
    history.execute(compound)
    with pytest.raises(RuntimeError, match="undo failure"):
        history.undo()
    assert values == [1, 2, 3]
    assert history.next_undo is compound
    assert not history.can_redo


def test_compound_surfaces_compensation_failure_without_recording_success():
    values = []
    history = CommandHistory()
    compound = CompoundCommand("Batch", "report_annotation", (
        _command(values, 1, fail_undo=True), _command(values, 2, fail_execute=True),
    ))
    with pytest.raises(ExceptionGroup) as caught:
        history.execute(compound)
    assert len(caught.value.exceptions) == 2
    assert not history.can_undo
    assert not history.can_redo


def test_compound_rejects_empty_duplicate_and_mixed_domain_children():
    values = []
    child = _command(values, 1)
    for commands in ((), (child, child), (CallbackCommand("Other", "curve", lambda: None, lambda: None),)):
        with pytest.raises(ValueError):
            CompoundCommand("Batch", "report_annotation", commands)
