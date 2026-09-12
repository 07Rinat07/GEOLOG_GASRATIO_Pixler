from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from geoworkbench.domain.models import CanvasObject, Well
from geoworkbench.project.canvas_object_transfer_controller import (
    CanvasObjectCollisionPolicy,
    CanvasObjectTransferError,
    CanvasObjectTransferOutcome,
    CanvasObjectTransferPlan,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.storage.project_file_safety import SaveMode


class CanvasObjectTransferApplication(Protocol):
    """UI-facing contract for reviewed canvas-object transfer."""

    def available_source_wells(self, target_well_id: str) -> tuple[Well, ...]: ...

    def analyze(
        self,
        source_well_id: str,
        target_well_id: str,
        *,
        object_ids: tuple[str, ...] | None = None,
        collision_policy: CanvasObjectCollisionPolicy = CanvasObjectCollisionPolicy.ERROR,
    ) -> CanvasObjectTransferPlan: ...

    def apply(self, plan: CanvasObjectTransferPlan) -> CanvasObjectTransferOutcome: ...

    def reset_state(self) -> None: ...


class MaterialProjectSaver(Protocol):
    def save_project(
        self,
        target: Path | None = None,
        *,
        mode: SaveMode = SaveMode.EXPLICIT,
        allow_existing_target: bool = False,
    ) -> Path: ...


class CanvasObjectTransferPersistenceError(CanvasObjectTransferError):
    """Raised when a confirmed canvas transfer cannot be persisted safely."""


@dataclass(frozen=True, slots=True)
class _CanvasTransferSnapshot:
    well: Well
    objects: tuple[CanvasObject, ...]
    content_revision: int
    session_dirty: bool

    @classmethod
    def capture(
        cls,
        session: ProjectSession,
        target_well_id: str,
    ) -> _CanvasTransferSnapshot:
        try:
            well = session.project.wells[target_well_id]
        except KeyError as exc:
            raise CanvasObjectTransferError(
                f"Скважина-приёмник не найдена: {target_well_id}"
            ) from exc
        return cls(
            well=well,
            objects=tuple(well.canvas_objects),
            content_revision=well.content_revision,
            session_dirty=session.dirty,
        )

    def restore(self, session: ProjectSession) -> None:
        self.well.canvas_objects[:] = self.objects
        self.well.content_revision = self.content_revision
        session.dirty = self.session_dirty


class CanvasObjectTransferWorkflow:
    """Apply one reviewed transfer and persist it as one material transaction."""

    def __init__(
        self,
        session: ProjectSession,
        controller: CanvasObjectTransferApplication,
        project_saver: MaterialProjectSaver,
    ) -> None:
        self._session = session
        self._controller = controller
        self._project_saver = project_saver

    def available_source_wells(self, target_well_id: str) -> tuple[Well, ...]:
        return self._controller.available_source_wells(target_well_id)

    def analyze(
        self,
        source_well_id: str,
        target_well_id: str,
        *,
        object_ids: tuple[str, ...] | None = None,
        collision_policy: CanvasObjectCollisionPolicy = CanvasObjectCollisionPolicy.ERROR,
    ) -> CanvasObjectTransferPlan:
        return self._controller.analyze(
            source_well_id,
            target_well_id,
            object_ids=object_ids,
            collision_policy=collision_policy,
        )

    def apply(self, plan: CanvasObjectTransferPlan) -> CanvasObjectTransferOutcome:
        snapshot = _CanvasTransferSnapshot.capture(self._session, plan.target_well_id)
        try:
            outcome = self._controller.apply(plan)
        except Exception:
            snapshot.restore(self._session)
            raise

        if not outcome.copied_object_ids:
            return outcome

        try:
            self._project_saver.save_project(mode=SaveMode.MATERIAL_AUTOSAVE)
        except Exception as exc:
            snapshot.restore(self._session)
            raise CanvasObjectTransferPersistenceError(
                "Перенос рисунков не сохранён; изменения полностью отменены"
            ) from exc
        return outcome

    def reset_state(self) -> None:
        self._controller.reset_state()
