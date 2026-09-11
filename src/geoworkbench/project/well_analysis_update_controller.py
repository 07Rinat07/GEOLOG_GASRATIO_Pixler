from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.domain.analysis_update import AnalysisCellChange, AnalysisField, AnalysisUpdateRecord
from geoworkbench.domain.models import Well
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.well_analysis_apply import apply_prepared_analysis_update
from geoworkbench.services.well_analysis_update import (
    AnalysisSourceSample,
    AnalysisUpdateError,
    WellAnalysisUpdatePlan,
    analyze_well_analysis_update,
    prepare_well_analysis_update,
)


@dataclass(frozen=True, slots=True)
class WellAnalysisUpdateOutcome:
    """Result of one confirmed late-analysis application."""

    plan: WellAnalysisUpdatePlan
    record: AnalysisUpdateRecord | None


class WellAnalysisUpdateController:
    """One-shot application workflow for previewing and committing late analyses.

    File and network adapters stay outside this controller. They provide immutable
    ``AnalysisSourceSample`` values and source identity. Domain validation and the
    atomic mutation of ``Well`` are delegated to the WELL-02 services; this layer
    binds a preview to the current project session and owns the dirty-state change.
    """

    def __init__(self, session: ProjectSession) -> None:
        self.session = session
        self._source_samples: tuple[AnalysisSourceSample, ...] | None = None
        self._source_name: str | None = None
        self._source_sha256: str | None = None
        self._plan: WellAnalysisUpdatePlan | None = None

    def analyze(
        self,
        source_samples: tuple[AnalysisSourceSample, ...],
        *,
        selected_fields: tuple[AnalysisField, ...],
        source_name: str,
        source_sha256: str,
    ) -> WellAnalysisUpdatePlan:
        """Create a non-mutating, one-shot preview for the current well."""

        self.reset_state()
        well = self._current_well()
        plan = analyze_well_analysis_update(
            well,
            source_samples,
            selected_fields=selected_fields,
            source_name=source_name,
            source_sha256=source_sha256,
        )
        self._source_samples = source_samples
        self._source_name = source_name
        self._source_sha256 = source_sha256
        self._plan = plan
        return plan

    def apply(
        self,
        plan: WellAnalysisUpdatePlan,
        *,
        selected_changes: tuple[AnalysisCellChange, ...],
    ) -> WellAnalysisUpdateOutcome:
        """Commit selected fill-only changes atomically, then consume the preview."""

        try:
            if (
                self._plan != plan
                or self._source_samples is None
                or self._source_name is None
                or self._source_sha256 is None
            ):
                raise AnalysisUpdateError("Сначала повторно просмотрите отдельные анализы")

            well = self._current_well()
            if well.well_id != plan.well_id:
                raise AnalysisUpdateError("Выбрана другая скважина; повторите просмотр анализов")

            prepared = prepare_well_analysis_update(
                well,
                self._source_samples,
                plan,
                source_name=self._source_name,
                source_sha256=self._source_sha256,
                selected_changes=selected_changes,
            )
            if prepared is None:
                return WellAnalysisUpdateOutcome(plan, None)

            record = apply_prepared_analysis_update(well, prepared)
            self.session.dirty = True
            return WellAnalysisUpdateOutcome(plan, record)
        finally:
            # A preview authorizes one exact source/well state only. Success,
            # failure and no-op confirmation all require a fresh next preview.
            self.reset_state()

    def reset_state(self) -> None:
        self._source_samples = None
        self._source_name = None
        self._source_sha256 = None
        self._plan = None

    def _current_well(self) -> Well:
        well = self.session.current_well
        if well is None:
            raise AnalysisUpdateError("Сначала выберите скважину")
        return well
