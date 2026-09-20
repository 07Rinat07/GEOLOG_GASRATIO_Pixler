from __future__ import annotations

from pathlib import Path

import pytest

from geoworkbench.domain.models import CanvasObject, Project, Well
from geoworkbench.project.canvas_object_transfer_controller import (
    CanvasObjectTransferError,
)
from geoworkbench.project.canvas_object_transfer_coordinator import (
    CanvasObjectTransferCoordinator,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.session_binding import SessionBindingController
from geoworkbench.storage.project_file_safety import SaveMode


class _Saver:
    def __init__(self) -> None:
        self.project_path: Path | None = Path("project.geologpkg")
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
        assert self.project_path is not None
        return self.project_path


def _canvas(object_id: str) -> CanvasObject:
    return CanvasObject(
        object_id=object_id,
        object_type="annotation",
        anchor_type="depth",
        x=0.1,
        y=1200.0,
        width=120.0,
        height=60.0,
        properties={"text": object_id},
    )


def _session(label: str) -> ProjectSession:
    source = Well("source", f"{label} source", canvas_objects=[_canvas(f"{label}-drawing")])
    target = Well("target", f"{label} target")
    return ProjectSession(
        project=Project(
            f"{label}-project",
            label,
            wells={source.well_id: source, target.well_id: target},
        ),
        current_well_id=target.well_id,
    )


def test_canvas_transfer_coordinator_preserves_transactional_workflow() -> None:
    session = _session("first")
    saver = _Saver()
    coordinator = CanvasObjectTransferCoordinator(session, saver)

    plan = coordinator.analyze(
        "source",
        "target",
        object_ids=("first-drawing",),
    )
    outcome = coordinator.apply(plan)

    assert outcome.copied_object_ids == ("first-drawing",)
    assert [item.object_id for item in session.project.wells["target"].canvas_objects] == [
        "first-drawing"
    ]
    assert saver.modes == [SaveMode.MATERIAL_AUTOSAVE]


def test_canvas_transfer_coordinator_rebinds_and_invalidates_old_review() -> None:
    first = _session("first")
    second = _session("second")
    coordinator = CanvasObjectTransferCoordinator(first, _Saver())
    stale_plan = coordinator.analyze(
        "source",
        "target",
        object_ids=("first-drawing",),
    )
    bindings = SessionBindingController()
    bindings.register(coordinator, name="canvas_object_transfer")

    report = bindings.bind(second)

    assert report.bound_controllers == 1
    assert coordinator.session is second
    assert coordinator.available_source_wells("target")[0].name == "second source"
    with pytest.raises(CanvasObjectTransferError, match="повторно просмотрите"):
        coordinator.apply(stale_plan)
