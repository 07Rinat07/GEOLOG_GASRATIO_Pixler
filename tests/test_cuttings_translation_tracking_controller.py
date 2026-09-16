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
    return controller.create_full_sample(
        100.0,
        110.0,
        {"sandstone": 70.0, "claystone": 30.0},
        description_i18n={"ru": "Песчаник", "kk": "Құмтас", "en": "Sandstone"},
        description_source_language="ru",
    )


def test_create_full_sample_tracks_description_source_and_targets() -> None:
    controller = _controller()
    sample = _tracked_sample(controller)
    well = controller.session.current_well
    assert well is not None
    field_id = f"cuttings/{sample.sample_id}/description"
    depth_id = f"cuttings/{sample.sample_id}/depth"
    composition_id = f"cuttings/{sample.sample_id}/composition"

    assert controller.description_source_language(sample.sample_id) == "ru"
    assert well.authored_field_revisions[field_id] == 1
    assert well.authored_field_revisions[depth_id] == 1
    assert well.authored_field_revisions[composition_id] == 1
    assert well.translation_statuses[field_id]["ru"].state is TranslationState.REVIEWED
    assert well.translation_statuses[field_id]["ru"].translation_revision == 0
    assert well.translation_statuses[field_id]["kk"].state is TranslationState.DRAFT
    assert well.translation_statuses[field_id]["en"].state is TranslationState.DRAFT


def test_composition_only_update_stales_targets_without_language_revision_bump() -> None:
    controller = _controller()
    sample = _tracked_sample(controller)
    well = controller.session.current_well
    assert well is not None
    field_id = f"cuttings/{sample.sample_id}/description"
    composition_id = f"cuttings/{sample.sample_id}/composition"
    language_revisions_before = dict(well.language_revisions)
    source_revision_before = well.authored_field_revisions[field_id]

    controller.update_composition(
        sample.sample_id,
        top_depth=100.0,
        bottom_depth=110.0,
        components={"sandstone": 60.0, "claystone": 40.0},
    )

    assert well.authored_field_revisions[field_id] == source_revision_before
    assert well.authored_field_revisions[composition_id] == 2
    assert well.translation_statuses[field_id]["ru"].state is TranslationState.REVIEWED
    assert well.translation_statuses[field_id]["kk"].state is TranslationState.STALE
    assert well.translation_statuses[field_id]["en"].state is TranslationState.STALE
    assert well.language_revisions == language_revisions_before


def test_invalid_full_update_is_atomic_for_sample_and_tracking_metadata() -> None:
    controller = _controller()
    sample = _tracked_sample(controller)
    well = controller.session.current_well
    assert well is not None
    sample_before = deepcopy(sample)
    statuses_before = deepcopy(well.translation_statuses)
    revisions_before = dict(well.authored_field_revisions)
    sources_before = dict(well.authored_field_source_languages)
    content_revision_before = well.content_revision

    with pytest.raises(ValueError, match="Группа ЛБА"):
        controller.update_full_sample(
            sample.sample_id,
            top_depth=101.0,
            bottom_depth=112.0,
            components={"sandstone": 50.0, "claystone": 50.0},
            lba_group=9,
            description_i18n={"ru": "Изменено", "kk": "Өзгертілді"},
            description_source_language="ru",
        )

    assert sample == sample_before
    assert well.translation_statuses == statuses_before
    assert well.authored_field_revisions == revisions_before
    assert well.authored_field_source_languages == sources_before
    assert well.content_revision == content_revision_before


def test_deleting_target_marks_it_missing_but_source_delete_is_rejected() -> None:
    controller = _controller()
    sample = _tracked_sample(controller)
    well = controller.session.current_well
    assert well is not None
    field_id = f"cuttings/{sample.sample_id}/description"

    controller.delete_description(sample.sample_id, language="kk")

    assert "kk" not in sample.description_i18n
    assert well.translation_statuses[field_id]["kk"].state is TranslationState.MISSING
    source_before = deepcopy(well.translation_statuses[field_id]["ru"])
    with pytest.raises(ValueError, match="язык оригинала"):
        controller.delete_description(sample.sample_id, language="ru")
    assert well.translation_statuses[field_id]["ru"] == source_before
    assert sample.description_i18n["ru"] == "Песчаник"


def test_legacy_full_sample_without_source_language_remains_untracked() -> None:
    controller = _controller()
    sample = controller.create_full_sample(
        100.0,
        110.0,
        {"sandstone": 100.0},
        description_i18n={"ru": "Песчаник", "kk": "Құмтас"},
    )
    well = controller.session.current_well
    assert well is not None

    controller.update_full_sample(
        sample.sample_id,
        top_depth=100.0,
        bottom_depth=111.0,
        components={"sandstone": 100.0},
        description_i18n={"ru": "Песчаник", "kk": "Құмтас"},
    )

    assert controller.description_source_language(sample.sample_id) is None
    assert not any(sample.sample_id in key for key in well.authored_field_source_languages)
    assert not any(sample.sample_id in key for key in well.translation_statuses)


def test_remove_tracked_sample_cleans_description_tracking_metadata() -> None:
    controller = _controller()
    sample = _tracked_sample(controller)
    well = controller.session.current_well
    assert well is not None

    controller.remove(sample.sample_id)

    assert not any(sample.sample_id in key for key in well.authored_field_source_languages)
    assert not any(sample.sample_id in key for key in well.authored_field_revisions)
    assert not any(sample.sample_id in key for key in well.translation_statuses)
