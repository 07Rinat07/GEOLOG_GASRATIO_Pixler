from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from geoworkbench.domain.localized_content import normalize_content_language


class TranslationState(StrEnum):
    MISSING = "missing"
    DRAFT = "draft"
    REVIEWED = "reviewed"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class TranslationStatus:
    """Persisted readiness of one language variant of one authored field."""

    state: TranslationState
    source_language: str
    source_revision: int
    translation_revision: int = 0
    dependency_revisions: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_language",
            normalize_content_language(self.source_language, allow_undetermined=True),
        )
        if (
            isinstance(self.source_revision, bool)
            or not isinstance(self.source_revision, int)
            or self.source_revision < 0
        ):
            raise ValueError("Ревизия исходного текста должна быть неотрицательной")
        if (
            isinstance(self.translation_revision, bool)
            or not isinstance(self.translation_revision, int)
            or self.translation_revision < 0
        ):
            raise ValueError("Ревизия перевода должна быть неотрицательной")
        for dependency, revision in self.dependency_revisions.items():
            if not dependency.strip():
                raise ValueError("ID зависимости перевода не может быть пустым")
            if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
                raise ValueError("Ревизия зависимости должна быть неотрицательной")


TranslationStatusRegistry = dict[str, dict[str, TranslationStatus]]


class TranslationStatusError(ValueError):
    """Raised when a translation-readiness transition is not valid."""


class TranslationStatusWorkflow:
    """Pure, atomic transitions for per-field translation readiness."""

    @staticmethod
    def begin_draft(
        registry: Mapping[str, Mapping[str, TranslationStatus]],
        *,
        field_id: str,
        language: object,
        source_language: object,
        source_revision: int,
        dependency_revisions: Mapping[str, int] | None = None,
    ) -> TranslationStatusRegistry:
        normalized_field_id = TranslationStatusWorkflow._field_id(field_id)
        language_code = normalize_content_language(language)
        previous = registry.get(normalized_field_id, {}).get(language_code)
        status = TranslationStatus(
            state=TranslationState.DRAFT,
            source_language=normalize_content_language(source_language, allow_undetermined=True),
            source_revision=source_revision,
            translation_revision=(previous.translation_revision if previous else 0) + 1,
            dependency_revisions=TranslationStatusWorkflow._dependencies(dependency_revisions),
        )
        return TranslationStatusWorkflow._replace(
            registry, normalized_field_id, language_code, status
        )

    @staticmethod
    def mark_missing(
        registry: Mapping[str, Mapping[str, TranslationStatus]],
        *,
        field_id: str,
        language: object,
        source_language: object,
        source_revision: int,
        dependency_revisions: Mapping[str, int] | None = None,
    ) -> TranslationStatusRegistry:
        normalized_field_id = TranslationStatusWorkflow._field_id(field_id)
        language_code = normalize_content_language(language)
        previous = registry.get(normalized_field_id, {}).get(language_code)
        status = TranslationStatus(
            state=TranslationState.MISSING,
            source_language=normalize_content_language(source_language, allow_undetermined=True),
            source_revision=source_revision,
            translation_revision=previous.translation_revision if previous else 0,
            dependency_revisions=TranslationStatusWorkflow._dependencies(dependency_revisions),
        )
        return TranslationStatusWorkflow._replace(
            registry, normalized_field_id, language_code, status
        )

    @staticmethod
    def review(
        registry: Mapping[str, Mapping[str, TranslationStatus]],
        *,
        field_id: str,
        language: object,
        current_source_revision: int,
        current_dependency_revisions: Mapping[str, int] | None = None,
    ) -> TranslationStatusRegistry:
        normalized_field_id = TranslationStatusWorkflow._field_id(field_id)
        language_code = normalize_content_language(language)
        current = registry.get(normalized_field_id, {}).get(language_code)
        if current is None or current.state is TranslationState.MISSING:
            raise TranslationStatusError("Нельзя проверить отсутствующий перевод")
        dependencies = TranslationStatusWorkflow._dependencies(current_dependency_revisions)
        validated_source_revision = TranslationStatusWorkflow._revision(
            current_source_revision, "исходного текста"
        )
        if current.source_revision != validated_source_revision:
            raise TranslationStatusError("Исходный текст изменился; перевод требует обновления")
        if current.dependency_revisions != dependencies:
            raise TranslationStatusError("Зависимые данные изменились; перевод требует обновления")
        reviewed = TranslationStatus(
            state=TranslationState.REVIEWED,
            source_language=current.source_language,
            source_revision=current.source_revision,
            translation_revision=current.translation_revision,
            dependency_revisions=current.dependency_revisions,
        )
        return TranslationStatusWorkflow._replace(
            registry, normalized_field_id, language_code, reviewed
        )

    @staticmethod
    def invalidate_changed_revisions(
        registry: Mapping[str, Mapping[str, TranslationStatus]],
        *,
        source_revisions: Mapping[str, int],
        dependency_revisions: Mapping[str, int],
    ) -> TranslationStatusRegistry:
        sources = TranslationStatusWorkflow._dependencies(source_revisions)
        dependencies = TranslationStatusWorkflow._dependencies(dependency_revisions)
        result = TranslationStatusWorkflow._copy(registry)
        for field_id, languages in result.items():
            for language, current in tuple(languages.items()):
                source_revision = sources.get(field_id)
                source_changed = (
                    source_revision is not None and source_revision != current.source_revision
                )
                dependency_changed = any(
                    dependency in dependencies and dependencies[dependency] != revision
                    for dependency, revision in current.dependency_revisions.items()
                )
                if (source_changed or dependency_changed) and current.state in {
                    TranslationState.DRAFT,
                    TranslationState.REVIEWED,
                }:
                    languages[language] = TranslationStatus(
                        state=TranslationState.STALE,
                        source_language=current.source_language,
                        source_revision=current.source_revision,
                        translation_revision=current.translation_revision,
                        dependency_revisions=current.dependency_revisions,
                    )
        return result

    @staticmethod
    def _field_id(field_id: str) -> str:
        if not isinstance(field_id, str) or not field_id.strip():
            raise TranslationStatusError("ID переводимого поля не может быть пустым")
        return field_id.strip()

    @staticmethod
    def _dependencies(values: Mapping[str, int] | None) -> dict[str, int]:
        normalized = dict(values or {})
        for dependency, revision in normalized.items():
            if not isinstance(dependency, str) or not dependency.strip():
                raise TranslationStatusError("ID зависимости не может быть пустым")
            if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
                raise TranslationStatusError("Ревизия зависимости должна быть неотрицательной")
        return normalized

    @staticmethod
    def _revision(value: int, label: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise TranslationStatusError(f"Ревизия {label} должна быть неотрицательной")
        return value

    @staticmethod
    def _copy(
        registry: Mapping[str, Mapping[str, TranslationStatus]],
    ) -> TranslationStatusRegistry:
        return {field_id: dict(languages) for field_id, languages in registry.items()}

    @staticmethod
    def _replace(
        registry: Mapping[str, Mapping[str, TranslationStatus]],
        field_id: str,
        language: str,
        status: TranslationStatus,
    ) -> TranslationStatusRegistry:
        result = TranslationStatusWorkflow._copy(registry)
        result.setdefault(field_id, {})[language] = status
        return result
