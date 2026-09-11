from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from geoworkbench.domain.analysis_update import AnalysisCellChange, AnalysisField, AnalysisUpdateRecord
from geoworkbench.domain.models import CuttingsSample, Well
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.well_analysis_update_controller import (
    WellAnalysisUpdateController,
    WellAnalysisUpdateOutcome,
)
from geoworkbench.services.well_analysis_update import (
    AnalysisSourceSample,
    AnalysisUpdateError,
    WellAnalysisUpdatePlan,
)
from geoworkbench.storage.project_file_safety import SaveMode


class MaterialProjectSaver(Protocol):
    """Persistence port required by the late-analysis application workflow."""

    def save_project(
        self,
        target: Path | None = None,
        *,
        mode: SaveMode = SaveMode.EXPLICIT,
        allow_existing_target: bool = False,
    ) -> Path: ...


class WellAnalysisUpdateApplication(Protocol):
    """UI-facing WELL-02 application contract."""

    def analyze(
        self,
        source_samples: tuple[AnalysisSourceSample, ...],
        *,
        selected_fields: tuple[AnalysisField, ...],
        source_name: str,
        source_sha256: str,
    ) -> WellAnalysisUpdatePlan: ...

    def apply(
        self,
        plan: WellAnalysisUpdatePlan,
        *,
        selected_changes: tuple[AnalysisCellChange, ...],
    ) -> WellAnalysisUpdateOutcome: ...

    def reset_state(self) -> None: ...


class LateAnalysisPersistenceError(AnalysisUpdateError):
    """Raised when a confirmed late-analysis update cannot be persisted safely."""


@dataclass(frozen=True, slots=True)
class _WellMutationSnapshot:
    well: Well
    cuttings: tuple[CuttingsSample, ...]
    analysis_update_history: tuple[AnalysisUpdateRecord, ...]
    content_revision: int
    session_dirty: bool

    @classmethod
    def capture(cls, session: ProjectSession) -> _WellMutationSnapshot:
        well = session.current_well
        if well is None:
            raise AnalysisUpdateError("Сначала выберите скважину")
        return cls(
            well=well,
            cuttings=tuple(well.cuttings),
            analysis_update_history=tuple(well.analysis_update_history),
            content_revision=int(well.content_revision),
            session_dirty=bool(session.dirty),
        )

    def restore(self, session: ProjectSession) -> None:
        self.well.cuttings = list(self.cuttings)
        self.well.analysis_update_history = list(self.analysis_update_history)
        self.well.content_revision = self.content_revision
        session.dirty = self.session_dirty


class WellAnalysisUpdateWorkflow:
    """Apply a reviewed WELL-02 update and persist it as one application transaction.

    The domain/controller layer remains I/O-free. This decorator owns the material
    autosave boundary and compensates the in-memory mutation if persistence fails.
    A failed save therefore leaves the well exactly at the state that preceded the
    user's confirmation and forces the next attempt through a fresh preview.
    """

    def __init__(
        self,
        session: ProjectSession,
        controller: WellAnalysisUpdateController,
        project_saver: MaterialProjectSaver,
    ) -> None:
        self._session = session
        self._controller = controller
        self._project_saver = project_saver

    def analyze(
        self,
        source_samples: tuple[AnalysisSourceSample, ...],
        *,
        selected_fields: tuple[AnalysisField, ...],
        source_name: str,
        source_sha256: str,
    ) -> WellAnalysisUpdatePlan:
        return self._controller.analyze(
            source_samples,
            selected_fields=selected_fields,
            source_name=source_name,
            source_sha256=source_sha256,
        )

    def apply(
        self,
        plan: WellAnalysisUpdatePlan,
        *,
        selected_changes: tuple[AnalysisCellChange, ...],
    ) -> WellAnalysisUpdateOutcome:
        snapshot = _WellMutationSnapshot.capture(self._session)
        try:
            outcome = self._controller.apply(plan, selected_changes=selected_changes)
        except Exception:
            snapshot.restore(self._session)
            raise

        if outcome.record is None:
            return outcome

        try:
            self._project_saver.save_project(mode=SaveMode.MATERIAL_AUTOSAVE)
        except Exception as exc:
            snapshot.restore(self._session)
            raise LateAnalysisPersistenceError(
                "Отдельные анализы не сохранены; изменения полностью отменены"
            ) from exc
        return outcome

    def reset_state(self) -> None:
        self._controller.reset_state()
