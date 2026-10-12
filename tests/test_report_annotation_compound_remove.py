import pytest

from geoworkbench.project.report_annotation_controller import ReportAnnotationController
from geoworkbench.services.edit_history import CommandHistory, CompoundCommand
from test_report_annotations import _session


def test_compound_remove_preserves_order_one_entry_and_checkpoint_redo():
    session = _session()
    history = CommandHistory()
    controller = ReportAnnotationController(session, shared_history=history)
    records = tuple(controller.add(text=str(i), depth=1000.0 + i) for i in range(20))
    checkpoint = controller.checkpoint()
    chosen = (records[15], records[2], records[10])
    assert controller.remove_many([record.annotation_id for record in chosen]) == chosen
    command = history.next_undo
    assert isinstance(command, CompoundCommand)
    assert controller.can_undo
    assert controller.available() == tuple(record for record in records if record not in chosen)
    controller.undo()
    assert controller.available() == records
    redo_checkpoint = controller.checkpoint()
    controller.redo()
    controller.restore(redo_checkpoint)
    assert history.next_redo is command
    controller.redo()
    controller.restore(checkpoint)
    assert controller.available() == records
    controller.undo()
    controller.redo()
    assert controller.available() == records


@pytest.mark.parametrize("invalid", ["missing", "duplicate", "empty", "string"])
def test_compound_remove_rejects_entire_invalid_selection_before_mutation(invalid):
    session = _session()
    history = CommandHistory()
    controller = ReportAnnotationController(session, shared_history=history)
    record = controller.add(text="Saved", depth=1000.0)
    retained = history.next_undo
    session.dirty = False
    selections = {
        "missing": [record.annotation_id, "missing"],
        "duplicate": [record.annotation_id, record.annotation_id],
        "empty": [], "string": record.annotation_id,
    }
    with pytest.raises((KeyError, ValueError, TypeError)):
        controller.remove_many(selections[invalid])
    assert controller.available() == (record,)
    assert history.next_undo is retained
    assert not session.dirty


def test_foreign_compound_children_block_undo_and_checkpoint_restore():
    session = _session()
    foreign_session = _session()
    history = CommandHistory()
    own = ReportAnnotationController(session, shared_history=history)
    own_record = own.add(text="Own", depth=1000.0)
    checkpoint = own.checkpoint()
    foreign = ReportAnnotationController(foreign_session, shared_history=history)
    records = [foreign.add(text=str(i), depth=1000.0 + i) for i in range(2)]
    foreign.remove_many([record.annotation_id for record in records])
    retained = history.next_undo
    assert not own.can_undo
    assert foreign.can_undo
    with pytest.raises(RuntimeError, match="другая область"):
        own.restore(checkpoint)
    assert own.available() == (own_record,)
    assert foreign.available() == ()
    assert history.next_undo is retained
