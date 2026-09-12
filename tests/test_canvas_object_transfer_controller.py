from __future__ import annotations

from copy import deepcopy

import pytest

from geoworkbench.domain.models import CanvasObject, Project, Well
from geoworkbench.project.canvas_object_transfer_controller import (
    CanvasObjectCollisionPolicy,
    CanvasObjectTransferAction,
    CanvasObjectTransferController,
    CanvasObjectTransferError,
)
from geoworkbench.project.session import ProjectSession


def _canvas(object_id: str, *, object_type: str = "annotation") -> CanvasObject:
    return CanvasObject(
        object_id=object_id,
        object_type=object_type,
        anchor_type="depth",
        x=0.25,
        y=1500.0,
        width=120.0,
        height=48.0,
        top_depth=1499.5,
        bottom_depth=1500.5,
        parameter_mnemonic="GR",
        track_id="track-geology",
        properties={
            "text": f"note-{object_id}",
            "style": {"color": "#112233", "width": 2.0},
            "points": [[1.0, 2.0], [3.0, 4.0]],
        },
    )


def _session(
    source_objects: list[CanvasObject],
    target_objects: list[CanvasObject] | None = None,
) -> tuple[ProjectSession, Well, Well]:
    source = Well("source-well", "Source", canvas_objects=source_objects)
    target = Well("target-well", "Target", canvas_objects=target_objects or [])
    project = Project(
        "canvas-transfer-project",
        "Canvas transfer",
        wells={source.well_id: source, target.well_id: target},
    )
    session = ProjectSession(
        project=project,
        current_well_id=target.well_id,
    )
    return session, source, target


def test_preview_is_non_mutating_and_apply_deep_copies_selected_objects() -> None:
    source_objects = [_canvas("drawing-a"), _canvas("drawing-b", object_type="symbol")]
    session, source, target = _session(source_objects)
    controller = CanvasObjectTransferController(session)
    source_before = deepcopy(source.canvas_objects)
    target_revision = target.content_revision

    plan = controller.analyze(
        source.well_id,
        target.well_id,
        object_ids=("drawing-b",),
    )

    assert plan.copy_count == 1
    assert plan.skipped_count == 0
    assert plan.collision_count == 0
    assert plan.items[0].source_object_id == "drawing-b"
    assert plan.items[0].target_object_id == "drawing-b"
    assert plan.items[0].action is CanvasObjectTransferAction.COPY
    assert source.canvas_objects == source_before
    assert target.canvas_objects == []
    assert target.content_revision == target_revision
    assert session.dirty is False

    outcome = controller.apply(plan)

    assert outcome.copied_object_ids == ("drawing-b",)
    assert outcome.skipped_object_ids == ()
    assert len(target.canvas_objects) == 1
    copied = target.canvas_objects[0]
    assert copied == source.canvas_objects[1]
    assert copied is not source.canvas_objects[1]
    assert copied.properties is not source.canvas_objects[1].properties
    assert copied.properties["style"] is not source.canvas_objects[1].properties["style"]
    copied.properties["style"]["color"] = "#ffffff"
    assert source.canvas_objects[1].properties["style"]["color"] == "#112233"
    assert target.content_revision == target_revision + 1
    assert session.dirty is True
    with pytest.raises(CanvasObjectTransferError, match="повторно просмотрите"):
        controller.apply(plan)


def test_collision_fails_closed_without_preview_or_mutation() -> None:
    session, source, target = _session(
        [_canvas("same-id")],
        [_canvas("same-id", object_type="existing")],
    )
    controller = CanvasObjectTransferController(session)
    target_before = deepcopy(target.canvas_objects)

    with pytest.raises(CanvasObjectTransferError, match="уже существует"):
        controller.analyze(source.well_id, target.well_id)

    assert target.canvas_objects == target_before
    assert session.dirty is False


def test_skip_policy_preserves_existing_object_and_does_not_dirty_noop() -> None:
    existing = _canvas("same-id", object_type="existing")
    session, source, target = _session([_canvas("same-id")], [existing])
    controller = CanvasObjectTransferController(session)
    original_revision = target.content_revision

    plan = controller.analyze(
        source.well_id,
        target.well_id,
        collision_policy=CanvasObjectCollisionPolicy.SKIP,
    )
    outcome = controller.apply(plan)

    assert plan.copy_count == 0
    assert plan.skipped_count == 1
    assert plan.collision_count == 1
    assert outcome.copied_object_ids == ()
    assert outcome.skipped_object_ids == ("same-id",)
    assert target.canvas_objects == [existing]
    assert target.content_revision == original_revision
    assert session.dirty is False


def test_rename_policy_uses_deterministic_free_id_without_overwrite() -> None:
    existing = _canvas("drawing")
    existing_copy = _canvas("drawing-copy", object_type="existing")
    session, source, target = _session(
        [_canvas("drawing")],
        [existing, existing_copy],
    )
    controller = CanvasObjectTransferController(session)

    plan = controller.analyze(
        source.well_id,
        target.well_id,
        collision_policy=CanvasObjectCollisionPolicy.RENAME,
    )
    outcome = controller.apply(plan)

    assert len(plan.items) == 1
    assert plan.items[0].action is CanvasObjectTransferAction.RENAME
    assert plan.items[0].target_object_id == "drawing-copy-2"
    assert outcome.copied_object_ids == ("drawing-copy-2",)
    assert [item.object_id for item in target.canvas_objects] == [
        "drawing",
        "drawing-copy",
        "drawing-copy-2",
    ]
    assert target.canvas_objects[0] is existing
    assert target.canvas_objects[1] is existing_copy


@pytest.mark.parametrize("changed_side", ["source", "target"])
def test_apply_rejects_stale_preview_and_consumes_authorization(changed_side: str) -> None:
    session, source, target = _session([_canvas("drawing")])
    controller = CanvasObjectTransferController(session)
    plan = controller.analyze(source.well_id, target.well_id)

    changed = source if changed_side == "source" else target
    changed.canvas_objects.append(_canvas(f"late-{changed_side}"))
    target_before = deepcopy(target.canvas_objects)
    dirty_before = session.dirty

    with pytest.raises(CanvasObjectTransferError, match="изменились"):
        controller.apply(plan)

    assert target.canvas_objects == target_before
    assert session.dirty is dirty_before
    with pytest.raises(CanvasObjectTransferError, match="повторно просмотрите"):
        controller.apply(plan)


def test_source_and_target_wells_must_be_distinct() -> None:
    session, source, _target = _session([_canvas("drawing")])
    controller = CanvasObjectTransferController(session)

    with pytest.raises(CanvasObjectTransferError, match="разными скважинами"):
        controller.analyze(source.well_id, source.well_id)
