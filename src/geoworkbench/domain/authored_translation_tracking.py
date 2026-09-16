from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from geoworkbench.domain.localized_content import (
    SUPPORTED_CONTENT_LANGUAGES,
    normalize_content_language,
)
from geoworkbench.domain.translation_status import (
    TranslationState,
    TranslationStatus,
    TranslationStatusRegistry,
    TranslationStatusWorkflow,
)


@dataclass(frozen=True, slots=True)
class AuthoredTranslationPlan:
    """Pure WELL-04 state prepared for one authored multilingual field save."""

    translation_statuses: TranslationStatusRegistry
    authored_field_revisions: dict[str, int]
    authored_field_source_languages: dict[str, str]
    source_revision: int


class AuthoredTranslationWorkflow:
    """Plan source provenance and target-language states without mutating a project."""

    @staticmethod
    def plan(
        registry: Mapping[str, Mapping[str, TranslationStatus]],
        field_revisions: Mapping[str, int],
        source_languages: Mapping[str, str],
        *,
        field_id: str,
        previous_texts: Mapping[str, str],
        current_texts: Mapping[str, str],
        source_language: object,
        dependency_revisions: Mapping[str, int] | None = None,
    ) -> AuthoredTranslationPlan:
        normalized_field_id = AuthoredTranslationWorkflow._field_id(field_id)
        normalized_source_language = normalize_content_language(source_language)
        before_texts = AuthoredTranslationWorkflow._texts(previous_texts)
        after_texts = AuthoredTranslationWorkflow._texts(current_texts)
        if not after_texts.get(normalized_source_language):
            raise ValueError("Выбранный язык оригинала не содержит авторского текста")

        revisions = AuthoredTranslationWorkflow._revisions(field_revisions)
        source_map = AuthoredTranslationWorkflow._source_languages(source_languages)
        previous_source_language = source_map.get(normalized_field_id)
        previous_revision = revisions.get(normalized_field_id, 0)
        source_changed = (
            previous_source_language != normalized_source_language
            or before_texts.get(normalized_source_language)
            != after_texts.get(normalized_source_language)
            or previous_revision == 0
        )
        source_revision = previous_revision + 1 if source_changed else previous_revision
        revisions[normalized_field_id] = source_revision
        source_map[normalized_field_id] = normalized_source_language

        statuses = TranslationStatusWorkflow.invalidate_changed_revisions(
            registry,
            source_revisions=(
                {normalized_field_id: source_revision} if source_changed else {}
            ),
            dependency_revisions=dependency_revisions or {},
        )
        dependencies = dict(dependency_revisions or {})
        source_language_changed = (
            previous_source_language is not None
            and previous_source_language != normalized_source_language
        )

        for language in SUPPORTED_CONTENT_LANGUAGES:
            if language == normalized_source_language:
                continue
            text = after_texts.get(language)
            previous_text = before_texts.get(language)
            current_status = statuses.get(normalized_field_id, {}).get(language)
            if text:
                if (
                    current_status is None
                    or current_status.state is TranslationState.MISSING
                    or text != previous_text
                    or (source_language_changed and language == previous_source_language)
                ):
                    statuses = TranslationStatusWorkflow.begin_draft(
                        statuses,
                        field_id=normalized_field_id,
                        language=language,
                        source_language=normalized_source_language,
                        source_revision=source_revision,
                        dependency_revisions=dependencies,
                    )
            else:
                if (
                    current_status is None
                    or current_status.state is not TranslationState.MISSING
                    or current_status.source_language != normalized_source_language
                    or current_status.source_revision != source_revision
                    or current_status.dependency_revisions != dependencies
                ):
                    statuses = TranslationStatusWorkflow.mark_missing(
                        statuses,
                        field_id=normalized_field_id,
                        language=language,
                        source_language=normalized_source_language,
                        source_revision=source_revision,
                        dependency_revisions=dependencies,
                    )

        AuthoredTranslationWorkflow._set_source_marker(
            statuses,
            normalized_field_id,
            normalized_source_language,
            source_revision,
        )
        return AuthoredTranslationPlan(
            translation_statuses=statuses,
            authored_field_revisions=revisions,
            authored_field_source_languages=source_map,
            source_revision=source_revision,
        )

    @staticmethod
    def _field_id(field_id: str) -> str:
        if not isinstance(field_id, str) or not field_id.strip():
            raise ValueError("ID авторского поля не может быть пустым")
        return field_id.strip()

    @staticmethod
    def _texts(values: Mapping[str, str]) -> dict[str, str]:
        result: dict[str, str] = {}
        for raw_language, raw_text in values.items():
            language = normalize_content_language(raw_language, allow_undetermined=True)
            if not isinstance(raw_text, str):
                raise ValueError("Авторский текст должен быть строкой")
            text = raw_text.strip()
            if text:
                result[language] = text
        return result

    @staticmethod
    def _revisions(values: Mapping[str, int]) -> dict[str, int]:
        result = dict(values)
        for revision_id, revision in result.items():
            if not isinstance(revision_id, str) or not revision_id.strip():
                raise ValueError("ID ревизии авторского поля не может быть пустым")
            if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
                raise ValueError("Ревизия авторского поля должна быть неотрицательной")
        return result

    @staticmethod
    def _source_languages(values: Mapping[str, str]) -> dict[str, str]:
        result: dict[str, str] = {}
        for field_id, language in values.items():
            normalized_field_id = AuthoredTranslationWorkflow._field_id(field_id)
            result[normalized_field_id] = normalize_content_language(language)
        return result

    @staticmethod
    def _set_source_marker(
        registry: TranslationStatusRegistry,
        field_id: str,
        source_language: str,
        source_revision: int,
    ) -> None:
        """Persist explicit proof that this language is the authored source, not a translation."""

        registry.setdefault(field_id, {})[source_language] = TranslationStatus(
            state=TranslationState.REVIEWED,
            source_language=source_language,
            source_revision=source_revision,
            translation_revision=0,
            dependency_revisions={},
        )
