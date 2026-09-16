from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from geoworkbench.domain.localized_content import normalize_content_language
from geoworkbench.domain.translation_status import (
    TranslationState,
    TranslationStatus,
)


class TranslationReadinessError(ValueError):
    """Raised when a translation-readiness query is ambiguous or invalid."""


@dataclass(frozen=True, slots=True)
class TranslatableField:
    """One authored field and its optional half-open MD interval."""

    field_id: str
    label: str
    top_depth: float | None = None
    bottom_depth: float | None = None

    def __post_init__(self) -> None:
        normalized_field_id = self.field_id.strip() if isinstance(self.field_id, str) else ""
        if not normalized_field_id:
            raise TranslationReadinessError("ID переводимого поля не может быть пустым")
        normalized_label = self.label.strip() if isinstance(self.label, str) else ""
        if not normalized_label:
            raise TranslationReadinessError("Название переводимого поля не может быть пустым")
        object.__setattr__(self, "field_id", normalized_field_id)
        object.__setattr__(self, "label", normalized_label)
        if (self.top_depth is None) != (self.bottom_depth is None):
            raise TranslationReadinessError("Границы поля должны быть заданы вместе")
        if self.top_depth is None:
            return
        top = _finite_depth(self.top_depth, "верхняя")
        bottom = _finite_depth(self.bottom_depth, "нижняя")
        if bottom <= top:
            raise TranslationReadinessError("Нижняя граница поля должна быть больше верхней")
        object.__setattr__(self, "top_depth", top)
        object.__setattr__(self, "bottom_depth", bottom)


@dataclass(frozen=True, slots=True)
class TranslationReadinessItem:
    field: TranslatableField
    language: str
    state: TranslationState
    status: TranslationStatus | None


@dataclass(frozen=True, slots=True)
class TranslationReadinessSummary:
    items: tuple[TranslationReadinessItem, ...]
    total_required: int
    reviewed_count: int
    missing_count: int
    draft_count: int
    stale_count: int

    @property
    def is_ready(self) -> bool:
        return self.total_required > 0 and self.reviewed_count == self.total_required


class TranslationReadinessQuery:
    """Pure range-aware projection over persisted per-field translation states."""

    @staticmethod
    def summarize(
        fields: Iterable[TranslatableField],
        registry: Mapping[str, Mapping[str, TranslationStatus]],
        *,
        target_languages: Sequence[object],
        depth_range: tuple[float, float] | None = None,
        source_revisions: Mapping[str, int] | None = None,
        dependency_revisions: Mapping[str, int] | None = None,
        source_languages: Mapping[str, object] | None = None,
        include_reviewed: bool = False,
    ) -> TranslationReadinessSummary:
        normalized_languages = _languages(target_languages)
        normalized_range = _depth_range(depth_range)
        normalized_fields = tuple(fields)
        _ensure_unique_fields(normalized_fields)
        current_sources = _revisions(source_revisions, "исходного поля")
        current_dependencies = _revisions(dependency_revisions, "зависимости")
        current_source_languages = _source_languages(source_languages)

        all_items: list[TranslationReadinessItem] = []
        for field in normalized_fields:
            if not _intersects(field, normalized_range):
                continue
            statuses = registry.get(field.field_id, {})
            for language in normalized_languages:
                status = statuses.get(language)
                state = _effective_state(
                    field.field_id,
                    language,
                    status,
                    source_revisions=current_sources,
                    dependency_revisions=current_dependencies,
                    source_languages=current_source_languages,
                )
                all_items.append(
                    TranslationReadinessItem(
                        field=field,
                        language=language,
                        state=state,
                        status=status,
                    )
                )

        counts = Counter(item.state for item in all_items)
        visible = tuple(
            item
            for item in all_items
            if include_reviewed or item.state is not TranslationState.REVIEWED
        )
        return TranslationReadinessSummary(
            items=visible,
            total_required=len(all_items),
            reviewed_count=counts[TranslationState.REVIEWED],
            missing_count=counts[TranslationState.MISSING],
            draft_count=counts[TranslationState.DRAFT],
            stale_count=counts[TranslationState.STALE],
        )


def _finite_depth(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TranslationReadinessError(f"{label.capitalize()} граница должна быть числом")
    result = float(value)
    if not math.isfinite(result):
        raise TranslationReadinessError(f"{label.capitalize()} граница должна быть конечной")
    return result


def _depth_range(value: tuple[float, float] | None) -> tuple[float, float] | None:
    if value is None:
        return None
    if not isinstance(value, tuple) or len(value) != 2:
        raise TranslationReadinessError("Диапазон должен содержать две границы")
    top = _finite_depth(value[0], "верхняя")
    bottom = _finite_depth(value[1], "нижняя")
    if bottom <= top:
        raise TranslationReadinessError("Конец диапазона должен быть больше начала")
    return top, bottom


def _languages(values: Sequence[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        language = normalize_content_language(value)
        if language not in result:
            result.append(language)
    if not result:
        raise TranslationReadinessError("Нужно выбрать хотя бы один язык перевода")
    return tuple(result)


def _revisions(values: Mapping[str, int] | None, label: str) -> dict[str, int]:
    result = dict(values or {})
    for revision_id, revision in result.items():
        if not isinstance(revision_id, str) or not revision_id.strip():
            raise TranslationReadinessError(f"ID {label} не может быть пустым")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            raise TranslationReadinessError(f"Ревизия {label} должна быть неотрицательной")
    return result


def _source_languages(values: Mapping[str, object] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for field_id, language in (values or {}).items():
        if not isinstance(field_id, str) or not field_id.strip():
            raise TranslationReadinessError("ID исходного поля не может быть пустым")
        try:
            result[field_id.strip()] = normalize_content_language(language)
        except ValueError as exc:
            raise TranslationReadinessError(str(exc)) from exc
    return result


def _ensure_unique_fields(fields: tuple[TranslatableField, ...]) -> None:
    seen: set[str] = set()
    for field in fields:
        if field.field_id in seen:
            raise TranslationReadinessError(f"Поле {field.field_id!r} указано повторно")
        seen.add(field.field_id)


def _intersects(
    field: TranslatableField,
    selected_range: tuple[float, float] | None,
) -> bool:
    if selected_range is None or field.top_depth is None or field.bottom_depth is None:
        return True
    top, bottom = selected_range
    return field.top_depth < bottom and field.bottom_depth > top


def _effective_state(
    field_id: str,
    language: str,
    status: TranslationStatus | None,
    *,
    source_revisions: Mapping[str, int],
    dependency_revisions: Mapping[str, int],
    source_languages: Mapping[str, str],
) -> TranslationState:
    current_source_language = source_languages.get(field_id)
    if current_source_language == language:
        return TranslationState.REVIEWED
    if status is None:
        return TranslationState.MISSING
    source_changed = (
        field_id in source_revisions and source_revisions[field_id] != status.source_revision
    )
    source_language_changed = (
        current_source_language is not None and current_source_language != status.source_language
    )
    dependency_changed = any(
        dependency in dependency_revisions and dependency_revisions[dependency] != revision
        for dependency, revision in status.dependency_revisions.items()
    )
    if (source_changed or source_language_changed or dependency_changed) and status.state in {
        TranslationState.DRAFT,
        TranslationState.REVIEWED,
    }:
        return TranslationState.STALE
    return status.state
