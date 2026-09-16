from __future__ import annotations

import pytest

from geoworkbench.domain.stratigraphy_description_tracking import (
    StratigraphyDescriptionTrackingWorkflow,
)
from geoworkbench.domain.translation_status import TranslationState


INTERVAL_ID = "strat-1"
FIELD_ID = f"stratigraphy/{INTERVAL_ID}/description"
DEPTH_ID = f"stratigraphy/{INTERVAL_ID}/depth"
CLASSIFICATION_ID = f"stratigraphy/{INTERVAL_ID}/classification"


def _new_plan():
    return StratigraphyDescriptionTrackingWorkflow.plan(
        {},
        {},
        {},
        interval_id=INTERVAL_ID,
        previous_depth=None,
        current_depth=(100.0, 120.0),
        previous_classification=None,
        current_classification=("K1", "Formation"),
        previous_texts={},
        current_texts={"ru": "Меловые отложения", "kk": "Бор шөгінділері"},
        source_language="ru",
    )


def test_new_stratigraphy_description_tracks_source_and_context() -> None:
    plan = _new_plan()

    assert plan.authored_field_revisions[FIELD_ID] == 1
    assert plan.authored_field_revisions[DEPTH_ID] == 1
    assert plan.authored_field_revisions[CLASSIFICATION_ID] == 1
    assert plan.authored_field_source_languages[FIELD_ID] == "ru"
    source = plan.translation_statuses[FIELD_ID]["ru"]
    target = plan.translation_statuses[FIELD_ID]["kk"]
    missing = plan.translation_statuses[FIELD_ID]["en"]
    assert source.state is TranslationState.REVIEWED
    assert target.state is TranslationState.DRAFT
    assert target.dependency_revisions == {
        DEPTH_ID: 1,
        CLASSIFICATION_ID: 1,
    }
    assert missing.state is TranslationState.MISSING


def test_depth_change_stales_translation_without_bumping_source_revision() -> None:
    first = _new_plan()
    second = StratigraphyDescriptionTrackingWorkflow.plan(
        first.translation_statuses,
        first.authored_field_revisions,
        first.authored_field_source_languages,
        interval_id=INTERVAL_ID,
        previous_depth=(100.0, 120.0),
        current_depth=(101.0, 120.0),
        previous_classification=("K1", "Formation"),
        current_classification=("K1", "Formation"),
        previous_texts={"ru": "Меловые отложения", "kk": "Бор шөгінділері"},
        current_texts={"ru": "Меловые отложения", "kk": "Бор шөгінділері"},
        source_language="ru",
    )

    assert second.authored_field_revisions[FIELD_ID] == 1
    assert second.authored_field_revisions[DEPTH_ID] == 2
    assert second.authored_field_revisions[CLASSIFICATION_ID] == 1
    assert second.translation_statuses[FIELD_ID]["kk"].state is TranslationState.STALE


def test_classification_change_stales_translation_without_false_depth_revision() -> None:
    first = _new_plan()
    second = StratigraphyDescriptionTrackingWorkflow.plan(
        first.translation_statuses,
        first.authored_field_revisions,
        first.authored_field_source_languages,
        interval_id=INTERVAL_ID,
        previous_depth=(100.0, 120.0),
        current_depth=(100.0, 120.0),
        previous_classification=("K1", "Formation"),
        current_classification=("K2", "Formation"),
        previous_texts={"ru": "Меловые отложения", "kk": "Бор шөгінділері"},
        current_texts={"ru": "Меловые отложения", "kk": "Бор шөгінділері"},
        source_language="ru",
    )

    assert second.authored_field_revisions[FIELD_ID] == 1
    assert second.authored_field_revisions[DEPTH_ID] == 1
    assert second.authored_field_revisions[CLASSIFICATION_ID] == 2
    assert second.translation_statuses[FIELD_ID]["kk"].state is TranslationState.STALE


def test_unchanged_context_does_not_bump_dependency_revisions() -> None:
    first = _new_plan()
    second = StratigraphyDescriptionTrackingWorkflow.plan(
        first.translation_statuses,
        first.authored_field_revisions,
        first.authored_field_source_languages,
        interval_id=INTERVAL_ID,
        previous_depth=(100.0, 120.0),
        current_depth=(100.0, 120.0),
        previous_classification=("K1", "Formation"),
        current_classification=("K1", "Formation"),
        previous_texts={"ru": "Меловые отложения", "kk": "Бор шөгінділері"},
        current_texts={"ru": "Меловые отложения", "kk": "Бор шөгінділері"},
        source_language="ru",
    )

    assert second.authored_field_revisions[FIELD_ID] == 1
    assert second.authored_field_revisions[DEPTH_ID] == 1
    assert second.authored_field_revisions[CLASSIFICATION_ID] == 1
    assert second.translation_statuses[FIELD_ID]["kk"].state is TranslationState.DRAFT


def test_target_edit_advances_only_translation_revision() -> None:
    first = _new_plan()
    second = StratigraphyDescriptionTrackingWorkflow.plan(
        first.translation_statuses,
        first.authored_field_revisions,
        first.authored_field_source_languages,
        interval_id=INTERVAL_ID,
        previous_depth=(100.0, 120.0),
        current_depth=(100.0, 120.0),
        previous_classification=("K1", "Formation"),
        current_classification=("K1", "Formation"),
        previous_texts={"ru": "Меловые отложения", "kk": "Бор шөгінділері"},
        current_texts={"ru": "Меловые отложения", "kk": "Жоғарғы бор шөгінділері"},
        source_language="ru",
    )

    assert second.authored_field_revisions[FIELD_ID] == 1
    target = second.translation_statuses[FIELD_ID]["kk"]
    assert target.state is TranslationState.DRAFT
    assert target.translation_revision == 2


def test_invalid_stratigraphy_tracking_input_is_fail_fast() -> None:
    with pytest.raises(ValueError, match="ID стратиграфического"):
        StratigraphyDescriptionTrackingWorkflow.plan(
            {},
            {},
            {},
            interval_id=" ",
            previous_depth=None,
            current_depth=(100.0, 120.0),
            previous_classification=None,
            current_classification=("K1", "Formation"),
            previous_texts={},
            current_texts={"ru": "Описание"},
            source_language="ru",
        )

    with pytest.raises(ValueError, match="меньше подошвы"):
        StratigraphyDescriptionTrackingWorkflow.plan(
            {},
            {},
            {},
            interval_id=INTERVAL_ID,
            previous_depth=None,
            current_depth=(120.0, 100.0),
            previous_classification=None,
            current_classification=("K1", "Formation"),
            previous_texts={},
            current_texts={"ru": "Описание"},
            source_language="ru",
        )

    with pytest.raises(ValueError, match="Код стратиграфического"):
        StratigraphyDescriptionTrackingWorkflow.plan(
            {},
            {},
            {},
            interval_id=INTERVAL_ID,
            previous_depth=None,
            current_depth=(100.0, 120.0),
            previous_classification=None,
            current_classification=(" ", "Formation"),
            previous_texts={},
            current_texts={"ru": "Описание"},
            source_language="ru",
        )
