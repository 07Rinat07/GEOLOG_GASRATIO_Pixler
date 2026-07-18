from copy import deepcopy

import pytest

from geoworkbench.domain.models import CanvasObject, Well
from geoworkbench.services.canvas_history import CanvasHistoryConflictError, CanvasObjectHistory


def make_object(object_id: str) -> CanvasObject:
    return CanvasObject(object_id, "note", "depth", 0.0, 100.0, 1.0, 0.0)


def test_canvas_history_detects_external_changes() -> None:
    well = Well("well", "Well", canvas_objects=[make_object("one")])
    history = CanvasObjectHistory()
    before = deepcopy(well.canvas_objects)
    well.canvas_objects.append(make_object("two"))
    history.record(well, before, description="Добавление")
    well.canvas_objects.append(make_object("external"))

    with pytest.raises(CanvasHistoryConflictError, match="вне истории"):
        history.undo()

    assert history.can_undo is True
    assert history.can_redo is False
