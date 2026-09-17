from __future__ import annotations

from copy import deepcopy

import pytest

from geoworkbench.domain.models import Project, Well
from geoworkbench.domain.translation_status import TranslationState
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.session import ProjectSession


def _controller() -> CuttingsController:
    well = Well("well", "Well")
    session = ProjectSession(Project("project", "Project", wells={well.well_id: well}))
    session.current_well_id = well.well_id
    session.dirty = False
    return CuttingsController(session)


def _full_values(*, calcite: float = 20.0) -> dict[str, object]:
    return {
        "calcite_percent": calcite,
        "dolomite_percent": 10.0,
        "lba_group": 2,
        "lba_type_id": "oil",
        "lba_intensity": 3,
        "lba_color": "brown",
        "lba_description_i18n": {
            "ru": "Равномерное коричневое свечение",
            "kk": "Біркелкі қоңыр люминесценция",
        },
        "analysis_interpretation_i18n": {
            "ru": "Признаки нефтенасыщения подтверждены",
            "kk": "Мұнайға қанығу белгілері расталды",
        },
        "description_i18n": {
            "ru": "Песчаник мелкозернистый",
            "kk": "Ұсақ түйірлі құмтас",
        },
    }


def _create_tracked_sample(controller: CuttingsController):
    return controller.create_full_sample(
        100.0,
        110.0,
        {"sandstone": 100.0},
        **_full_values(),
        description_source_language="ru",
        lba_description_source_language="ru",
        analysis_interpretation_source_language="ru",
    )


def test_create_full_sample_commits_all_provenance_in_one_revision() -> None:
    controller = _controller()

    sample = _create_tracked_sample(controller)

    well = controller.session.current_well
    assert well is not None
    description_field = f"cuttings/{sample.sample_id}/description"
    lba_field = f"cuttings/{sample.sample_id}/lba_description"
    interpretation_field = f"cuttings/{sample.sample_id}/analysis_interpretation"

    assert controller.description_source_language(sample.sample_id) == "ru"
    assert controller.lba_description_source_language(sample.sample_id) == "ru"
    assert controller.analysis_interpretation_source_language(sample.sample_id) == "ru"
    assert well.translation_statuses[description_field]["kk"].state is TranslationState.DRAFT
    assert well.translation_statuses[lba_field]["kk"].state is TranslationState.DRAFT
    assert (
        well.translation_statuses[interpretation_field]["kk"].state
        is TranslationState.DRAFT
    )
    assert well.content_revision == 1
    assert well.language_revisions["ru"] == 1
    assert well.language_revisions["kk"] == 1
    assert controller.session.dirty is True


def test_full_sample_update_inherits_sources_and_stales_only_interpretation() -> None:
    controller = _controller()
    sample = _create_tracked_sample(controller)
    controller.session.dirty = False

    updated = controller.update_full_sample(
        sample.sample_id,
        top_depth=100.0,
        bottom_depth=110.0,
        components={"sandstone": 100.0},
        **_full_values(calcite=25.0),
    )

    well = controller.session.current_well
    assert well is not None
    description_field = f"cuttings/{sample.sample_id}/description"
    lba_field = f"cuttings/{sample.sample_id}/lba_description"
    interpretation_field = f"cuttings/{sample.sample_id}/analysis_interpretation"

    assert updated is sample
    assert controller.description_source_language(sample.sample_id) == "ru"
    assert controller.lba_description_source_language(sample.sample_id) == "ru"
    assert controller.analysis_interpretation_source_language(sample.sample_id) == "ru"
    assert well.translation_statuses[description_field]["kk"].state is TranslationState.DRAFT
    assert well.translation_statuses[lba_field]["kk"].state is TranslationState.DRAFT
    assert (
        well.translation_statuses[interpretation_field]["kk"].state
        is TranslationState.STALE
    )
    assert controller.session.dirty is True


def test_repeated_tracked_full_sample_update_is_noop() -> None:
    controller = _controller()
    sample = _create_tracked_sample(controller)
    well = controller.session.current_well
    assert well is not None
    baseline_content_revision = well.content_revision
    baseline_language_revisions = dict(well.language_revisions)
    baseline_statuses = deepcopy(well.translation_statuses)
    baseline_revisions = dict(well.authored_field_revisions)
    baseline_sources = dict(well.authored_field_source_languages)
    controller.session.dirty = False

    same = controller.update_full_sample(
        sample.sample_id,
        top_depth=100.0,
        bottom_depth=110.0,
        components={"sandstone": 100.0},
        **_full_values(),
    )

    assert same is sample
    assert well.content_revision == baseline_content_revision
    assert well.language_revisions == baseline_language_revisions
    assert well.translation_statuses == baseline_statuses
    assert well.authored_field_revisions == baseline_revisions
    assert well.authored_field_source_languages == baseline_sources
    assert controller.session.dirty is False


def test_invalid_full_sample_provenance_rolls_back_model_and_metadata() -> None:
    controller = _controller()
    sample = _create_tracked_sample(controller)
    well = controller.session.current_well
    assert well is not None
    before_sample = deepcopy(sample)
    before_statuses = deepcopy(well.translation_statuses)
    before_revisions = dict(well.authored_field_revisions)
    before_sources = dict(well.authored_field_source_languages)
    before_content_revision = well.content_revision
    before_language_revisions = dict(well.language_revisions)
    controller.session.dirty = False

    with pytest.raises(ValueError):
        controller.update_full_sample(
            sample.sample_id,
            top_depth=100.0,
            bottom_depth=110.0,
            components={"sandstone": 100.0},
            **_full_values(calcite=30.0),
            analysis_interpretation_source_language="und",
        )

    assert sample == before_sample
    assert well.translation_statuses == before_statuses
    assert well.authored_field_revisions == before_revisions
    assert well.authored_field_source_languages == before_sources
    assert well.content_revision == before_content_revision
    assert well.language_revisions == before_language_revisions
    assert controller.session.dirty is False
