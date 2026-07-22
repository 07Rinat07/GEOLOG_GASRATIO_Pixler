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


def test_professional_annotation_preserves_anchor_style_and_geometry() -> None:
    from geoworkbench.project.annotation_schema import (
        AnnotationAnchor,
        AnnotationKind,
        AnnotationStyle,
    )

    controller = make_controller()
    dataset = controller.session.current_dataset
    assert dataset is not None
    dataset.upsert_curve("ROP", np.array([10.0, 20.0]))
    style = AnnotationStyle(
        font_family="DejaVu Sans",
        font_size=13.0,
        bold=True,
        italic=True,
        text_color="#112233",
        fill_color="#fef3c7",
        fill_opacity=0.8,
        border_color="#b45309",
        border_width=2.0,
        border_style="dash",
        leader_color="#92400e",
        leader_style="dot",
        arrow_style="open",
        vertical_alignment="center",
        shadow_blur=9.0,
        shadow_offset_x=4.0,
        shadow_offset_y=5.0,
        rotation=7.0,
    )

    created = controller.add_annotation(
        kind=AnnotationKind.CALLOUT,
        anchor=AnnotationAnchor.CURVE,
        text="Параметры бурового раствора",
        track_id="drilling",
        depth=150.0,
        parameter_mnemonic="ROP",
        parameter_value=15.0,
        unit="m/h",
        x_fraction=0.35,
        offset_x=22.0,
        offset_y=-44.0,
        width=280.0,
        height=96.0,
        style=style,
        locked=True,
        print_enabled=True,
    )

    stored = controller.session.current_well.canvas_objects[-1]
    assert stored.object_type == "annotation"
    assert stored.anchor_type == "curve"
    assert stored.track_id == "drilling"
    assert stored.parameter_mnemonic == "ROP"
    assert created.style == style
    assert created.parameter_value == 15.0
    assert created.locked is True

    changed = controller.set_geometry(
        created.annotation_id,
        offset_x=40.0,
        offset_y=18.0,
        width=310.0,
        height=110.0,
    )
    assert (changed.offset_x, changed.offset_y, changed.width, changed.height) == (
        40.0,
        18.0,
        310.0,
        110.0,
    )

    duplicate = controller.duplicate(created.annotation_id)
    assert duplicate.annotation_id != created.annotation_id
    assert duplicate.text == created.text
    assert duplicate.style == created.style
    assert duplicate.locked is False
    assert duplicate.offset_x == changed.offset_x + 16.0
    assert duplicate.offset_y == changed.offset_y + 16.0


def test_curve_value_can_be_saved_as_print_annotation() -> None:
    from geoworkbench.project.annotation_schema import AnnotationAnchor, AnnotationKind

    controller = make_controller()
    dataset = controller.session.current_dataset
    assert dataset is not None
    dataset.upsert_curve("TG", np.array([1.5, 3.5]), unit="%")

    saved = controller.add_curve_value(
        track_id="gas",
        depth=150.0,
        axis_value=150.0,
        axis_id=dataset.active_index.index_id,
        mnemonic="TG",
        value=2.5,
        unit="%",
        x_fraction=0.42,
    )

    assert saved.kind is AnnotationKind.VALUE
    assert saved.anchor is AnnotationAnchor.CURVE
    assert saved.text == "TG: 2.5 %"
    assert saved.parameter_mnemonic == "TG"
    assert saved.parameter_value == 2.5
    assert saved.print_enabled is True
    assert saved.style.bold is True


def test_curve_anchor_derives_parameter_value_and_unit_after_depth_change() -> None:
    from geoworkbench.project.annotation_schema import AnnotationAnchor, AnnotationKind

    controller = make_controller()
    dataset = controller.session.current_dataset
    assert dataset is not None
    dataset.upsert_curve("ROP", np.array([10.0, 20.0]), unit="m/h")

    created = controller.add_annotation(
        kind=AnnotationKind.CALLOUT,
        anchor=AnnotationAnchor.CURVE,
        text="Рейс",
        depth=100.0,
        parameter_mnemonic="ROP",
    )
    assert created.parameter_value == 10.0
    assert created.unit == "m/h"

    updated = controller.update_annotation(created.annotation_id, depth=200.0)
    assert updated.parameter_value == 20.0
    assert updated.unit == "m/h"


def test_time_annotation_preserves_axis_and_canonical_depth() -> None:
    from geoworkbench.domain.models import DatasetIndex, IndexRole, IndexType
    from geoworkbench.project.annotation_schema import AnnotationAnchor, AnnotationKind

    controller = make_controller()
    dataset = controller.session.current_dataset
    assert dataset is not None
    dataset.add_index(
        DatasetIndex(
            "time",
            "TIME",
            IndexType.RELATIVE_TIME,
            IndexRole.TIME,
            "s",
            np.array([0.0, 10.0]),
        )
    )

    created = controller.add_annotation(
        kind=AnnotationKind.COMMENT,
        anchor=AnnotationAnchor.TIME,
        text="Остановка циркуляции",
        track_id=None,
        depth=150.0,
        axis_value=5.0,
        axis_id="time",
        x_fraction=0.7,
    )

    assert created.anchor is AnnotationAnchor.TIME
    assert created.depth == 150.0
    assert created.axis_value == 5.0
    assert created.axis_id == "time"


def test_identical_geometry_does_not_create_history_or_dirty_project() -> None:
    controller = make_controller()
    created = controller.add_annotation(text="Без движения", depth=150.0)
    controller.history.clear()
    controller.session.dirty = False

    same = controller.set_geometry(
        created.annotation_id,
        offset_x=created.offset_x,
        offset_y=created.offset_y,
        width=created.width,
        height=created.height,
    )

    assert same == created
    assert controller.session.dirty is False
    with pytest.raises(RuntimeError, match="Нет операций"):
        controller.undo()
