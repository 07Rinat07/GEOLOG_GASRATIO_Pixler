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


def test_annotations_are_scoped_to_current_tablet_form() -> None:
    from geoworkbench.project.annotation_schema import annotation_scope_id_for_session
    from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind

    controller = make_controller()
    first_layout = TabletLayout(
        tracks=[TrackDefinition("form-a-track", "A", TrackKind.CURVE)],
        vertical_index_id=controller.session.current_dataset.active_index.index_id,
    )
    controller.session.set_current_tablet_layout(first_layout)
    created = controller.add_annotation(text="Только форма A", depth=150.0)
    first_scope = annotation_scope_id_for_session(controller.session)

    assert created.scope_id == first_scope
    assert [item.annotation_id for item in controller.available_annotations()] == [
        created.annotation_id
    ]
    assert [item.object_id for item in controller.canvas_objects_for_current_scope()] == [
        created.annotation_id
    ]

    second_layout = TabletLayout(
        tracks=[TrackDefinition("form-b-track", "B", TrackKind.CURVE)],
        vertical_index_id=controller.session.current_dataset.active_index.index_id,
    )
    controller.session.set_current_tablet_layout(second_layout)

    assert controller.available_annotations() == ()
    assert controller.canvas_objects_for_current_scope() == []
    assert controller.available_annotations(include_all_scopes=True)[0].annotation_id == created.annotation_id

    controller.session.set_current_tablet_layout(first_layout)
    assert controller.available_annotations()[0].annotation_id == created.annotation_id


def test_legacy_unscoped_annotations_are_adopted_by_current_form_once() -> None:
    from geoworkbench.domain.models import CanvasObject
    from geoworkbench.project.annotation_schema import annotation_scope_id_for_session
    from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind

    controller = make_controller()
    controller.session.set_current_tablet_layout(
        TabletLayout(
            tracks=[TrackDefinition("legacy-form-track", "Legacy", TrackKind.CURVE)],
            vertical_index_id=controller.session.current_dataset.active_index.index_id,
        )
    )
    well = controller.session.current_well
    assert well is not None
    legacy = CanvasObject(
        object_id="legacy-note",
        object_type="annotation",
        anchor_type="depth",
        x=0.5,
        y=150.0,
        width=200.0,
        height=70.0,
        top_depth=150.0,
        bottom_depth=150.0,
        properties={"kind": "comment", "text": "Старая заметка"},
    )
    well.canvas_objects.append(legacy)

    assert controller.adopt_unscoped_annotations() == 1
    assert controller.adopt_unscoped_annotations() == 0
    assert legacy.properties["scope_id"] == annotation_scope_id_for_session(controller.session)
    assert controller.available_annotations()[0].annotation_id == "legacy-note"


def test_rebinding_current_scope_moves_annotations_to_saved_form_scope() -> None:
    from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind

    controller = make_controller()
    layout = TabletLayout(
        tracks=[TrackDefinition("working-track", "Working", TrackKind.CURVE)],
        vertical_index_id=controller.session.current_dataset.active_index.index_id,
        annotation_scope_id="dataset:dataset:default",
    )
    controller.session.set_current_tablet_layout(layout)
    created = controller.add_annotation(text="Сохранить с формой", depth=150.0)

    changed = controller.rebind_current_scope("dataset:dataset:form:user-form")

    assert changed == 1
    assert layout.annotation_scope_id == "dataset:dataset:form:user-form"
    assert controller.get(created.annotation_id).scope_id == "dataset:dataset:form:user-form"


def test_annotation_scope_stays_stable_when_tracks_are_edited() -> None:
    from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind

    controller = make_controller()
    layout = TabletLayout(
        tracks=[TrackDefinition("track-one", "One", TrackKind.CURVE)],
        vertical_index_id=controller.session.current_dataset.active_index.index_id,
        annotation_scope_id="dataset:dataset:form:stable",
    )
    controller.session.set_current_tablet_layout(layout)
    created = controller.add_annotation(text="Не исчезать", depth=150.0)

    layout.add_track(TrackDefinition("track-two", "Two", TrackKind.CURVE))
    layout.remove_track("track-one")

    assert controller.current_scope_id() == "dataset:dataset:form:stable"
    assert controller.available_annotations()[0].annotation_id == created.annotation_id


def test_forms_with_identical_tracks_keep_annotations_isolated_by_form_id() -> None:
    """Form identity, not visual similarity, owns annotation visibility."""

    from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind

    controller = make_controller()
    axis_id = controller.session.current_dataset.active_index.index_id
    shared_tracks_a = [TrackDefinition("shared-track", "Shared", TrackKind.CURVE)]
    form_a = TabletLayout(
        tracks=shared_tracks_a,
        vertical_index_id=axis_id,
        annotation_scope_id="dataset:dataset:form:form-a",
    )
    controller.session.set_current_tablet_layout(form_a)
    created = controller.add_annotation(text="Только A", depth=150.0)

    form_b = TabletLayout(
        tracks=[TrackDefinition("shared-track", "Shared", TrackKind.CURVE)],
        vertical_index_id=axis_id,
        annotation_scope_id="dataset:dataset:form:form-b",
    )
    controller.session.set_current_tablet_layout(form_b)

    assert controller.available_annotations() == ()
    assert controller.canvas_objects_for_current_scope() == []

    controller.session.set_current_tablet_layout(form_a)
    assert [record.annotation_id for record in controller.available_annotations()] == [
        created.annotation_id
    ]


def test_delete_removes_model_object_and_undo_restores_same_form_scope() -> None:
    from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind

    controller = make_controller()
    controller.session.set_current_tablet_layout(
        TabletLayout(
            tracks=[TrackDefinition("delete-track", "Delete", TrackKind.CURVE)],
            vertical_index_id=controller.session.current_dataset.active_index.index_id,
            annotation_scope_id="dataset:dataset:form:delete-form",
        )
    )
    created = controller.add_annotation(text="Удалить", depth=150.0)
    controller.history.clear()

    removed = controller.remove(created.annotation_id)

    assert removed.annotation_id == created.annotation_id
    assert controller.available_annotations() == ()
    assert controller.canvas_objects_for_current_scope() == []
    well = controller.session.current_well
    assert well is not None
    assert all(item.object_id != created.annotation_id for item in well.canvas_objects)

    controller.undo()
    restored = controller.get(created.annotation_id)
    assert restored.scope_id == "dataset:dataset:form:delete-form"
    assert controller.available_annotations()[0].annotation_id == created.annotation_id


def test_duplicate_never_leaks_into_another_form_scope() -> None:
    from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind

    controller = make_controller()
    axis_id = controller.session.current_dataset.active_index.index_id
    form_a = TabletLayout(
        tracks=[TrackDefinition("track-a", "A", TrackKind.CURVE)],
        vertical_index_id=axis_id,
        annotation_scope_id="dataset:dataset:form:a",
    )
    controller.session.set_current_tablet_layout(form_a)
    created = controller.add_annotation(text="A", depth=150.0)
    duplicate = controller.duplicate(created.annotation_id)

    assert duplicate.scope_id == created.scope_id == "dataset:dataset:form:a"

    controller.session.set_current_tablet_layout(
        TabletLayout(
            tracks=[TrackDefinition("track-b", "B", TrackKind.CURVE)],
            vertical_index_id=axis_id,
            annotation_scope_id="dataset:dataset:form:b",
        )
    )
    assert controller.available_annotations() == ()


def test_stale_annotation_id_cannot_delete_object_from_previous_form() -> None:
    from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind

    controller = make_controller()
    axis_id = controller.session.current_dataset.active_index.index_id
    controller.session.set_current_tablet_layout(
        TabletLayout(
            tracks=[TrackDefinition("scope-a", "A", TrackKind.CURVE)],
            vertical_index_id=axis_id,
            annotation_scope_id="dataset:dataset:form:a",
        )
    )
    created = controller.add_annotation(text="A", depth=150.0)

    controller.session.set_current_tablet_layout(
        TabletLayout(
            tracks=[TrackDefinition("scope-b", "B", TrackKind.CURVE)],
            vertical_index_id=axis_id,
            annotation_scope_id="dataset:dataset:form:b",
        )
    )

    with pytest.raises(KeyError, match="текущей форме"):
        controller.remove(created.annotation_id)

    well = controller.session.current_well
    assert well is not None
    assert any(item.object_id == created.annotation_id for item in well.canvas_objects)
