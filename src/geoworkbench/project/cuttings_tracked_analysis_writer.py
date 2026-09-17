from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, fields

from geoworkbench.domain.localized_content import (
    SUPPORTED_CONTENT_LANGUAGES,
    bump_language_revision,
)
from geoworkbench.domain.models import CuttingsSample, Well
from geoworkbench.project.cuttings_analysis_tracking_coordinator import (
    CuttingsAnalysisTrackingCoordinator,
    CuttingsAnalysisTrackingSources,
)
from geoworkbench.project.session import ProjectSession


@dataclass(slots=True)
class CuttingsTrackedAnalysisWriter:
    """Atomically commit one staged analysis sample together with WELL-04 provenance."""

    session: ProjectSession

    def commit(
        self,
        previous_sample: CuttingsSample | None,
        staged_sample: CuttingsSample,
        *,
        sources: CuttingsAnalysisTrackingSources,
    ) -> CuttingsSample:
        """Validate provenance first, then commit model and metadata as one logical save."""
        self._validate_identity(previous_sample, staged_sample)
        coordinator = CuttingsAnalysisTrackingCoordinator(self.session)
        plan = coordinator.plan(
            previous_sample,
            staged_sample,
            lba_description_source_language=sources.lba_description,
            interpretation_source_language=sources.interpretation,
        )

        well = self._require_well()
        before = deepcopy(previous_sample) if previous_sample is not None else None
        if previous_sample is None:
            current_sample = deepcopy(staged_sample)
            well.cuttings.append(current_sample)
        else:
            current_sample = previous_sample
            self._copy_sample(current_sample, staged_sample)

        coordinator.apply(plan)
        self._bump_changed_languages(before, current_sample)
        well.content_revision += 1
        self.session.dirty = True
        return current_sample

    def resolve_and_commit(
        self,
        previous_sample: CuttingsSample | None,
        staged_sample: CuttingsSample,
        *,
        lba_description_source_language: object | None,
        interpretation_source_language: object | None,
    ) -> CuttingsSample:
        """Resolve explicit/persisted sources and atomically commit the staged sample."""
        coordinator = CuttingsAnalysisTrackingCoordinator(self.session)
        sources = coordinator.resolve_sources(
            previous_sample.sample_id if previous_sample is not None else None,
            lba_description_source_language=lba_description_source_language,
            interpretation_source_language=interpretation_source_language,
        )
        if not sources.tracked:
            raise ValueError("Для tracked-сохранения анализа укажите язык оригинала")
        return self.commit(previous_sample, staged_sample, sources=sources)

    def _require_well(self) -> Well:
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Активная скважина не выбрана")
        return well

    def _validate_identity(
        self,
        previous_sample: CuttingsSample | None,
        staged_sample: CuttingsSample,
    ) -> None:
        sample_id = staged_sample.sample_id.strip() if isinstance(staged_sample.sample_id, str) else ""
        if not sample_id:
            raise ValueError("ID пробы шлама не может быть пустым")
        if previous_sample is not None and previous_sample.sample_id != sample_id:
            raise ValueError("ID staged-пробы должен совпадать с существующей пробой")
        if previous_sample is None and any(
            item.sample_id == sample_id for item in self._require_well().cuttings
        ):
            raise ValueError(f"Проба шлама с ID {sample_id} уже существует")

    @staticmethod
    def _copy_sample(target: CuttingsSample, source: CuttingsSample) -> None:
        for model_field in fields(CuttingsSample):
            setattr(target, model_field.name, deepcopy(getattr(source, model_field.name)))

    def _bump_changed_languages(
        self,
        previous_sample: CuttingsSample | None,
        current_sample: CuttingsSample,
    ) -> None:
        well = self._require_well()
        previous_maps = (
            ({}, {})
            if previous_sample is None
            else (
                previous_sample.lba_description_i18n,
                previous_sample.analysis_interpretation_i18n,
            )
        )
        current_maps = (
            current_sample.lba_description_i18n,
            current_sample.analysis_interpretation_i18n,
        )
        for language in SUPPORTED_CONTENT_LANGUAGES:
            if any(
                previous.get(language) != current.get(language)
                for previous, current in zip(previous_maps, current_maps, strict=True)
            ):
                bump_language_revision(well.language_revisions, language)
