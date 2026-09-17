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
class CuttingsLbaContext:
    """LBA observations that can change the meaning of the authored description."""

    group: int | None = None
    intensity: int | None = None
    type_id: str | None = None
    color: str | None = None
    distribution: str | None = None
    cut: str | None = None
    cut_speed: str | None = None
    cut_color: str | None = None
    residue_type: str | None = None
    residue_color: str | None = None
    odour: str | None = None
    stain: str | None = None


class CuttingsLbaDescriptionTrackingWorkflow:
    """Plan WELL-04 provenance for one cuttings LBA description field."""

    @staticmethod
    def plan(
        registry: Mapping[str, Mapping[str, TranslationStatus]],
        field_revisions: Mapping[str, int],
        source_languages: Mapping[str, str],
        *,
        sample_id: str,
        previous_depth: tuple[float, float] | None,
        current_depth: tuple[float, float],
        previous_context: CuttingsLbaContext | None,
        current_context: CuttingsLbaContext,
        previous_texts: Mapping[str, str],
        current_texts: Mapping[str, str],
        source_language: object,
    ) -> AuthoredTranslationPlan:
        normalized_sample_id = CuttingsLbaDescriptionTrackingWorkflow._sample_id(sample_id)
        previous_interval = (
            CuttingsLbaDescriptionTrackingWorkflow._depth(previous_depth)
            if previous_depth is not None
            else None
        )
        current_interval = CuttingsLbaDescriptionTrackingWorkflow._depth(current_depth)
        previous_lba = (
            CuttingsLbaDescriptionTrackingWorkflow._context(previous_context)
            if previous_context is not None
            else None
        )
        current_lba = CuttingsLbaDescriptionTrackingWorkflow._context(current_context)

        revisions = dict(field_revisions)
        depth_id = CuttingsLbaDescriptionTrackingWorkflow.depth_dependency_id(
            normalized_sample_id
        )
        context_id = CuttingsLbaDescriptionTrackingWorkflow.context_dependency_id(
            normalized_sample_id
        )
        if previous_interval != current_interval or revisions.get(depth_id, 0) == 0:
            revisions[depth_id] = revisions.get(depth_id, 0) + 1
        if previous_lba != current_lba or revisions.get(context_id, 0) == 0:
            revisions[context_id] = revisions.get(context_id, 0) + 1

        return AuthoredTranslationWorkflow.plan(
            registry,
            revisions,
            source_languages,
            field_id=CuttingsLbaDescriptionTrackingWorkflow.field_id(normalized_sample_id),
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
            f"cuttings/{CuttingsLbaDescriptionTrackingWorkflow._sample_id(sample_id)}"
            "/lba_description"
        )

    @staticmethod
    def depth_dependency_id(sample_id: str) -> str:
        return f"cuttings/{CuttingsLbaDescriptionTrackingWorkflow._sample_id(sample_id)}/depth"

    @staticmethod
    def context_dependency_id(sample_id: str) -> str:
        return (
            f"cuttings/{CuttingsLbaDescriptionTrackingWorkflow._sample_id(sample_id)}"
            "/lba_context"
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
    def _context(value: CuttingsLbaContext) -> tuple[object, ...]:
        if not isinstance(value, CuttingsLbaContext):
            raise ValueError("Контекст ЛБА должен быть CuttingsLbaContext")
        return (
            CuttingsLbaDescriptionTrackingWorkflow._scale(value.group, "Группа ЛБА"),
            CuttingsLbaDescriptionTrackingWorkflow._scale(
                value.intensity, "Интенсивность ЛБА"
            ),
            CuttingsLbaDescriptionTrackingWorkflow._text(value.type_id),
            CuttingsLbaDescriptionTrackingWorkflow._text(value.color),
            CuttingsLbaDescriptionTrackingWorkflow._text(value.distribution),
            CuttingsLbaDescriptionTrackingWorkflow._text(value.cut),
            CuttingsLbaDescriptionTrackingWorkflow._text(value.cut_speed),
            CuttingsLbaDescriptionTrackingWorkflow._text(value.cut_color),
            CuttingsLbaDescriptionTrackingWorkflow._text(value.residue_type),
            CuttingsLbaDescriptionTrackingWorkflow._text(value.residue_color),
            CuttingsLbaDescriptionTrackingWorkflow._text(value.odour),
            CuttingsLbaDescriptionTrackingWorkflow._text(value.stain),
        )

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
            raise ValueError("Параметр ЛБА должен быть текстом")
        return value.strip() or None
