from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.domain.translation_status import TranslationState
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.session import ProjectSession


def _controller() -> CuttingsController:
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
    return CuttingsController(session)


def _tracked_sample(controller: CuttingsController):
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
        lba_description_source_language="ru",
        analysis_interpretation_source_language="ru",
    )


def test_set_analysis_tracks_lba_and_interpretation_in_one_write() -> None:
    controller = _controller()
    sample = _tracked_sample(controller)
    well = controller.session.current_well
    assert well is not None

    lba_field = f"cuttings/{sample.sample_id}/lba_description"
    interpretation_field = f"cuttings/{sample.sample_id}/analysis_interpretation"

    assert controller.lba_description_source_language(sample.sample_id) == "ru"
    assert controller.analysis_interpretation_source_language(sample.sample_id) == "ru"
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


def test_calcimetry_change_stales_only_interpretation_and_inherits_sources() -> None:
    controller = _controller()
    sample = _tracked_sample(controller)
    well = controller.session.current_well
    assert well is not None

    lba_field = f"cuttings/{sample.sample_id}/lba_description"
    interpretation_field = f"cuttings/{sample.sample_id}/analysis_interpretation"
    content_revision_before = well.content_revision

    controller.set_analysis(
        100.0,
        110.0,
        calcite_percent=25.0,
        dolomite_percent=10.0,
        lba_group=sample.lba_group,
        lba_type_id=sample.lba_type_id,
        lba_intensity=sample.lba_intensity,
        lba_color=sample.lba_color,
        lba_distribution=sample.lba_distribution,
        lba_description_i18n=dict(sample.lba_description_i18n),
        analysis_interpretation_i18n=dict(sample.analysis_interpretation_i18n),
    )

    assert controller.lba_description_source_language(sample.sample_id) == "ru"
    assert controller.analysis_interpretation_source_language(sample.sample_id) == "ru"
    assert well.translation_statuses[lba_field]["kk"].state is TranslationState.DRAFT
    assert (
        well.translation_statuses[interpretation_field]["kk"].state
        is TranslationState.STALE
    )
    assert well.authored_field_revisions[lba_field] == 1
    assert well.authored_field_revisions[interpretation_field] == 1
    assert well.content_revision == content_revision_before + 1


def test_interpretation_only_tracking_preserves_plain_lba_description() -> None:
    controller = _controller()

    sample = controller.set_analysis(
        100.0,
        110.0,
        lba_group=2,
        lba_intensity=3,
        lba_description="Legacy LBA text",
        analysis_interpretation_i18n={
            "ru": "Заключение",
            "kk": "Қорытынды",
        },
        analysis_interpretation_source_language="ru",
    )
    well = controller.session.current_well
    assert well is not None

    lba_field = f"cuttings/{sample.sample_id}/lba_description"
    interpretation_field = f"cuttings/{sample.sample_id}/analysis_interpretation"
    assert sample.lba_description == "Legacy LBA text"
    assert controller.lba_description_source_language(sample.sample_id) is None
    assert controller.analysis_interpretation_source_language(sample.sample_id) == "ru"
    assert lba_field not in well.translation_statuses
    assert interpretation_field in well.translation_statuses


def test_plain_tracked_interpretation_update_is_rejected_atomically() -> None:
    controller = _controller()
    sample = _tracked_sample(controller)
    well = controller.session.current_well
    assert well is not None

    sample_before = deepcopy(sample)
    statuses_before = deepcopy(well.translation_statuses)
    revisions_before = dict(well.authored_field_revisions)
    sources_before = dict(well.authored_field_source_languages)
    language_revisions_before = dict(well.language_revisions)
    content_revision_before = well.content_revision

    with pytest.raises(ValueError, match="tracked-заключения"):
        controller.set_analysis(
            100.0,
            110.0,
            calcite_percent=sample.calcite_percent,
            dolomite_percent=sample.dolomite_percent,
            lba_group=sample.lba_group,
            lba_type_id=sample.lba_type_id,
            lba_intensity=sample.lba_intensity,
            lba_color=sample.lba_color,
            lba_distribution=sample.lba_distribution,
            lba_description_i18n=dict(sample.lba_description_i18n),
            analysis_interpretation="Новое plain-заключение",
        )

    assert sample == sample_before
    assert well.translation_statuses == statuses_before
    assert well.authored_field_revisions == revisions_before
    assert well.authored_field_source_languages == sources_before
    assert well.language_revisions == language_revisions_before
    assert well.content_revision == content_revision_before


def test_remove_clears_lba_and_interpretation_provenance() -> None:
    controller = _controller()
    sample = _tracked_sample(controller)
    well = controller.session.current_well
    assert well is not None

    lba_field = f"cuttings/{sample.sample_id}/lba_description"
    interpretation_field = f"cuttings/{sample.sample_id}/analysis_interpretation"
    controller.remove(sample.sample_id)

    assert lba_field not in well.translation_statuses
    assert interpretation_field not in well.translation_statuses
    assert lba_field not in well.authored_field_source_languages
    assert interpretation_field not in well.authored_field_source_languages
    assert lba_field not in well.authored_field_revisions
    assert interpretation_field not in well.authored_field_revisions
