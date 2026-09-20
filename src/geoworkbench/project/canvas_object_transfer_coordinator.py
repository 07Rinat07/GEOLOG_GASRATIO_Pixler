from __future__ import annotations

from pathlib import Path
from typing import Protocol

from geoworkbench.domain.models import Well
from geoworkbench.project.canvas_object_transfer_controller import (
    CanvasObjectCollisionPolicy,
    CanvasObjectTransferController,
    CanvasObjectTransferOutcome,
    CanvasObjectTransferPlan,
)
from geoworkbench.project.canvas_object_transfer_workflow import (
    CanvasObjectTransferWorkflow,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.storage.project_file_safety import SaveMode


class CanvasObjectTransferProjectSaver(Protocol):
    """Persistence port required by the canvas-object transfer feature."""

    project_path: Path | None

    def save_project(
        self,
        target: Path | None = None,
        *,
        mode: SaveMode = SaveMode.EXPLICIT,
        allow_existing_target: bool = False,
    ) -> Path: ...


class CanvasObjectTransferCoordinator:
    """Session-bound composition root for reviewed canvas-object transfer.

    Qt only selects a target well and renders the review dialog. The controller,
    transactional workflow and material autosave boundary remain behind this
    coordinator and are rebound together whenever the active project changes.
    """

    def __init__(
        self,
        session: ProjectSession,
        project_saver: CanvasObjectTransferProjectSaver,
    ) -> None:
        self._project_saver = project_saver
        self._session = session
        self._controller = CanvasObjectTransferController(session)
        self._workflow = CanvasObjectTransferWorkflow(
            session,
            self._controller,
            project_saver,
        )

    @property
    def session(self) -> ProjectSession:
        return self._session

    @session.setter
    def session(self, session: ProjectSession) -> None:
        if not isinstance(session, ProjectSession):
            raise TypeError("Ожидалась сессия проекта")
        self._session = session
        self._controller.session = session
        self._controller.reset_state()
        self._workflow = CanvasObjectTransferWorkflow(
            session,
            self._controller,
            self._project_saver,
        )

    def available_source_wells(self, target_well_id: str) -> tuple[Well, ...]:
        return self._workflow.available_source_wells(target_well_id)

    def analyze(
        self,
        source_well_id: str,
        target_well_id: str,
        *,
        object_ids: tuple[str, ...] | None = None,
        collision_policy: CanvasObjectCollisionPolicy = CanvasObjectCollisionPolicy.ERROR,
    ) -> CanvasObjectTransferPlan:
        return self._workflow.analyze(
            source_well_id,
            target_well_id,
            object_ids=object_ids,
            collision_policy=collision_policy,
        )

    def apply(self, plan: CanvasObjectTransferPlan) -> CanvasObjectTransferOutcome:
        return self._workflow.apply(plan)

    def reset_state(self) -> None:
        self._workflow.reset_state()


__all__ = [
    "CanvasObjectTransferCoordinator",
    "CanvasObjectTransferProjectSaver",
]
