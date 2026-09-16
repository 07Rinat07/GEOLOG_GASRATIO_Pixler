from __future__ import annotations

import pytest

from geoworkbench.domain.authored_translation_tracking import AuthoredTranslationWorkflow
from geoworkbench.domain.translation_status import TranslationState


FIELD_ID = "lithology/interval-1/description"
DEPTH_ID = "lithology/interval-1/depth"
LITHOTYPE_ID = "lithology/interval-1/lithotype"
DEPENDENCIES = {DEPTH_ID: 1, LITHOTYPE_ID: 1}


def test_new_authored_field_creates_provenance_draft_and_missing_states() -> None:
    plan = AuthoredTranslationWorkflow.plan(
        {},
        {DEPTH_ID: 1, LITHOTYPE_ID: 1},
        {},
        field_id=FIELD_ID,
        previous_texts={},
        current_texts={"ru": "Песчаник", "kk": "Құмтас"},
        source_language="ru",
        dependency_revisions=DEPENDENCIES,
    )

    assert plan.source_revision == 1
    assert plan.authored_field_revisions[FIELD_ID] == 1
    assert plan.authored_field_source_languages[FIELD_ID] == "ru"
    assert "ru" not in plan.translation_statuses[FIELD_ID]
    kk = plan.translation_statuses[FIELD_ID]["kk"]
    en = plan.translation_statuses[FIELD_ID]["en"]
    assert kk.state is TranslationState.DRAFT
    assert en.state is TranslationState.MISSING
    assert kk.source_language == "ru"
    assert kk.source_revision == 1
    assert kk.dependency_revisions == DEPENDENCIES


def test_source_change_keeps_translation_text_but_stales_existing_target() -> None:
    first = AuthoredTranslationWorkflow.plan(
        {},
        {DEPTH_ID: 1, LITHOTYPE_ID: 1},
        {},
        field_id=FIELD_ID,
        previous_texts={},
        current_texts={"ru": "Песчаник", "kk": "Құмтас"},
        source_language="ru",
        dependency_revisions=DEPENDENCIES,
    )

    second = AuthoredTranslationWorkflow.plan(
        first.translation_statuses,
        first.authored_field_revisions,
        first.authored_field_source_languages,
        field_id=FIELD_ID,
        previous_texts={"ru": "Песчаник", "kk": "Құмтас"},
        current_texts={"ru": "Песчаник серый", "kk": "Құмтас"},
        source_language="ru",
        dependency_revisions=DEPENDENCIES,
    )

    assert second.source_revision == 2
    assert second.translation_statuses[FIELD_ID]["kk"].state is TranslationState.STALE
    assert second.translation_statuses[FIELD_ID]["kk"].translation_revision == 1


def test_target_edit_restarts_draft_against_current_source_revision() -> None:
    first = AuthoredTranslationWorkflow.plan(
        {},
        {DEPTH_ID: 1, LITHOTYPE_ID: 1},
        {},
        field_id=FIELD_ID,
        previous_texts={},
        current_texts={"ru": "Песчаник", "kk": "Құмтас"},
        source_language="ru",
        dependency_revisions=DEPENDENCIES,
    )
    second = AuthoredTranslationWorkflow.plan(
        first.translation_statuses,
        first.authored_field_revisions,
        first.authored_field_source_languages,
        field_id=FIELD_ID,
        previous_texts={"ru": "Песчаник", "kk": "Құмтас"},
        current_texts={"ru": "Песчаник", "kk": "Ұсақ түйірлі құмтас"},
        source_language="ru",
        dependency_revisions=DEPENDENCIES,
    )

    status = second.translation_statuses[FIELD_ID]["kk"]
    assert second.source_revision == 1
    assert status.state is TranslationState.DRAFT
    assert status.translation_revision == 2
    assert status.source_revision == 1


def test_source_language_switch_removes_status_for_new_source() -> None:
    first = AuthoredTranslationWorkflow.plan(
        {},
        {DEPTH_ID: 1, LITHOTYPE_ID: 1},
        {},
        field_id=FIELD_ID,
        previous_texts={},
        current_texts={"ru": "Песчаник", "kk": "Құмтас", "en": "Sandstone"},
        source_language="ru",
        dependency_revisions=DEPENDENCIES,
    )

    second = AuthoredTranslationWorkflow.plan(
        first.translation_statuses,
        first.authored_field_revisions,
        first.authored_field_source_languages,
        field_id=FIELD_ID,
        previous_texts={"ru": "Песчаник", "kk": "Құмтас", "en": "Sandstone"},
        current_texts={"ru": "Песчаник", "kk": "Құмтас", "en": "Sandstone"},
        source_language="en",
        dependency_revisions=DEPENDENCIES,
    )

    assert second.source_revision == 2
    assert second.authored_field_source_languages[FIELD_ID] == "en"
    assert "en" not in second.translation_statuses[FIELD_ID]
    assert second.translation_statuses[FIELD_ID]["ru"].state is TranslationState.DRAFT


def test_source_language_requires_real_authored_text() -> None:
    with pytest.raises(ValueError, match="язык оригинала"):
        AuthoredTranslationWorkflow.plan(
            {},
            {},
            {},
            field_id=FIELD_ID,
            previous_texts={},
            current_texts={"kk": "Құмтас"},
            source_language="ru",
        )
