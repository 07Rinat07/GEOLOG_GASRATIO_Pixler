from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from geoworkbench.data.late_analysis_adapter import (
    LateAnalysisImportResult,
    load_late_analysis_source,
)
from geoworkbench.domain.analysis_update import AnalysisCellChange, AnalysisField
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.well_analysis_update_controller import (
    WellAnalysisUpdateController,
    WellAnalysisUpdateOutcome,
)
from geoworkbench.project.well_analysis_update_workflow import (
    WellAnalysisUpdateWorkflow,
)
from geoworkbench.services.well_analysis_update import (
    AnalysisSourceSample,
    AnalysisUpdateError,
    WellAnalysisUpdatePlan,
)
from geoworkbench.storage.project_file_safety import SaveMode


LateAnalysisLoader = Callable[[str | Path], LateAnalysisImportResult]


class LateAnalysisProjectSaver(Protocol):
    """Persistence port required by the reviewed late-analysis feature."""

    def save_project(
        self,
        target: Path | None = None,
        *,
        mode: SaveMode = SaveMode.EXPLICIT,
        allow_existing_target: bool = False,
    ) -> Path: ...


@dataclass(frozen=True, slots=True)
class LateAnalysisReviewContext:
    """Immutable source/baseline captured before the modal review starts."""

    source_samples: tuple[AnalysisSourceSample, ...]
    source_name: str
    source_sha256: str
    well_id: str
    content_revision_before: int
    history_count_before: int


@dataclass(frozen=True, slots=True)
class LateAnalysisCompletion:
    changed: bool
    applied_count: int = 0


class LateAnalysisCoordinator:
    """Session-bound composition root for WELL-02 late-analysis updates."""

    def __init__(
        self,
        session: ProjectSession,
        project_saver: LateAnalysisProjectSaver,
        *,
        loader: LateAnalysisLoader = load_late_analysis_source,
    ) -> None:
        self._project_saver = project_saver
        self._loader = loader
        self._session = session
        self._controller = WellAnalysisUpdateController(session)
        self._workflow = WellAnalysisUpdateWorkflow(
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
        self._workflow = WellAnalysisUpdateWorkflow(
            session,
            self._controller,
            self._project_saver,
        )

    def prepare_review(self, source: str | Path) -> LateAnalysisReviewContext:
        well = self._session.current_well
        if well is None:
            raise AnalysisUpdateError("Сначала выберите скважину")
        imported = self._loader(source)
        return LateAnalysisReviewContext(
            source_samples=imported.source_samples,
            source_name=imported.source_name,
            source_sha256=imported.source_sha256,
            well_id=well.well_id,
            content_revision_before=well.content_revision,
            history_count_before=len(well.analysis_update_history),
        )

    def analyze(
        self,
        source_samples: tuple[AnalysisSourceSample, ...],
        *,
        selected_fields: tuple[AnalysisField, ...],
        source_name: str,
        source_sha256: str,
    ) -> WellAnalysisUpdatePlan:
        return self._workflow.analyze(
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
        return self._workflow.apply(plan, selected_changes=selected_changes)

    def reset_state(self) -> None:
        self._workflow.reset_state()

    def complete_review(
        self,
        context: LateAnalysisReviewContext,
    ) -> LateAnalysisCompletion:
        well = self._session.current_well
        if well is None or well.well_id != context.well_id:
            return LateAnalysisCompletion(False)
        changed = (
            well.content_revision > context.content_revision_before
            and len(well.analysis_update_history) > context.history_count_before
        )
        if not changed:
            return LateAnalysisCompletion(False)
        return LateAnalysisCompletion(
            True,
            len(well.analysis_update_history[-1].changes),
        )


__all__ = [
    "LateAnalysisCompletion",
    "LateAnalysisCoordinator",
    "LateAnalysisProjectSaver",
    "LateAnalysisReviewContext",
]
