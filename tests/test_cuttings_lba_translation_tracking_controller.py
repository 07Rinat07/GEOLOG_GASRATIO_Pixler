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


def _tracked_lba(controller: CuttingsController):
    return controller.set_analysis(
        100.0,
        110.0,
        lba_group=2,
        lba_type_id="mb",
        lba_intensity=3,
        lba_color="brown",
        lba_distribution="uniform",
        lba_description_i18n={
            "ru": "Равномерное коричневое свечение",
            "kk": "Біркелкі қоңыр люминесценция",
        },
        lba_description_source_language="ru",
    )


def test_set_analysis_tracks_lba_description_source_and_targets() -> None:
    controller = _controller()
    sample = _tracked_lba(controller)
    well = controller.session.current_well
    assert well is not None
    field_id = f"cuttings/{sample.sample_id}/lba_description"
    depth_id = f"{field_id}/depth"
    context_id = f"{field_id}/context"

    assert controller.lba_description_source_language(sample.sample_id) == "ru"
    assert well.authored_field_revisions[field_id] == 1
    assert well.authored_field_revisions[depth_id] == 1
    assert well.authored_field_revisions[context_id] == 1
    assert well.translation_statuses[field_id]["ru"].state is TranslationState.REVIEWED
    assert well.translation_statuses[field_id]["ru"].translation_revision == 0
    assert well.translation_statuses[field_id]["kk"].state is TranslationState.DRAFT
    assert well.translation_statuses[field_id]["en"].state is TranslationState.MISSING


def test_lba_context_change_stales_targets_once_without_source_revision_bump() -> None:
    controller = _controller()
    sample = _tracked_lba(controller)
    well = controller.session.current_well
    assert well is not None
    field_id = f"cuttings/{sample.sample_id}/lba_description"
    context_id = f"{field_id}/context"
    source_revision_before = well.authored_field_revisions[field_id]
    content_revision_before = well.content_revision
    language_revisions_before = dict(well.language_revisions)

    controller.set_analysis(
        100.0,
        110.0,
        lba_group=2,
        lba_type_id="mb",
        lba_intensity=4,
        lba_color="brown",
        lba_distribution="uniform",
        lba_description_i18n=dict(sample.lba_description_i18n),
    )

    assert well.authored_field_revisions[field_id] == source_revision_before
    assert well.authored_field_revisions[context_id] == 2
    assert well.translation_statuses[field_id]["ru"].state is TranslationState.REVIEWED
    assert well.translation_statuses[field_id]["kk"].state is TranslationState.STALE
    assert well.content_revision == content_revision_before + 1
    assert well.language_revisions == language_revisions_before


def test_calcimetry_only_change_does_not_stale_lba_translation() -> None:
    controller = _controller()
    sample = _tracked_lba(controller)
    well = controller.session.current_well
    assert well is not None
    field_id = f"cuttings/{sample.sample_id}/lba_description"
    context_id = f"{field_id}/context"
    context_revision_before = well.authored_field_revisions[context_id]

    controller.set_analysis(
        100.0,
        110.0,
        calcite_percent=20.0,
        dolomite_percent=10.0,
        lba_group=sample.lba_group,
        lba_type_id=sample.lba_type_id,
        lba_intensity=sample.lba_intensity,
        lba_color=sample.lba_color,
        lba_distribution=sample.lba_distribution,
        lba_description_i18n=dict(sample.lba_description_i18n),
    )

    assert well.authored_field_revisions[context_id] == context_revision_before
    assert well.translation_statuses[field_id]["kk"].state is TranslationState.DRAFT


def test_invalid_lba_source_change_is_atomic() -> None:
    controller = _controller()
    sample = _tracked_lba(controller)
    well = controller.session.current_well
    assert well is not None
    sample_before = deepcopy(sample)
    statuses_before = deepcopy(well.translation_statuses)
    revisions_before = dict(well.authored_field_revisions)
    sources_before = dict(well.authored_field_source_languages)
    content_revision_before = well.content_revision

    with pytest.raises(ValueError, match="язык оригинала"):
        controller.set_analysis(
            100.0,
            110.0,
            lba_group=2,
            lba_type_id="mb",
            lba_intensity=3,
            lba_color="brown",
            lba_description_i18n={"ru": "Описание"},
            lba_description_source_language="kk",
        )

    assert sample == sample_before
    assert well.translation_statuses == statuses_before
    assert well.authored_field_revisions == revisions_before
    assert well.authored_field_source_languages == sources_before
    assert well.content_revision == content_revision_before


def test_remove_tracked_sample_cleans_lba_tracking_metadata() -> None:
    controller = _controller()
    sample = _tracked_lba(controller)
    well = controller.session.current_well
    assert well is not None

    controller.remove(sample.sample_id)

    assert not any(sample.sample_id in key for key in well.authored_field_source_languages)
    assert not any(sample.sample_id in key for key in well.authored_field_revisions)
    assert not any(sample.sample_id in key for key in well.translation_statuses)
