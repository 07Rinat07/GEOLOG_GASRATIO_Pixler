from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from geoworkbench.domain.authored_translation_tracking import (
    AuthoredTranslationPlan,
    AuthoredTranslationWorkflow,
)
from geoworkbench.domain.translation_status import TranslationStatus


@dataclass(frozen=True, slots=True)
class CuttingsAnalysisContext:
    """Measured and standardized observations that support a geologist conclusion."""

    calcite_percent: float | None = None
    dolomite_percent: float | None = None
    lba_group: int | None = None
    lba_intensity: int | None = None
    lba_type_id: str | None = None
    lba_color: str | None = None
    lba_distribution: str | None = None
    lba_cut: str | None = None
    lba_cut_speed: str | None = None
    lba_cut_color: str | None = None
    lba_residue_type: str | None = None
    lba_residue_color: str | None = None
    lba_odour: str | None = None
    lba_stain: str | None = None


class CuttingsAnalysisInterpretationTrackingWorkflow:
    """Plan WELL-04 provenance for one authored cuttings analysis conclusion."""

    @staticmethod
    def plan(
        registry: Mapping[str, Mapping[str, TranslationStatus]],
        field_revisions: Mapping[str, int],
        source_languages: Mapping[str, str],
        *,
        sample_id: str,
        previous_depth: tuple[float, float] | None,
        current_depth: tuple[float, float],
        previous_context: CuttingsAnalysisContext | None,
        current_context: CuttingsAnalysisContext,
        previous_texts: Mapping[str, str],
        current_texts: Mapping[str, str],
        source_language: object,
    ) -> AuthoredTranslationPlan:
        normalized_sample_id = CuttingsAnalysisInterpretationTrackingWorkflow._sample_id(
            sample_id
        )
        previous_interval = (
            CuttingsAnalysisInterpretationTrackingWorkflow._depth(previous_depth)
            if previous_depth is not None
            else None
        )
        current_interval = CuttingsAnalysisInterpretationTrackingWorkflow._depth(
            current_depth
        )
        previous_analysis = (
            CuttingsAnalysisInterpretationTrackingWorkflow._context(previous_context)
            if previous_context is not None
            else None
        )
        current_analysis = CuttingsAnalysisInterpretationTrackingWorkflow._context(
            current_context
        )

        revisions = dict(field_revisions)
        depth_id = CuttingsAnalysisInterpretationTrackingWorkflow.depth_dependency_id(
            normalized_sample_id
        )
        context_id = CuttingsAnalysisInterpretationTrackingWorkflow.context_dependency_id(
            normalized_sample_id
        )
        if previous_interval != current_interval or revisions.get(depth_id, 0) == 0:
            revisions[depth_id] = revisions.get(depth_id, 0) + 1
        if previous_analysis != current_analysis or revisions.get(context_id, 0) == 0:
            revisions[context_id] = revisions.get(context_id, 0) + 1

        return AuthoredTranslationWorkflow.plan(
            registry,
            revisions,
            source_languages,
            field_id=CuttingsAnalysisInterpretationTrackingWorkflow.field_id(
                normalized_sample_id
            ),
            previous_texts=previous_texts,
            current_texts=current_texts,
            source_language=source_language,
            dependency_revisions={
                depth_id: revisions[depth_id],
                context_id: revisions[context_id],
            },
        )

    @staticmethod
    def field_id(sample_id: str) -> str:
        return (
            f"cuttings/{CuttingsAnalysisInterpretationTrackingWorkflow._sample_id(sample_id)}"
            "/analysis_interpretation"
        )

    @staticmethod
    def depth_dependency_id(sample_id: str) -> str:
        return (
            f"{CuttingsAnalysisInterpretationTrackingWorkflow.field_id(sample_id)}/depth"
        )

    @staticmethod
    def context_dependency_id(sample_id: str) -> str:
        return (
            f"{CuttingsAnalysisInterpretationTrackingWorkflow.field_id(sample_id)}/context"
        )

    @staticmethod
    def _sample_id(value: str) -> str:
        normalized = value.strip() if isinstance(value, str) else ""
        if not normalized:
            raise ValueError("ID пробы шлама не может быть пустым")
        return normalized

    @staticmethod
    def _depth(value: tuple[float, float]) -> tuple[float, float]:
        if not isinstance(value, tuple) or len(value) != 2:
            raise ValueError("Границы пробы шлама должны содержать кровлю и подошву")
        top, bottom = value
        if isinstance(top, bool) or isinstance(bottom, bool):
            raise ValueError("Границы пробы шлама должны быть числами")
        if not isinstance(top, (int, float)) or not isinstance(bottom, (int, float)):
            raise ValueError("Границы пробы шлама должны быть числами")
        normalized_top = float(top)
        normalized_bottom = float(bottom)
        if (
            not math.isfinite(normalized_top)
            or not math.isfinite(normalized_bottom)
            or normalized_top >= normalized_bottom
        ):
            raise ValueError("Кровля пробы шлама должна быть меньше подошвы")
        return normalized_top, normalized_bottom

    @staticmethod
    def _context(value: CuttingsAnalysisContext) -> tuple[object, ...]:
        if not isinstance(value, CuttingsAnalysisContext):
            raise ValueError("Контекст анализа должен быть CuttingsAnalysisContext")
        calcite = CuttingsAnalysisInterpretationTrackingWorkflow._percentage(
            value.calcite_percent, "Кальцит"
        )
        dolomite = CuttingsAnalysisInterpretationTrackingWorkflow._percentage(
            value.dolomite_percent, "Доломит"
        )
        if sum(item for item in (calcite, dolomite) if item is not None) > 100.01:
            raise ValueError("Сумма кальцита и доломита не должна превышать 100%")
        return (
            calcite,
            dolomite,
            CuttingsAnalysisInterpretationTrackingWorkflow._scale(
                value.lba_group, "Группа ЛБА"
            ),
            CuttingsAnalysisInterpretationTrackingWorkflow._scale(
                value.lba_intensity, "Интенсивность ЛБА"
            ),
            CuttingsAnalysisInterpretationTrackingWorkflow._text(value.lba_type_id),
            CuttingsAnalysisInterpretationTrackingWorkflow._text(value.lba_color),
            CuttingsAnalysisInterpretationTrackingWorkflow._text(value.lba_distribution),
            CuttingsAnalysisInterpretationTrackingWorkflow._text(value.lba_cut),
            CuttingsAnalysisInterpretationTrackingWorkflow._text(value.lba_cut_speed),
            CuttingsAnalysisInterpretationTrackingWorkflow._text(value.lba_cut_color),
            CuttingsAnalysisInterpretationTrackingWorkflow._text(value.lba_residue_type),
            CuttingsAnalysisInterpretationTrackingWorkflow._text(value.lba_residue_color),
            CuttingsAnalysisInterpretationTrackingWorkflow._text(value.lba_odour),
            CuttingsAnalysisInterpretationTrackingWorkflow._text(value.lba_stain),
        )

    @staticmethod
    def _percentage(value: float | None, label: str) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{label} должен быть числом")
        normalized = float(value)
        if not math.isfinite(normalized) or not 0.0 <= normalized <= 100.0:
            raise ValueError(f"{label} должен быть в диапазоне 0–100%")
        return normalized

    @staticmethod
    def _scale(value: int | None, label: str) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
            raise ValueError(f"{label} должна быть целым числом от 1 до 5")
        return value

    @staticmethod
    def _text(value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Параметр анализа должен быть текстом")
        return value.strip() or None
