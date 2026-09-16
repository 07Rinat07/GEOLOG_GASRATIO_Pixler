from __future__ import annotations

from geoworkbench.domain.translation_readiness import (
    TranslatableField,
    TranslationReadinessQuery,
)
from geoworkbench.domain.translation_status import (
    TranslationState,
    TranslationStatus,
)


FIELD_ID = "lithology/a/description"


def _source_marker(*, language: str = "ru", source_revision: int = 3) -> dict[str, dict[str, TranslationStatus]]:
    return {
        FIELD_ID: {
            language: TranslationStatus(
                state=TranslationState.REVIEWED,
                source_language=language,
                source_revision=source_revision,
                translation_revision=0,
            )
        }
    }


def test_persisted_source_marker_is_ready() -> None:
    registry = _source_marker()
    summary = TranslationReadinessQuery.summarize(
        [TranslatableField(FIELD_ID, "Описание A", 100.0, 110.0)],
        registry,
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
    assert summary.items[0].status is registry[FIELD_ID]["ru"]
    assert summary.items[0].status.translation_revision == 0


def test_source_metadata_without_persisted_marker_remains_missing_fail_safe() -> None:
    summary = TranslationReadinessQuery.summarize(
        [TranslatableField(FIELD_ID, "Описание A", 100.0, 110.0)],
        {},
        target_languages=["ru"],
        source_revisions={FIELD_ID: 3},
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


def test_other_target_language_still_requires_its_own_translation_status() -> None:
    summary = TranslationReadinessQuery.summarize(
        [TranslatableField(FIELD_ID, "Описание A", 100.0, 110.0)],
        _source_marker(source_revision=1),
        target_languages=["kk"],
        source_revisions={FIELD_ID: 1},
        source_languages={FIELD_ID: "ru"},
    )

    assert summary.reviewed_count == 0
    assert summary.missing_count == 1
    assert summary.items[0].state is TranslationState.MISSING


def test_source_marker_becomes_stale_if_revision_changes_out_of_band() -> None:
    summary = TranslationReadinessQuery.summarize(
        [TranslatableField(FIELD_ID, "Описание A", 100.0, 110.0)],
        _source_marker(source_revision=2),
        target_languages=["ru"],
        source_revisions={FIELD_ID: 3},
        source_languages={FIELD_ID: "ru"},
        include_reviewed=True,
    )

    assert summary.reviewed_count == 0
    assert summary.stale_count == 1
    assert summary.items[0].state is TranslationState.STALE
