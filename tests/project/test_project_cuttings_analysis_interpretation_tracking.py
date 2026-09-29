from __future__ import annotations

from copy import deepcopy

import numpy as np

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


def _sample(controller: CuttingsController):
    return controller.set_analysis(
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


def test_service_applies_source_language_and_dependency_revisions() -> None:
    controller, service = _service()
    sample = _sample(controller)
    well = controller.session.current_well
    assert well is not None

    plan = service.plan(None, sample, source_language="ru")
    service.apply(plan)

    field_id = f"cuttings/{sample.sample_id}/analysis_interpretation"
    depth_id = f"{field_id}/depth"
    context_id = f"{field_id}/context"

    assert service.source_language(sample.sample_id) == "ru"
    assert well.authored_field_revisions[field_id] == 1
    assert well.authored_field_revisions[depth_id] == 1
    assert well.authored_field_revisions[context_id] == 1
    assert well.translation_statuses[field_id]["ru"].state is TranslationState.REVIEWED
    assert well.translation_statuses[field_id]["kk"].state is TranslationState.DRAFT
    assert well.translation_statuses[field_id]["en"].state is TranslationState.MISSING


def test_calcimetry_change_stales_target_without_bumping_source_revision() -> None:
    controller, service = _service()
    sample = _sample(controller)
    well = controller.session.current_well
    assert well is not None

    first = service.plan(None, sample, source_language="ru")
    service.apply(first)
    previous = deepcopy(sample)
    current = deepcopy(sample)
    current.calcite_percent = 25.0

    second = service.plan(previous, current, source_language="ru")
    service.apply(second)

    field_id = f"cuttings/{sample.sample_id}/analysis_interpretation"
    context_id = f"{field_id}/context"
    assert well.authored_field_revisions[field_id] == 1
    assert well.authored_field_revisions[context_id] == 2
    assert well.translation_statuses[field_id]["ru"].state is TranslationState.REVIEWED
    assert well.translation_statuses[field_id]["kk"].state is TranslationState.STALE


def test_clear_removes_only_interpretation_tracking_metadata() -> None:
    controller, service = _service()
    sample = _sample(controller)
    well = controller.session.current_well
    assert well is not None

    plan = service.plan(None, sample, source_language="ru")
    service.apply(plan)
    unrelated_field = f"cuttings/{sample.sample_id}/lba_description"
    well.authored_field_revisions[unrelated_field] = 7

    service.clear(sample.sample_id)

    field_id = f"cuttings/{sample.sample_id}/analysis_interpretation"
    assert field_id not in well.translation_statuses
    assert field_id not in well.authored_field_source_languages
    assert field_id not in well.authored_field_revisions
    assert f"{field_id}/depth" not in well.authored_field_revisions
    assert f"{field_id}/context" not in well.authored_field_revisions
    assert well.authored_field_revisions[unrelated_field] == 7
