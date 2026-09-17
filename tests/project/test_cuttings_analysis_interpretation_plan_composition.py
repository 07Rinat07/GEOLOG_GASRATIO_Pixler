from __future__ import annotations

import numpy as np

from geoworkbench.domain.authored_translation_tracking import AuthoredTranslationPlan
from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.domain.translation_status import TranslationState
from geoworkbench.project.cuttings_analysis_interpretation_tracking import (
    CuttingsAnalysisInterpretationTrackingService,
)
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.session import ProjectSession


def _service() -> tuple[CuttingsController, CuttingsAnalysisInterpretationTrackingService]:
    session = ProjectSession()
    session.add_dataset(
        Dataset(
            "dataset",
            "Well",
            DatasetKind.GTI,
            DepthDomain.MD,
            np.array([100.0, 200.0]),
        )
    )
    session.dirty = False
    return CuttingsController(session), CuttingsAnalysisInterpretationTrackingService(session)


def test_plan_composes_on_top_of_existing_field_scoped_metadata() -> None:
    controller, service = _service()
    sample = controller.set_analysis(
        100.0,
        110.0,
        calcite_percent=20.0,
        dolomite_percent=10.0,
        lba_group=2,
        lba_type_id="oil",
        lba_intensity=3,
        lba_color="brown",
        lba_distribution="uniform",
        analysis_interpretation_i18n={
            "ru": "Признаки нефтенасыщения подтверждены",
            "kk": "Мұнайға қанығу белгілері расталды",
        },
    )
    well = controller.session.current_well
    assert well is not None

    unrelated_field = f"cuttings/{sample.sample_id}/lba_description"
    base_plan = AuthoredTranslationPlan(
        translation_statuses={},
        authored_field_revisions={unrelated_field: 7},
        authored_field_source_languages={unrelated_field: "ru"},
        source_revision=7,
    )

    plan = service.plan(None, sample, source_language="ru", base_plan=base_plan)

    interpretation_field = f"cuttings/{sample.sample_id}/analysis_interpretation"
    assert well.authored_field_revisions == {}
    assert well.authored_field_source_languages == {}
    assert plan.authored_field_revisions[unrelated_field] == 7
    assert plan.authored_field_source_languages[unrelated_field] == "ru"
    assert plan.authored_field_revisions[interpretation_field] == 1
    assert plan.authored_field_source_languages[interpretation_field] == "ru"
    assert (
        plan.translation_statuses[interpretation_field]["ru"].state
        is TranslationState.REVIEWED
    )
    assert (
        plan.translation_statuses[interpretation_field]["kk"].state
        is TranslationState.DRAFT
    )


def test_apply_commits_composed_metadata_once_plan_is_valid() -> None:
    controller, service = _service()
    sample = controller.set_analysis(
        100.0,
        110.0,
        calcite_percent=20.0,
        analysis_interpretation_i18n={"ru": "Заключение"},
    )
    well = controller.session.current_well
    assert well is not None

    unrelated_field = f"cuttings/{sample.sample_id}/lba_description"
    base_plan = AuthoredTranslationPlan(
        translation_statuses={},
        authored_field_revisions={unrelated_field: 3},
        authored_field_source_languages={unrelated_field: "ru"},
        source_revision=3,
    )
    plan = service.plan(None, sample, source_language="ru", base_plan=base_plan)

    service.apply(plan)

    interpretation_field = f"cuttings/{sample.sample_id}/analysis_interpretation"
    assert well.authored_field_revisions[unrelated_field] == 3
    assert well.authored_field_revisions[interpretation_field] == 1
    assert well.authored_field_source_languages[unrelated_field] == "ru"
    assert well.authored_field_source_languages[interpretation_field] == "ru"
