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
            np.array([90.0, 130.0]),
        )
    )
    session.dirty = False
    return CuttingsController(session)


def _analysis_values(*, calcite: float = 20.0) -> dict[str, object]:
    return {
        "calcite_percent": calcite,
        "dolomite_percent": 10.0,
        "lba_group": 2,
        "lba_type_id": "oil",
        "lba_intensity": 3,
        "lba_color": "brown",
        "lba_distribution": "uniform",
        "lba_description_i18n": {
            "ru": "Равномерное коричневое свечение",
            "kk": "Біркелкі қоңыр люминесценция",
        },
        "analysis_interpretation_i18n": {
            "ru": "Признаки нефтенасыщения подтверждены",
            "kk": "Мұнайға қанығу белгілері расталды",
        },
    }


def test_set_analysis_tracks_lba_and_interpretation_through_one_controller_save() -> None:
    controller = _controller()

    sample = controller.set_analysis(
        100.0,
        110.0,
        **_analysis_values(),
        lba_description_source_language="ru",
        analysis_interpretation_source_language="ru",
    )

    well = controller.session.current_well
    assert well is not None
    lba_field = f"cuttings/{sample.sample_id}/lba_description"
    interpretation_field = f"cuttings/{sample.sample_id}/analysis_interpretation"
    assert controller.lba_description_source_language(sample.sample_id) == "ru"
    assert controller.analysis_interpretation_source_language(sample.sample_id) == "ru"
    assert well.translation_statuses[lba_field]["kk"].state is TranslationState.DRAFT
    assert (
        well.translation_statuses[interpretation_field]["kk"].state
        is TranslationState.DRAFT
    )
    assert well.authored_field_revisions[lba_field] == 1
    assert well.authored_field_revisions[interpretation_field] == 1


def test_calcimetry_change_stales_only_interpretation_via_controller() -> None:
    controller = _controller()
    sample = controller.set_analysis(
        100.0,
        110.0,
        **_analysis_values(),
        lba_description_source_language="ru",
        analysis_interpretation_source_language="ru",
    )

    updated = controller.set_analysis(100.0, 110.0, **_analysis_values(calcite=25.0))

    well = controller.session.current_well
    assert well is not None
    assert updated is sample
    lba_field = f"cuttings/{sample.sample_id}/lba_description"
    interpretation_field = f"cuttings/{sample.sample_id}/analysis_interpretation"
    assert well.translation_statuses[lba_field]["kk"].state is TranslationState.DRAFT
    assert (
        well.translation_statuses[interpretation_field]["kk"].state
        is TranslationState.STALE
    )
    assert well.authored_field_revisions[lba_field] == 1
    assert well.authored_field_revisions[interpretation_field] == 1


def test_repeated_tracked_controller_save_inherits_sources_and_is_noop() -> None:
    controller = _controller()
    sample = controller.set_analysis(
        100.0,
        110.0,
        **_analysis_values(),
        lba_description_source_language="ru",
        analysis_interpretation_source_language="ru",
    )
    well = controller.session.current_well
    assert well is not None
    baseline_content_revision = well.content_revision
    baseline_language_revisions = dict(well.language_revisions)
    baseline_statuses = deepcopy(well.translation_statuses)
    baseline_revisions = dict(well.authored_field_revisions)
    controller.session.dirty = False

    same = controller.set_analysis(100.0, 110.0, **_analysis_values())

    assert same is sample
    assert controller.lba_description_source_language(sample.sample_id) == "ru"
    assert controller.analysis_interpretation_source_language(sample.sample_id) == "ru"
    assert well.content_revision == baseline_content_revision
    assert well.language_revisions == baseline_language_revisions
    assert well.translation_statuses == baseline_statuses
    assert well.authored_field_revisions == baseline_revisions
    assert controller.session.dirty is False


def test_invalid_interpretation_source_rolls_back_controller_save_atomically() -> None:
    controller = _controller()
    sample = controller.set_analysis(
        100.0,
        110.0,
        **_analysis_values(),
        lba_description_source_language="ru",
        analysis_interpretation_source_language="ru",
    )
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
        controller.set_analysis(
            100.0,
            110.0,
            **_analysis_values(calcite=30.0),
            analysis_interpretation_source_language="und",
        )

    assert sample == before_sample
    assert well.translation_statuses == before_statuses
    assert well.authored_field_revisions == before_revisions
    assert well.authored_field_source_languages == before_sources
    assert well.content_revision == before_content_revision
    assert well.language_revisions == before_language_revisions
    assert controller.session.dirty is False


def test_remove_clears_description_lba_and_interpretation_provenance() -> None:
    controller = _controller()
    sample = controller.set_analysis(
        100.0,
        110.0,
        **_analysis_values(),
        lba_description_source_language="ru",
        analysis_interpretation_source_language="ru",
    )
    controller.update_description(
        sample.sample_id,
        top_depth=100.0,
        bottom_depth=110.0,
        description="Описание шлама",
        language="ru",
        source_language="ru",
    )
    well = controller.session.current_well
    assert well is not None
    prefix = f"cuttings/{sample.sample_id}/"
    assert any(key.startswith(prefix) for key in well.authored_field_revisions)

    removed = controller.remove(sample.sample_id)

    assert removed is sample
    assert sample not in well.cuttings
    assert not any(key.startswith(prefix) for key in well.translation_statuses)
    assert not any(key.startswith(prefix) for key in well.authored_field_source_languages)
    assert not any(key.startswith(prefix) for key in well.authored_field_revisions)
