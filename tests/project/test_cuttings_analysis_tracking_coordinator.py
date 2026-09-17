from __future__ import annotations

from copy import deepcopy

import numpy as np

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.domain.translation_status import TranslationState
from geoworkbench.project.cuttings_analysis_tracking_coordinator import (
    CuttingsAnalysisTrackingCoordinator,
)
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.session import ProjectSession


def _controller() -> tuple[CuttingsController, CuttingsAnalysisTrackingCoordinator]:
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
    return CuttingsController(session), CuttingsAnalysisTrackingCoordinator(session)


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
        lba_description_i18n={
            "ru": "Равномерное коричневое свечение",
            "kk": "Біркелкі қоңыр люминесценция",
        },
        analysis_interpretation_i18n={
            "ru": "Признаки нефтенасыщения подтверждены",
            "kk": "Мұнайға қанығу белгілері расталды",
        },
    )


def test_plan_tracks_lba_and_interpretation_in_one_composed_snapshot() -> None:
    controller, coordinator = _controller()
    sample = _sample(controller)
    well = controller.session.current_well
    assert well is not None

    plan = coordinator.plan(
        None,
        sample,
        lba_description_source_language="ru",
        interpretation_source_language="ru",
    )
    coordinator.apply(plan)

    lba_field = f"cuttings/{sample.sample_id}/lba_description"
    interpretation_field = f"cuttings/{sample.sample_id}/analysis_interpretation"
    assert well.authored_field_source_languages[lba_field] == "ru"
    assert well.authored_field_source_languages[interpretation_field] == "ru"
    assert well.authored_field_revisions[lba_field] == 1
    assert well.authored_field_revisions[interpretation_field] == 1
    assert well.translation_statuses[lba_field]["ru"].state is TranslationState.REVIEWED
    assert well.translation_statuses[lba_field]["kk"].state is TranslationState.DRAFT
    assert (
        well.translation_statuses[interpretation_field]["ru"].state
        is TranslationState.REVIEWED
    )
    assert (
        well.translation_statuses[interpretation_field]["kk"].state
        is TranslationState.DRAFT
    )


def test_calcimetry_change_stales_only_interpretation_target() -> None:
    controller, coordinator = _controller()
    sample = _sample(controller)
    first = coordinator.plan(
        None,
        sample,
        lba_description_source_language="ru",
        interpretation_source_language="ru",
    )
    coordinator.apply(first)
    previous = deepcopy(sample)
    sample.calcite_percent = 25.0

    second = coordinator.plan(
        previous,
        sample,
        lba_description_source_language=coordinator.lba_source_language(sample.sample_id),
        interpretation_source_language=coordinator.interpretation_source_language(
            sample.sample_id
        ),
    )
    coordinator.apply(second)

    well = controller.session.current_well
    assert well is not None
    lba_field = f"cuttings/{sample.sample_id}/lba_description"
    interpretation_field = f"cuttings/{sample.sample_id}/analysis_interpretation"
    assert well.translation_statuses[lba_field]["kk"].state is TranslationState.DRAFT
    assert (
        well.translation_statuses[interpretation_field]["kk"].state
        is TranslationState.STALE
    )
    assert well.authored_field_revisions[lba_field] == 1
    assert well.authored_field_revisions[interpretation_field] == 1


def test_clear_removes_analysis_fields_without_touching_cuttings_description() -> None:
    controller, coordinator = _controller()
    sample = _sample(controller)
    well = controller.session.current_well
    assert well is not None
    description_field = f"cuttings/{sample.sample_id}/description"
    well.authored_field_revisions[description_field] = 8
    well.authored_field_source_languages[description_field] = "ru"

    plan = coordinator.plan(
        None,
        sample,
        lba_description_source_language="ru",
        interpretation_source_language="ru",
    )
    coordinator.apply(plan)
    coordinator.clear(sample.sample_id)

    lba_field = f"cuttings/{sample.sample_id}/lba_description"
    interpretation_field = f"cuttings/{sample.sample_id}/analysis_interpretation"
    assert lba_field not in well.authored_field_revisions
    assert interpretation_field not in well.authored_field_revisions
    assert lba_field not in well.authored_field_source_languages
    assert interpretation_field not in well.authored_field_source_languages
    assert well.authored_field_revisions[description_field] == 8
    assert well.authored_field_source_languages[description_field] == "ru"
