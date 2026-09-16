from __future__ import annotations

import math
from collections.abc import Mapping

from geoworkbench.domain.authored_translation_tracking import (
    AuthoredTranslationPlan,
    AuthoredTranslationWorkflow,
)
from geoworkbench.domain.translation_status import TranslationStatus


class StratigraphyDescriptionTrackingWorkflow:
    """Plan WELL-04 provenance for one stratigraphic description field."""

    @staticmethod
    def plan(
        registry: Mapping[str, Mapping[str, TranslationStatus]],
        field_revisions: Mapping[str, int],
        source_languages: Mapping[str, str],
        *,
        interval_id: str,
        previous_depth: tuple[float, float] | None,
        current_depth: tuple[float, float],
        previous_classification: tuple[str, str | None] | None,
        current_classification: tuple[str, str | None],
        previous_texts: Mapping[str, str],
        current_texts: Mapping[str, str],
        source_language: object,
    ) -> AuthoredTranslationPlan:
        normalized_interval_id = StratigraphyDescriptionTrackingWorkflow._interval_id(interval_id)
        previous_interval = (
            StratigraphyDescriptionTrackingWorkflow._depth(previous_depth)
            if previous_depth is not None
            else None
        )
        current_interval = StratigraphyDescriptionTrackingWorkflow._depth(current_depth)
        previous_identity = (
            StratigraphyDescriptionTrackingWorkflow._classification(previous_classification)
            if previous_classification is not None
            else None
        )
        current_identity = StratigraphyDescriptionTrackingWorkflow._classification(
            current_classification
        )

        revisions = dict(field_revisions)
        depth_id = StratigraphyDescriptionTrackingWorkflow.depth_dependency_id(
            normalized_interval_id
        )
        classification_id = StratigraphyDescriptionTrackingWorkflow.classification_dependency_id(
            normalized_interval_id
        )
        if previous_interval != current_interval or revisions.get(depth_id, 0) == 0:
            revisions[depth_id] = revisions.get(depth_id, 0) + 1
        if previous_identity != current_identity or revisions.get(classification_id, 0) == 0:
            revisions[classification_id] = revisions.get(classification_id, 0) + 1

        return AuthoredTranslationWorkflow.plan(
            registry,
            revisions,
            source_languages,
            field_id=StratigraphyDescriptionTrackingWorkflow.field_id(normalized_interval_id),
            previous_texts=previous_texts,
            current_texts=current_texts,
            source_language=source_language,
            dependency_revisions={
                depth_id: revisions[depth_id],
                classification_id: revisions[classification_id],
            },
        )

    @staticmethod
    def field_id(interval_id: str) -> str:
        return (
            f"stratigraphy/{StratigraphyDescriptionTrackingWorkflow._interval_id(interval_id)}"
            "/description"
        )

    @staticmethod
    def depth_dependency_id(interval_id: str) -> str:
        return (
            f"stratigraphy/{StratigraphyDescriptionTrackingWorkflow._interval_id(interval_id)}"
            "/depth"
        )

    @staticmethod
    def classification_dependency_id(interval_id: str) -> str:
        return (
            f"stratigraphy/{StratigraphyDescriptionTrackingWorkflow._interval_id(interval_id)}"
            "/classification"
        )

    @staticmethod
    def _interval_id(value: str) -> str:
        normalized = value.strip() if isinstance(value, str) else ""
        if not normalized:
            raise ValueError("ID стратиграфического интервала не может быть пустым")
        return normalized

    @staticmethod
    def _depth(value: tuple[float, float]) -> tuple[float, float]:
        if not isinstance(value, tuple) or len(value) != 2:
            raise ValueError("Границы стратиграфического интервала должны содержать кровлю и подошву")
        top, bottom = value
        if isinstance(top, bool) or isinstance(bottom, bool):
            raise ValueError("Границы стратиграфического интервала должны быть числами")
        if not isinstance(top, (int, float)) or not isinstance(bottom, (int, float)):
            raise ValueError("Границы стратиграфического интервала должны быть числами")
        normalized_top = float(top)
        normalized_bottom = float(bottom)
        if (
            not math.isfinite(normalized_top)
            or not math.isfinite(normalized_bottom)
            or normalized_top >= normalized_bottom
        ):
            raise ValueError("Кровля стратиграфического интервала должна быть меньше подошвы")
        return normalized_top, normalized_bottom

    @staticmethod
    def _classification(value: tuple[str, str | None]) -> tuple[str, str | None]:
        if not isinstance(value, tuple) or len(value) != 2:
            raise ValueError("Классификация должна содержать код и ранг интервала")
        raw_code, raw_rank = value
        code = raw_code.strip() if isinstance(raw_code, str) else ""
        if not code:
            raise ValueError("Код стратиграфического интервала не может быть пустым")
        if len(code) > 100:
            raise ValueError("Код стратиграфического интервала не должен превышать 100 символов")
        if raw_rank is not None and not isinstance(raw_rank, str):
            raise ValueError("Ранг стратиграфического интервала должен быть строкой")
        rank = raw_rank.strip() if isinstance(raw_rank, str) and raw_rank.strip() else None
        if rank is not None and len(rank) > 100:
            raise ValueError("Ранг стратиграфического интервала не должен превышать 100 символов")
        return code, rank
