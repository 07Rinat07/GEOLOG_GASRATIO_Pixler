from __future__ import annotations

import math
from collections.abc import Mapping

from geoworkbench.domain.authored_translation_tracking import (
    AuthoredTranslationPlan,
    AuthoredTranslationWorkflow,
)
from geoworkbench.domain.translation_status import TranslationStatus


class CuttingsDescriptionTrackingWorkflow:
    """Plan WELL-04 provenance for one cuttings rich-description field."""

    @staticmethod
    def plan(
        registry: Mapping[str, Mapping[str, TranslationStatus]],
        field_revisions: Mapping[str, int],
        source_languages: Mapping[str, str],
        *,
        sample_id: str,
        previous_depth: tuple[float, float] | None,
        current_depth: tuple[float, float],
        previous_components: Mapping[str, float] | None,
        current_components: Mapping[str, float],
        previous_texts: Mapping[str, str],
        current_texts: Mapping[str, str],
        source_language: object,
    ) -> AuthoredTranslationPlan:
        normalized_sample_id = CuttingsDescriptionTrackingWorkflow._sample_id(sample_id)
        previous_interval = (
            CuttingsDescriptionTrackingWorkflow._depth(previous_depth)
            if previous_depth is not None
            else None
        )
        current_interval = CuttingsDescriptionTrackingWorkflow._depth(current_depth)
        previous_composition = (
            CuttingsDescriptionTrackingWorkflow._components(previous_components)
            if previous_components is not None
            else None
        )
        current_composition = CuttingsDescriptionTrackingWorkflow._components(current_components)

        revisions = dict(field_revisions)
        depth_id = CuttingsDescriptionTrackingWorkflow.depth_dependency_id(normalized_sample_id)
        composition_id = CuttingsDescriptionTrackingWorkflow.composition_dependency_id(
            normalized_sample_id
        )
        if previous_interval != current_interval or revisions.get(depth_id, 0) == 0:
            revisions[depth_id] = revisions.get(depth_id, 0) + 1
        if previous_composition != current_composition or revisions.get(composition_id, 0) == 0:
            revisions[composition_id] = revisions.get(composition_id, 0) + 1

        return AuthoredTranslationWorkflow.plan(
            registry,
            revisions,
            source_languages,
            field_id=CuttingsDescriptionTrackingWorkflow.field_id(normalized_sample_id),
            previous_texts=previous_texts,
            current_texts=current_texts,
            source_language=source_language,
            dependency_revisions={
                depth_id: revisions[depth_id],
                composition_id: revisions[composition_id],
            },
        )

    @staticmethod
    def field_id(sample_id: str) -> str:
        return f"cuttings/{CuttingsDescriptionTrackingWorkflow._sample_id(sample_id)}/description"

    @staticmethod
    def depth_dependency_id(sample_id: str) -> str:
        return f"cuttings/{CuttingsDescriptionTrackingWorkflow._sample_id(sample_id)}/depth"

    @staticmethod
    def composition_dependency_id(sample_id: str) -> str:
        return f"cuttings/{CuttingsDescriptionTrackingWorkflow._sample_id(sample_id)}/composition"

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
    def _components(values: Mapping[str, float]) -> tuple[tuple[str, float], ...]:
        if not isinstance(values, Mapping):
            raise ValueError("Состав шлама должен быть отображением литотипов и долей")
        normalized: list[tuple[str, float]] = []
        for raw_lithotype_id, raw_percentage in values.items():
            lithotype_id = raw_lithotype_id.strip() if isinstance(raw_lithotype_id, str) else ""
            if not lithotype_id:
                raise ValueError("ID компонента шлама не может быть пустым")
            if isinstance(raw_percentage, bool) or not isinstance(raw_percentage, (int, float)):
                raise ValueError("Доля компонента шлама должна быть числом")
            percentage = float(raw_percentage)
            if not math.isfinite(percentage) or percentage < 0.0 or percentage > 100.0:
                raise ValueError("Доля компонента шлама должна быть в диапазоне 0–100%")
            if percentage > 0.0:
                normalized.append((lithotype_id, percentage))
        return tuple(sorted(normalized))
