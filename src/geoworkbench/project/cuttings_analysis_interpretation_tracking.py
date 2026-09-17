from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.domain.authored_translation_tracking import AuthoredTranslationPlan
from geoworkbench.domain.cuttings_analysis_interpretation_tracking import (
    CuttingsAnalysisContext,
    CuttingsAnalysisInterpretationTrackingWorkflow,
)
from geoworkbench.domain.models import CuttingsSample, Well
from geoworkbench.project.session import ProjectSession


@dataclass(slots=True)
class CuttingsAnalysisInterpretationTrackingService:
    """Project-layer adapter for WELL-04 cuttings interpretation provenance."""

    session: ProjectSession

    def source_language(self, sample_id: str) -> str | None:
        sample = self._require_sample(sample_id)
        field_id = CuttingsAnalysisInterpretationTrackingWorkflow.field_id(sample.sample_id)
        return self._require_well().authored_field_source_languages.get(field_id)

    def plan(
        self,
        previous_sample: CuttingsSample | None,
        current_sample: CuttingsSample,
        *,
        source_language: object,
    ) -> AuthoredTranslationPlan:
        well = self._require_well()
        return CuttingsAnalysisInterpretationTrackingWorkflow.plan(
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
                self._analysis_context(previous_sample)
                if previous_sample is not None
                else None
            ),
            current_context=self._analysis_context(current_sample),
            previous_texts=(
                dict(previous_sample.analysis_interpretation_i18n)
                if previous_sample is not None
                else {}
            ),
            current_texts=dict(current_sample.analysis_interpretation_i18n),
            source_language=source_language,
        )

    def apply(self, plan: AuthoredTranslationPlan) -> None:
        well = self._require_well()
        well.translation_statuses = plan.translation_statuses
        well.authored_field_revisions = plan.authored_field_revisions
        well.authored_field_source_languages = plan.authored_field_source_languages

    def clear(self, sample_id: str) -> None:
        normalized_sample_id = self._require_sample(sample_id).sample_id
        well = self._require_well()
        field_id = CuttingsAnalysisInterpretationTrackingWorkflow.field_id(
            normalized_sample_id
        )
        well.translation_statuses.pop(field_id, None)
        well.authored_field_source_languages.pop(field_id, None)
        for revision_id in (
            field_id,
            CuttingsAnalysisInterpretationTrackingWorkflow.depth_dependency_id(
                normalized_sample_id
            ),
            CuttingsAnalysisInterpretationTrackingWorkflow.context_dependency_id(
                normalized_sample_id
            ),
        ):
            well.authored_field_revisions.pop(revision_id, None)

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
    def _analysis_context(sample: CuttingsSample) -> CuttingsAnalysisContext:
        return CuttingsAnalysisContext(
            calcite_percent=sample.calcite_percent,
            dolomite_percent=sample.dolomite_percent,
            lba_group=sample.lba_group,
            lba_intensity=sample.lba_intensity,
            lba_type_id=sample.lba_type_id,
            lba_color=sample.lba_color,
            lba_distribution=sample.lba_distribution,
            lba_cut=sample.lba_cut,
            lba_cut_speed=sample.lba_cut_speed,
            lba_cut_color=sample.lba_cut_color,
            lba_residue_type=sample.lba_residue_type,
            lba_residue_color=sample.lba_residue_color,
            lba_odour=sample.lba_odour,
            lba_stain=sample.lba_stain,
        )
