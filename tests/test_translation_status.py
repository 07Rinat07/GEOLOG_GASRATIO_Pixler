from __future__ import annotations

import pytest

from geoworkbench.domain.translation_status import (
    TranslationState,
    TranslationStatusError,
    TranslationStatusWorkflow,
)


FIELD_ID = "lithology/interval-1/description"


def _draft(*, language: str = "kk", source_revision: int = 3):
    return TranslationStatusWorkflow.begin_draft(
        {},
        field_id=FIELD_ID,
        language=language,
        source_language="ru",
        source_revision=source_revision,
        dependency_revisions={"interval-1/depth": 2},
    )


def test_draft_review_and_source_invalidation_are_atomic() -> None:
    empty: dict = {}
    draft = _draft()
    reviewed = TranslationStatusWorkflow.review(
        draft,
        field_id=FIELD_ID,
        language="kk",
        current_source_revision=3,
        current_dependency_revisions={"interval-1/depth": 2},
    )
    stale = TranslationStatusWorkflow.invalidate_changed_revisions(
        reviewed,
        source_revisions={FIELD_ID: 4},
        dependency_revisions={},
    )

    assert empty == {}
    assert draft[FIELD_ID]["kk"].state is TranslationState.DRAFT
    assert reviewed[FIELD_ID]["kk"].state is TranslationState.REVIEWED
    assert stale[FIELD_ID]["kk"].state is TranslationState.STALE
    assert stale[FIELD_ID]["kk"].source_revision == 3


def test_unrelated_dependency_change_keeps_reviewed_translation_current() -> None:
    reviewed = TranslationStatusWorkflow.review(
        _draft(language="en"),
        field_id=FIELD_ID,
        language="en",
        current_source_revision=3,
        current_dependency_revisions={"interval-1/depth": 2},
    )

    unchanged = TranslationStatusWorkflow.invalidate_changed_revisions(
        reviewed,
        source_revisions={"lithology/interval-2/description": 4},
        dependency_revisions={"interval-2/depth": 6},
    )

    assert unchanged[FIELD_ID]["en"].state is TranslationState.REVIEWED


def test_editing_translation_starts_new_draft_revision() -> None:
    first = _draft(source_revision=1)
    second = TranslationStatusWorkflow.begin_draft(
        first,
        field_id=FIELD_ID,
        language="kk",
        source_language="ru",
        source_revision=2,
    )

    assert second[FIELD_ID]["kk"].state is TranslationState.DRAFT
    assert second[FIELD_ID]["kk"].translation_revision == 2
    assert second[FIELD_ID]["kk"].source_revision == 2


def test_review_rejects_changed_source_language_revision_or_dependencies() -> None:
    draft = _draft(source_revision=2)

    with pytest.raises(TranslationStatusError, match="Язык исходного текста изменился"):
        TranslationStatusWorkflow.review(
            draft,
            field_id=FIELD_ID,
            language="kk",
            current_source_revision=2,
            current_source_language="en",
            current_dependency_revisions={"interval-1/depth": 2},
        )
    with pytest.raises(TranslationStatusError, match="Исходный текст изменился"):
        TranslationStatusWorkflow.review(
            draft,
            field_id=FIELD_ID,
            language="kk",
            current_source_revision=3,
            current_source_language="ru",
            current_dependency_revisions={"interval-1/depth": 2},
        )
    with pytest.raises(TranslationStatusError, match="Зависимые данные изменились"):
        TranslationStatusWorkflow.review(
            draft,
            field_id=FIELD_ID,
            language="kk",
            current_source_revision=2,
            current_source_language="ru",
            current_dependency_revisions={"interval-1/depth": 5},
        )


def test_missing_translation_cannot_be_reviewed() -> None:
    missing = TranslationStatusWorkflow.mark_missing(
        {},
        field_id=FIELD_ID,
        language="en",
        source_language="ru",
        source_revision=1,
    )

    with pytest.raises(TranslationStatusError, match="отсутствующий перевод"):
        TranslationStatusWorkflow.review(
            missing,
            field_id=FIELD_ID,
            language="en",
            current_source_revision=1,
        )
