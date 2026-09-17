from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.domain.authored_translation_tracking import AuthoredTranslationPlan
from geoworkbench.domain.cuttings_lba_description_tracking import (
    CuttingsLbaContext,
    CuttingsLbaDescriptionTrackingWorkflow,
)
from geoworkbench.domain.models import CuttingsSample, Well
from geoworkbench.project.cuttings_analysis_interpretation_tracking import (
    CuttingsAnalysisInterpretationTrackingService,
)
from geoworkbench.project.session import ProjectSession


@dataclass(slots=True)
class CuttingsAnalysisTrackingCoordinator:
    """Compose field-scoped WELL-04 provenance for one cuttings analysis save."""

    session: ProjectSession

    def plan(
        self,
        previous_sample: CuttingsSample | None,
        current_sample: CuttingsSample,
        *,
        lba_description_source_language: object | None,
        interpretation_source_language: object | None,
    ) -> AuthoredTranslationPlan | None:
        """Build one immutable metadata plan for all tracked analysis authored fields."""
        plan: AuthoredTranslationPlan | None = None
        if lba_description_source_language is not None:
            plan = self._lba_plan(
                previous_sample,
                current_sample,
                source_language=lba_description_source_language,
            )
        if interpretation_source_language is not None:
            plan = self._interpretation_service().plan(
                previous_sample,
                current_sample,
                source_language=interpretation_source_language,
                base_plan=plan,
            )
        return plan

    def apply(self, plan: AuthoredTranslationPlan | None) -> None:
        """Commit a fully validated composed plan without partial metadata writes."""
        if plan is None:
            return
        self._interpretation_service().apply(plan)

    def lba_source_language(self, sample_id: str) -> str | None:
        sample = self._require_sample(sample_id)
        field_id = CuttingsLbaDescriptionTrackingWorkflow.field_id(sample.sample_id)
        return self._require_well().authored_field_source_languages.get(field_id)

    def interpretation_source_language(self, sample_id: str) -> str | None:
        return self._interpretation_service().source_language(sample_id)

    def clear(self, sample_id: str) -> None:
        """Remove only analysis-authored provenance for an existing cuttings sample."""
        sample = self._require_sample(sample_id)
        well = self._require_well()
        lba_field = CuttingsLbaDescriptionTrackingWorkflow.field_id(sample.sample_id)
        well.translation_statuses.pop(lba_field, None)
        well.authored_field_source_languages.pop(lba_field, None)
        for revision_id in (
            lba_field,
            CuttingsLbaDescriptionTrackingWorkflow.depth_dependency_id(sample.sample_id),
            CuttingsLbaDescriptionTrackingWorkflow.context_dependency_id(sample.sample_id),
        ):
            well.authored_field_revisions.pop(revision_id, None)
        self._interpretation_service().clear(sample.sample_id)

    def _lba_plan(
        self,
        previous_sample: CuttingsSample | None,
        current_sample: CuttingsSample,
        *,
        source_language: object,
    ) -> AuthoredTranslationPlan:
        well = self._require_well()
        return CuttingsLbaDescriptionTrackingWorkflow.plan(
            well.translation_statuses,
            well.authored_field_revisions,
            well.authored_field_source_languages,
            sample_id=current_sample.sample_id,
            previous_depth=(
                (previous_sample.top_depth, previous_sample.bottom_depth)
                if previous_sample is not None
                else None
            ),
            current_depth=(current_sample.top_depth, current_sample.bottom_depth),
            previous_context=(
                self._lba_context(previous_sample)
                if previous_sample is not None
                else None
            ),
            current_context=self._lba_context(current_sample),
            previous_texts=(
                dict(previous_sample.lba_description_i18n)
                if previous_sample is not None
                else {}
            ),
            current_texts=dict(current_sample.lba_description_i18n),
            source_language=source_language,
        )

    def _interpretation_service(self) -> CuttingsAnalysisInterpretationTrackingService:
        return CuttingsAnalysisInterpretationTrackingService(self.session)

    def _require_well(self) -> Well:
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Активная скважина не выбрана")
        return well

    def _require_sample(self, sample_id: str) -> CuttingsSample:
        normalized_sample_id = sample_id.strip() if isinstance(sample_id, str) else ""
        if not normalized_sample_id:
            raise ValueError("ID пробы шлама не может быть пустым")
        for sample in self._require_well().cuttings:
            if sample.sample_id == normalized_sample_id:
                return sample
        raise ValueError(f"Проба шлама не найдена: {normalized_sample_id}")

    @staticmethod
    def _lba_context(sample: CuttingsSample) -> CuttingsLbaContext:
        return CuttingsLbaContext(
            group=sample.lba_group,
            intensity=sample.lba_intensity,
            type_id=sample.lba_type_id,
            color=sample.lba_color,
            distribution=sample.lba_distribution,
            cut=sample.lba_cut,
            cut_speed=sample.lba_cut_speed,
            cut_color=sample.lba_cut_color,
            residue_type=sample.lba_residue_type,
            residue_color=sample.lba_residue_color,
            odour=sample.lba_odour,
            stain=sample.lba_stain,
        )
