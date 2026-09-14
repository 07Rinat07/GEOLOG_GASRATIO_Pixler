from __future__ import annotations

import pytest

from geoworkbench.domain.translation_readiness import (
    TranslatableField,
    TranslationReadinessError,
    TranslationReadinessQuery,
)
from geoworkbench.domain.translation_status import (
    TranslationState,
    TranslationStatusWorkflow,
)


def _registry():
    registry = TranslationStatusWorkflow.begin_draft(
        {},
        field_id="lithology/a/description",
        language="kk",
        source_language="ru",
        source_revision=2,
        dependency_revisions={"lithology/a/depth": 1},
    )
    return TranslationStatusWorkflow.review(
        registry,
        field_id="lithology/a/description",
        language="kk",
        current_source_revision=2,
        current_dependency_revisions={"lithology/a/depth": 1},
    )


def test_readiness_lists_only_incomplete_languages_in_selected_depth_range() -> None:
    fields = [
        TranslatableField("well/name", "Название скважины"),
        TranslatableField("lithology/a/description", "Описание A", 100.0, 110.0),
        TranslatableField("lithology/b/description", "Описание B", 120.0, 130.0),
    ]

    summary = TranslationReadinessQuery.summarize(
        fields,
        _registry(),
        target_languages=["kk", "en", "kk"],
        depth_range=(95.0, 115.0),
        source_revisions={"lithology/a/description": 2},
        dependency_revisions={"lithology/a/depth": 1},
    )

    assert summary.total_required == 4
    assert summary.reviewed_count == 1
    assert summary.missing_count == 3
    assert summary.draft_count == 0
    assert summary.stale_count == 0
    assert summary.is_ready is False
    assert {(item.field.field_id, item.language) for item in summary.items} == {
        ("well/name", "kk"),
        ("well/name", "en"),
        ("lithology/a/description", "en"),
    }


def test_readiness_derives_stale_without_mutating_persisted_status() -> None:
    registry = _registry()

    summary = TranslationReadinessQuery.summarize(
        [TranslatableField("lithology/a/description", "Описание A", 100.0, 110.0)],
        registry,
        target_languages=["kk"],
        source_revisions={"lithology/a/description": 3},
        dependency_revisions={"lithology/a/depth": 1},
    )

    assert summary.stale_count == 1
    assert summary.items[0].state is TranslationState.STALE
    assert registry["lithology/a/description"]["kk"].state is TranslationState.REVIEWED


def test_half_open_depth_filter_does_not_include_touching_interval() -> None:
    summary = TranslationReadinessQuery.summarize(
        [TranslatableField("lithology/a/description", "Описание A", 100.0, 110.0)],
        {},
        target_languages=["en"],
        depth_range=(110.0, 120.0),
    )

    assert summary.total_required == 0
    assert summary.items == ()
    assert summary.is_ready is False


def test_invalid_field_and_query_inputs_are_rejected() -> None:
    with pytest.raises(TranslationReadinessError, match="Границы поля"):
        TranslatableField("field", "Поле", 100.0, None)
    with pytest.raises(TranslationReadinessError, match="больше верхней"):
        TranslatableField("field", "Поле", 100.0, 100.0)
    with pytest.raises(TranslationReadinessError, match="хотя бы один язык"):
        TranslationReadinessQuery.summarize([], {}, target_languages=[])
    with pytest.raises(TranslationReadinessError, match="повторно"):
        TranslationReadinessQuery.summarize(
            [TranslatableField("same", "Один"), TranslatableField("same", "Два")],
            {},
            target_languages=["en"],
        )
