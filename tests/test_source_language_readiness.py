from __future__ import annotations

from geoworkbench.domain.translation_readiness import (
    TranslatableField,
    TranslationReadinessQuery,
)
from geoworkbench.domain.translation_status import TranslationState


FIELD_ID = "lithology/a/description"


def test_explicit_source_language_is_ready_without_translation_status() -> None:
    summary = TranslationReadinessQuery.summarize(
        [TranslatableField(FIELD_ID, "Описание A", 100.0, 110.0)],
        {},
        target_languages=["ru"],
        source_revisions={FIELD_ID: 3},
        source_languages={FIELD_ID: "ru"},
        include_reviewed=True,
    )

    assert summary.total_required == 1
    assert summary.reviewed_count == 1
    assert summary.missing_count == 0
    assert summary.is_ready is True
    assert summary.items[0].state is TranslationState.REVIEWED
    assert summary.items[0].status is None


def test_source_metadata_without_authored_revision_remains_missing_fail_safe() -> None:
    summary = TranslationReadinessQuery.summarize(
        [TranslatableField(FIELD_ID, "Описание A", 100.0, 110.0)],
        {},
        target_languages=["ru"],
        source_languages={FIELD_ID: "ru"},
    )

    assert summary.reviewed_count == 0
    assert summary.missing_count == 1
    assert summary.items[0].state is TranslationState.MISSING


def test_legacy_field_without_source_metadata_remains_missing_fail_safe() -> None:
    summary = TranslationReadinessQuery.summarize(
        [TranslatableField(FIELD_ID, "Описание A", 100.0, 110.0)],
        {},
        target_languages=["ru"],
        source_revisions={FIELD_ID: 3},
        source_languages={},
    )

    assert summary.total_required == 1
    assert summary.reviewed_count == 0
    assert summary.missing_count == 1
    assert summary.items[0].state is TranslationState.MISSING


def test_other_target_language_still_uses_persisted_translation_state() -> None:
    summary = TranslationReadinessQuery.summarize(
        [TranslatableField(FIELD_ID, "Описание A", 100.0, 110.0)],
        {},
        target_languages=["kk"],
        source_revisions={FIELD_ID: 1},
        source_languages={FIELD_ID: "ru"},
    )

    assert summary.reviewed_count == 0
    assert summary.missing_count == 1
    assert summary.items[0].state is TranslationState.MISSING
