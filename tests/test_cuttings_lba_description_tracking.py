from __future__ import annotations

import pytest

from geoworkbench.domain.cuttings_lba_description_tracking import (
    CuttingsLbaContext,
    CuttingsLbaDescriptionTrackingWorkflow,
)
from geoworkbench.domain.translation_status import TranslationState


SAMPLE_ID = "sample-1"
FIELD_ID = f"cuttings/{SAMPLE_ID}/lba_description"
DEPTH_ID = f"cuttings/{SAMPLE_ID}/depth"
CONTEXT_ID = f"cuttings/{SAMPLE_ID}/lba_context"
BASE_CONTEXT = CuttingsLbaContext(
    group=2,
    intensity=3,
    type_id="oil",
    color="brown",
    distribution="uniform",
)


def _new_plan():
    return CuttingsLbaDescriptionTrackingWorkflow.plan(
        {},
        {},
        {},
        sample_id=SAMPLE_ID,
        previous_depth=None,
        current_depth=(100.0, 110.0),
        previous_context=None,
        current_context=BASE_CONTEXT,
        previous_texts={},
        current_texts={"ru": "Равномерное свечение", "kk": "Біркелкі люминесценция"},
        source_language="ru",
    )


def test_new_lba_description_tracks_source_and_relevant_dependencies() -> None:
    plan = _new_plan()

    assert plan.authored_field_revisions[FIELD_ID] == 1
    assert plan.authored_field_revisions[DEPTH_ID] == 1
    assert plan.authored_field_revisions[CONTEXT_ID] == 1
    assert plan.authored_field_source_languages[FIELD_ID] == "ru"
    source = plan.translation_statuses[FIELD_ID]["ru"]
    target = plan.translation_statuses[FIELD_ID]["kk"]
    missing = plan.translation_statuses[FIELD_ID]["en"]
    assert source.state is TranslationState.REVIEWED
    assert source.translation_revision == 0
    assert target.state is TranslationState.DRAFT
    assert target.dependency_revisions == {DEPTH_ID: 1, CONTEXT_ID: 1}
    assert missing.state is TranslationState.MISSING


def test_lba_context_change_stales_target_without_bumping_source_revision() -> None:
    first = _new_plan()
    changed_context = CuttingsLbaContext(
        group=2,
        intensity=4,
        type_id="oil",
        color="brown",
        distribution="uniform",
    )

    second = CuttingsLbaDescriptionTrackingWorkflow.plan(
        first.translation_statuses,
        first.authored_field_revisions,
        first.authored_field_source_languages,
        sample_id=SAMPLE_ID,
        previous_depth=(100.0, 110.0),
        current_depth=(100.0, 110.0),
        previous_context=BASE_CONTEXT,
        current_context=changed_context,
        previous_texts={"ru": "Равномерное свечение", "kk": "Біркелкі люминесценция"},
        current_texts={"ru": "Равномерное свечение", "kk": "Біркелкі люминесценция"},
        source_language="ru",
    )

    assert second.authored_field_revisions[FIELD_ID] == 1
    assert second.authored_field_revisions[DEPTH_ID] == 1
    assert second.authored_field_revisions[CONTEXT_ID] == 2
    assert second.translation_statuses[FIELD_ID]["kk"].state is TranslationState.STALE
    assert second.translation_statuses[FIELD_ID]["ru"].state is TranslationState.REVIEWED


def test_context_normalization_avoids_false_revision() -> None:
    first = _new_plan()
    equivalent_context = CuttingsLbaContext(
        group=2,
        intensity=3,
        type_id=" oil ",
        color="brown",
        distribution="uniform",
    )

    second = CuttingsLbaDescriptionTrackingWorkflow.plan(
        first.translation_statuses,
        first.authored_field_revisions,
        first.authored_field_source_languages,
        sample_id=SAMPLE_ID,
        previous_depth=(100.0, 110.0),
        current_depth=(100.0, 110.0),
        previous_context=BASE_CONTEXT,
        current_context=equivalent_context,
        previous_texts={"ru": "Равномерное свечение", "kk": "Біркелкі люминесценция"},
        current_texts={"ru": "Равномерное свечение", "kk": "Біркелкі люминесценция"},
        source_language="ru",
    )

    assert second.authored_field_revisions[CONTEXT_ID] == 1
    assert second.translation_statuses[FIELD_ID]["kk"].state is TranslationState.DRAFT


def test_depth_change_stales_only_this_field_targets() -> None:
    first = _new_plan()
    second = CuttingsLbaDescriptionTrackingWorkflow.plan(
        first.translation_statuses,
        first.authored_field_revisions,
        first.authored_field_source_languages,
        sample_id=SAMPLE_ID,
        previous_depth=(100.0, 110.0),
        current_depth=(100.0, 111.0),
        previous_context=BASE_CONTEXT,
        current_context=BASE_CONTEXT,
        previous_texts={"ru": "Равномерное свечение", "kk": "Біркелкі люминесценция"},
        current_texts={"ru": "Равномерное свечение", "kk": "Біркелкі люминесценция"},
        source_language="ru",
    )

    assert second.authored_field_revisions[DEPTH_ID] == 2
    assert second.authored_field_revisions[CONTEXT_ID] == 1
    assert second.translation_statuses[FIELD_ID]["kk"].state is TranslationState.STALE


def test_target_edit_advances_translation_revision_without_source_bump() -> None:
    first = _new_plan()
    second = CuttingsLbaDescriptionTrackingWorkflow.plan(
        first.translation_statuses,
        first.authored_field_revisions,
        first.authored_field_source_languages,
        sample_id=SAMPLE_ID,
        previous_depth=(100.0, 110.0),
        current_depth=(100.0, 110.0),
        previous_context=BASE_CONTEXT,
        current_context=BASE_CONTEXT,
        previous_texts={"ru": "Равномерное свечение", "kk": "Біркелкі люминесценция"},
        current_texts={"ru": "Равномерное свечение", "kk": "Күшті біркелкі люминесценция"},
        source_language="ru",
    )

    assert second.authored_field_revisions[FIELD_ID] == 1
    target = second.translation_statuses[FIELD_ID]["kk"]
    assert target.state is TranslationState.DRAFT
    assert target.translation_revision == 2


def test_invalid_lba_context_is_fail_fast() -> None:
    with pytest.raises(ValueError, match="Интенсивность ЛБА"):
        CuttingsLbaDescriptionTrackingWorkflow.plan(
            {},
            {},
            {},
            sample_id=SAMPLE_ID,
            previous_depth=None,
            current_depth=(100.0, 110.0),
            previous_context=None,
            current_context=CuttingsLbaContext(intensity=6),
            previous_texts={},
            current_texts={"ru": "Описание"},
            source_language="ru",
        )

    with pytest.raises(ValueError, match="ID пробы"):
        CuttingsLbaDescriptionTrackingWorkflow.plan(
            {},
            {},
            {},
            sample_id=" ",
            previous_depth=None,
            current_depth=(100.0, 110.0),
            previous_context=None,
            current_context=BASE_CONTEXT,
            previous_texts={},
            current_texts={"ru": "Описание"},
            source_language="ru",
        )
