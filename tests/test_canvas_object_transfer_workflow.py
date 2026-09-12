from __future__ import annotations

from pathlib import Path

import pytest

from geoworkbench.domain.models import CanvasObject, Project, Well
from geoworkbench.project.canvas_object_transfer_controller import (
    CanvasObjectCollisionPolicy,
    CanvasObjectTransferController,
)
from geoworkbench.project.canvas_object_transfer_workflow import (
    CanvasObjectTransferPersistenceError,
    CanvasObjectTransferWorkflow,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.storage.project_file_safety import SaveMode


def _canvas(object_id: str) -> CanvasObject:
    return CanvasObject(
        object_id=object_id,
        object_type="annotation",
        anchor_type="depth",
        y=1000.0,
        properties={"text": object_id},
    )


def _session(*, collision: bool = False) -> tuple[ProjectSession, Well, Well]:
    source = Well("source", "Source", canvas_objects=[_canvas("drawing")])
    target_objects = [_canvas("drawing")] if collision else []
    target = Well("target", "Target", canvas_objects=target_objects)
    session = ProjectSession(
        project=Project(
            "project",
            "Project",
            wells={source.well_id: source, target.well_id: target},
        ),
        current_well_id=target.well_id,
    )
    return session, source, target


class _Saver:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.modes: list[SaveMode] = []

    def save_project(
        self,
        target: Path | None = None,
        *,
        mode: SaveMode = SaveMode.EXPLICIT,
        allow_existing_target: bool = False,
    ) -> Path:
        del target, allow_existing_target
        self.modes.append(mode)
        if self.fail:
            raise OSError("disk unavailable")
        return Path("project.geologpkg")


def test_confirmed_transfer_is_material_autosaved() -> None:
    session, source, target = _session()
    saver = _Saver()
    workflow = CanvasObjectTransferWorkflow(
        session,
        CanvasObjectTransferController(session),
        saver,
    )

    plan = workflow.analyze(
        source.well_id,
        target.well_id,
        object_ids=("drawing",),
    )
    outcome = workflow.apply(plan)

    assert outcome.copied_object_ids == ("drawing",)
    assert [item.object_id for item in target.canvas_objects] == ["drawing"]
    assert session.dirty is True
    assert saver.modes == [SaveMode.MATERIAL_AUTOSAVE]


def test_failed_material_autosave_restores_target_exactly() -> None:
    session, source, target = _session()
    existing = _canvas("existing")
    target.canvas_objects.append(existing)
    original_revision = target.content_revision
    session.dirty = False
    saver = _Saver(fail=True)
    workflow = CanvasObjectTransferWorkflow(
        session,
        CanvasObjectTransferController(session),
        saver,
    )
    plan = workflow.analyze(
        source.well_id,
        target.well_id,
        object_ids=("drawing",),
    )

    with pytest.raises(
        CanvasObjectTransferPersistenceError,
        match="изменения полностью отменены",
    ):
        workflow.apply(plan)

    assert target.canvas_objects == [existing]
    assert target.canvas_objects[0] is existing
    assert target.content_revision == original_revision
    assert session.dirty is False
    assert saver.modes == [SaveMode.MATERIAL_AUTOSAVE]


def test_skip_only_plan_does_not_trigger_material_autosave() -> None:
    session, source, target = _session(collision=True)
    existing = target.canvas_objects[0]
    original_revision = target.content_revision
    saver = _Saver()
    workflow = CanvasObjectTransferWorkflow(
        session,
        CanvasObjectTransferController(session),
        saver,
    )

    plan = workflow.analyze(
        source.well_id,
        target.well_id,
        object_ids=("drawing",),
        collision_policy=CanvasObjectCollisionPolicy.SKIP,
    )
    outcome = workflow.apply(plan)

    assert outcome.copied_object_ids == ()
    assert outcome.skipped_object_ids == ("drawing",)
    assert target.canvas_objects == [existing]
    assert target.canvas_objects[0] is existing
    assert target.content_revision == original_revision
    assert session.dirty is False
    assert saver.modes == []
