from __future__ import annotations

import pytest

from geoworkbench.domain.cuttings_analysis_interpretation_tracking import (
    CuttingsAnalysisContext,
    CuttingsAnalysisInterpretationTrackingWorkflow,
)
from geoworkbench.domain.translation_status import TranslationState, TranslationStatus


SAMPLE_ID = "sample-1"
FIELD_ID = f"cuttings/{SAMPLE_ID}/analysis_interpretation"
DEPTH_ID = f"{FIELD_ID}/depth"
CONTEXT_ID = f"{FIELD_ID}/context"
BASE_CONTEXT = CuttingsAnalysisContext(
    calcite_percent=20.0,
    dolomite_percent=10.0,
    lba_group=2,
    lba_intensity=3,
    lba_type_id="oil",
    lba_color="brown",
    lba_distribution="uniform",
)


def _new_plan():
    return CuttingsAnalysisInterpretationTrackingWorkflow.plan(
        {},
        {},
        {},
        sample_id=SAMPLE_ID,
        previous_depth=None,
        current_depth=(100.0, 110.0),
        previous_context=None,
        current_context=BASE_CONTEXT,
        previous_texts={},
        current_texts={
            "ru": "Признаки нефтенасыщения подтверждены",
            "kk": "Мұнайға қанығу белгілері расталды",
        },
        source_language="ru",
    )


def test_new_interpretation_tracks_source_and_analysis_dependencies() -> None:
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


def test_initial_tracking_does_not_touch_lba_description_metadata() -> None:
    lba_field = f"cuttings/{SAMPLE_ID}/lba_description"
    lba_context = f"{lba_field}/context"
    lba_status = TranslationStatus(
        state=TranslationState.REVIEWED,
        source_language="ru",
        source_revision=4,
        translation_revision=3,
        dependency_revisions={lba_context: 6},
    )

    plan = CuttingsAnalysisInterpretationTrackingWorkflow.plan(
        {lba_field: {"kk": lba_status}},
        {lba_field: 4, lba_context: 6},
        {lba_field: "ru"},
        sample_id=SAMPLE_ID,
        previous_depth=None,
        current_depth=(100.0, 110.0),
        previous_context=None,
        current_context=BASE_CONTEXT,
        previous_texts={},
        current_texts={"ru": "Заключение"},
        source_language="ru",
    )

    assert plan.authored_field_revisions[lba_context] == 6
    assert plan.translation_statuses[lba_field]["kk"] == lba_status


def test_calcimetry_change_stales_target_without_source_revision_bump() -> None:
    first = _new_plan()
    changed_context = CuttingsAnalysisContext(
        calcite_percent=25.0,
        dolomite_percent=10.0,
        lba_group=2,
        lba_intensity=3,
        lba_type_id="oil",
        lba_color="brown",
        lba_distribution="uniform",
    )

    second = CuttingsAnalysisInterpretationTrackingWorkflow.plan(
        first.translation_statuses,
        first.authored_field_revisions,
        first.authored_field_source_languages,
        sample_id=SAMPLE_ID,
        previous_depth=(100.0, 110.0),
        current_depth=(100.0, 110.0),
        previous_context=BASE_CONTEXT,
        current_context=changed_context,
        previous_texts={
            "ru": "Признаки нефтенасыщения подтверждены",
            "kk": "Мұнайға қанығу белгілері расталды",
        },
        current_texts={
            "ru": "Признаки нефтенасыщения подтверждены",
            "kk": "Мұнайға қанығу белгілері расталды",
        },
        source_language="ru",
    )

    assert second.authored_field_revisions[FIELD_ID] == 1
    assert second.authored_field_revisions[CONTEXT_ID] == 2
    assert second.translation_statuses[FIELD_ID]["ru"].state is TranslationState.REVIEWED
    assert second.translation_statuses[FIELD_ID]["kk"].state is TranslationState.STALE


def test_lba_context_change_stales_interpretation_target() -> None:
    first = _new_plan()
    changed_context = CuttingsAnalysisContext(
        calcite_percent=20.0,
        dolomite_percent=10.0,
        lba_group=2,
        lba_intensity=4,
        lba_type_id="oil",
        lba_color="brown",
        lba_distribution="uniform",
    )

    second = CuttingsAnalysisInterpretationTrackingWorkflow.plan(
        first.translation_statuses,
        first.authored_field_revisions,
        first.authored_field_source_languages,
        sample_id=SAMPLE_ID,
        previous_depth=(100.0, 110.0),
        current_depth=(100.0, 110.0),
        previous_context=BASE_CONTEXT,
        current_context=changed_context,
        previous_texts={"ru": "Заключение", "kk": "Қорытынды"},
        current_texts={"ru": "Заключение", "kk": "Қорытынды"},
        source_language="ru",
    )

    assert second.authored_field_revisions[CONTEXT_ID] == 2
    assert second.translation_statuses[FIELD_ID]["kk"].state is TranslationState.STALE


def test_context_normalization_avoids_false_revision() -> None:
    first = _new_plan()
    equivalent_context = CuttingsAnalysisContext(
        calcite_percent=20,
        dolomite_percent=10,
        lba_group=2,
        lba_intensity=3,
        lba_type_id=" oil ",
        lba_color="brown",
        lba_distribution="uniform",
    )

    second = CuttingsAnalysisInterpretationTrackingWorkflow.plan(
        first.translation_statuses,
        first.authored_field_revisions,
        first.authored_field_source_languages,
        sample_id=SAMPLE_ID,
        previous_depth=(100.0, 110.0),
        current_depth=(100.0, 110.0),
        previous_context=BASE_CONTEXT,
        current_context=equivalent_context,
        previous_texts={
            "ru": "Признаки нефтенасыщения подтверждены",
            "kk": "Мұнайға қанығу белгілері расталды",
        },
        current_texts={
            "ru": "Признаки нефтенасыщения подтверждены",
            "kk": "Мұнайға қанығу белгілері расталды",
        },
        source_language="ru",
    )

    assert second.authored_field_revisions[CONTEXT_ID] == 1
    assert second.translation_statuses[FIELD_ID]["kk"].state is TranslationState.DRAFT


def test_depth_change_stales_only_interpretation_targets() -> None:
    first = _new_plan()
    second = CuttingsAnalysisInterpretationTrackingWorkflow.plan(
        first.translation_statuses,
        first.authored_field_revisions,
        first.authored_field_source_languages,
        sample_id=SAMPLE_ID,
        previous_depth=(100.0, 110.0),
        current_depth=(100.0, 111.0),
        previous_context=BASE_CONTEXT,
        current_context=BASE_CONTEXT,
        previous_texts={
            "ru": "Признаки нефтенасыщения подтверждены",
            "kk": "Мұнайға қанығу белгілері расталды",
        },
        current_texts={
            "ru": "Признаки нефтенасыщения подтверждены",
            "kk": "Мұнайға қанығу белгілері расталды",
        },
        source_language="ru",
    )

    assert second.authored_field_revisions[DEPTH_ID] == 2
    assert second.authored_field_revisions[CONTEXT_ID] == 1
    assert second.translation_statuses[FIELD_ID]["kk"].state is TranslationState.STALE


def test_invalid_analysis_context_is_fail_fast() -> None:
    with pytest.raises(ValueError, match="Сумма кальцита и доломита"):
        CuttingsAnalysisInterpretationTrackingWorkflow.plan(
            {},
            {},
            {},
            sample_id=SAMPLE_ID,
            previous_depth=None,
            current_depth=(100.0, 110.0),
            previous_context=None,
            current_context=CuttingsAnalysisContext(
                calcite_percent=80.0,
                dolomite_percent=30.0,
            ),
            previous_texts={},
            current_texts={"ru": "Заключение"},
            source_language="ru",
        )

    with pytest.raises(ValueError, match="Интенсивность ЛБА"):
        CuttingsAnalysisInterpretationTrackingWorkflow.plan(
            {},
            {},
            {},
            sample_id=SAMPLE_ID,
            previous_depth=None,
            current_depth=(100.0, 110.0),
            previous_context=None,
            current_context=CuttingsAnalysisContext(lba_intensity=6),
            previous_texts={},
            current_texts={"ru": "Заключение"},
            source_language="ru",
        )

    with pytest.raises(ValueError, match="ID пробы"):
        CuttingsAnalysisInterpretationTrackingWorkflow.plan(
            {},
            {},
            {},
            sample_id=" ",
            previous_depth=None,
            current_depth=(100.0, 110.0),
            previous_context=None,
            current_context=BASE_CONTEXT,
            previous_texts={},
            current_texts={"ru": "Заключение"},
            source_language="ru",
        )
