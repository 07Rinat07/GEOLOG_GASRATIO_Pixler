from __future__ import annotations

import pytest

from geoworkbench.domain.cuttings_description_tracking import (
    CuttingsDescriptionTrackingWorkflow,
)
from geoworkbench.domain.translation_status import TranslationState


SAMPLE_ID = "sample-1"
FIELD_ID = f"cuttings/{SAMPLE_ID}/description"
DEPTH_ID = f"cuttings/{SAMPLE_ID}/depth"
COMPOSITION_ID = f"cuttings/{SAMPLE_ID}/composition"


def _new_plan():
    return CuttingsDescriptionTrackingWorkflow.plan(
        {},
        {},
        {},
        sample_id=SAMPLE_ID,
        previous_depth=None,
        current_depth=(100.0, 110.0),
        previous_components=None,
        current_components={"sandstone": 70.0, "claystone": 30.0},
        previous_texts={},
        current_texts={"ru": "Песчаник", "kk": "Құмтас"},
        source_language="ru",
    )


def test_new_cuttings_description_tracks_source_and_dependencies() -> None:
    plan = _new_plan()

    assert plan.authored_field_revisions[FIELD_ID] == 1
    assert plan.authored_field_revisions[DEPTH_ID] == 1
    assert plan.authored_field_revisions[COMPOSITION_ID] == 1
    assert plan.authored_field_source_languages[FIELD_ID] == "ru"
    source = plan.translation_statuses[FIELD_ID]["ru"]
    target = plan.translation_statuses[FIELD_ID]["kk"]
    missing = plan.translation_statuses[FIELD_ID]["en"]
    assert source.state is TranslationState.REVIEWED
    assert source.translation_revision == 0
    assert target.state is TranslationState.DRAFT
    assert target.dependency_revisions == {DEPTH_ID: 1, COMPOSITION_ID: 1}
    assert missing.state is TranslationState.MISSING


def test_depth_change_stales_target_without_bumping_source_revision() -> None:
    first = _new_plan()
    second = CuttingsDescriptionTrackingWorkflow.plan(
        first.translation_statuses,
        first.authored_field_revisions,
        first.authored_field_source_languages,
        sample_id=SAMPLE_ID,
        previous_depth=(100.0, 110.0),
        current_depth=(100.0, 112.0),
        previous_components={"sandstone": 70.0, "claystone": 30.0},
        current_components={"sandstone": 70.0, "claystone": 30.0},
        previous_texts={"ru": "Песчаник", "kk": "Құмтас"},
        current_texts={"ru": "Песчаник", "kk": "Құмтас"},
        source_language="ru",
    )

    assert second.authored_field_revisions[FIELD_ID] == 1
    assert second.authored_field_revisions[DEPTH_ID] == 2
    assert second.authored_field_revisions[COMPOSITION_ID] == 1
    assert second.translation_statuses[FIELD_ID]["kk"].state is TranslationState.STALE
    assert second.translation_statuses[FIELD_ID]["ru"].state is TranslationState.REVIEWED


def test_composition_change_stales_target_independent_of_mapping_order() -> None:
    first = _new_plan()
    unchanged = CuttingsDescriptionTrackingWorkflow.plan(
        first.translation_statuses,
        first.authored_field_revisions,
        first.authored_field_source_languages,
        sample_id=SAMPLE_ID,
        previous_depth=(100.0, 110.0),
        current_depth=(100.0, 110.0),
        previous_components={"sandstone": 70.0, "claystone": 30.0},
        current_components={"claystone": 30.0, "sandstone": 70.0},
        previous_texts={"ru": "Песчаник", "kk": "Құмтас"},
        current_texts={"ru": "Песчаник", "kk": "Құмтас"},
        source_language="ru",
    )
    changed = CuttingsDescriptionTrackingWorkflow.plan(
        unchanged.translation_statuses,
        unchanged.authored_field_revisions,
        unchanged.authored_field_source_languages,
        sample_id=SAMPLE_ID,
        previous_depth=(100.0, 110.0),
        current_depth=(100.0, 110.0),
        previous_components={"sandstone": 70.0, "claystone": 30.0},
        current_components={"sandstone": 60.0, "claystone": 40.0},
        previous_texts={"ru": "Песчаник", "kk": "Құмтас"},
        current_texts={"ru": "Песчаник", "kk": "Құмтас"},
        source_language="ru",
    )

    assert unchanged.authored_field_revisions[COMPOSITION_ID] == 1
    assert unchanged.translation_statuses[FIELD_ID]["kk"].state is TranslationState.DRAFT
    assert changed.authored_field_revisions[COMPOSITION_ID] == 2
    assert changed.translation_statuses[FIELD_ID]["kk"].state is TranslationState.STALE


def test_target_edit_advances_only_translation_revision() -> None:
    first = _new_plan()
    second = CuttingsDescriptionTrackingWorkflow.plan(
        first.translation_statuses,
        first.authored_field_revisions,
        first.authored_field_source_languages,
        sample_id=SAMPLE_ID,
        previous_depth=(100.0, 110.0),
        current_depth=(100.0, 110.0),
        previous_components={"sandstone": 70.0, "claystone": 30.0},
        current_components={"sandstone": 70.0, "claystone": 30.0},
        previous_texts={"ru": "Песчаник", "kk": "Құмтас"},
        current_texts={"ru": "Песчаник", "kk": "Ұсақ түйірлі құмтас"},
        source_language="ru",
    )

    assert second.authored_field_revisions[FIELD_ID] == 1
    assert second.translation_statuses[FIELD_ID]["kk"].state is TranslationState.DRAFT
    assert second.translation_statuses[FIELD_ID]["kk"].translation_revision == 2


def test_invalid_cuttings_tracking_input_is_fail_fast() -> None:
    with pytest.raises(ValueError, match="ID пробы"):
        CuttingsDescriptionTrackingWorkflow.plan(
            {},
            {},
            {},
            sample_id=" ",
            previous_depth=None,
            current_depth=(100.0, 110.0),
            previous_components=None,
            current_components={"sandstone": 100.0},
            previous_texts={},
            current_texts={"ru": "Песчаник"},
            source_language="ru",
        )

    with pytest.raises(ValueError, match="диапазоне"):
        CuttingsDescriptionTrackingWorkflow.plan(
            {},
            {},
            {},
            sample_id=SAMPLE_ID,
            previous_depth=None,
            current_depth=(100.0, 110.0),
            previous_components=None,
            current_components={"sandstone": 101.0},
            previous_texts={},
            current_texts={"ru": "Песчаник"},
            source_language="ru",
        )
