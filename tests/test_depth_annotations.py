import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.annotation_controller import DepthAnnotationController
from geoworkbench.project.session import ProjectSession


def make_controller() -> DepthAnnotationController:
    dataset = Dataset("dataset", "Well", DatasetKind.GTI, DepthDomain.MD, np.array([100.0, 200.0]))
    session = ProjectSession()
    session.add_dataset(dataset)
    session.dirty = False
    return DepthAnnotationController(session)


def test_depth_annotation_crud_uses_canvas_objects() -> None:
    controller = make_controller()
    created = controller.add(150.0, "  Газопроявление  ")

    assert created.text == "Газопроявление"
    assert controller.available() == (created,)
    assert controller.session.current_well is not None
    stored = controller.session.current_well.canvas_objects[0]
    assert stored.object_type == "depth_annotation"
    assert stored.anchor_type == "depth"
    assert stored.top_depth == 150.0

    updated = controller.update(created.annotation_id, depth=160.0, text="Проверить")
    assert updated.depth == 160.0
    assert controller.remove(created.annotation_id) == updated
    assert controller.available() == ()
    assert controller.session.dirty is True


def test_depth_annotation_validates_text_and_dataset_range() -> None:
    controller = make_controller()
    with pytest.raises(ValueError, match="пустым"):
        controller.add(150.0, "  ")
    with pytest.raises(ValueError, match="вне"):
        controller.add(300.0, "Вне диапазона")


def test_depth_annotation_history_undoes_and_redoes_crud() -> None:
    controller = make_controller()
    created = controller.add(150.0, "Первая")
    controller.update(created.annotation_id, depth=160.0, text="Изменена")
    controller.remove(created.annotation_id)

    assert controller.available() == ()
    assert controller.undo() == "Удаление глубинной заметки"
    assert controller.available()[0].text == "Изменена"
    assert controller.undo() == "Изменение глубинной заметки"
    assert controller.available()[0].text == "Первая"
    assert controller.undo() == "Добавление глубинной заметки"
    assert controller.available() == ()

    assert controller.redo() == "Добавление глубинной заметки"
    assert controller.redo() == "Изменение глубинной заметки"
    assert controller.redo() == "Удаление глубинной заметки"
    assert controller.available() == ()
