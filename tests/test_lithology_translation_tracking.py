from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, LithologyInterval, Well
from geoworkbench.domain.translation_status import TranslationState
from geoworkbench.project.lithology_controller import LithologyController
from geoworkbench.project.session import ProjectSession


FIELD = "lithology/{interval_id}/description"
DEPTH = "lithology/{interval_id}/depth"
LITHOTYPE = "lithology/{interval_id}/lithotype"


def _controller() -> LithologyController:
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
    return LithologyController(session)


def test_tracked_lithology_add_creates_field_and_dependency_revisions() -> None:
    controller = _controller()
    well = controller.session.current_well
    assert well is not None
    revision_before = well.content_revision

    interval = controller.add(
        100.0,
        150.0,
        "sandstone",
        description_i18n={"ru": "Песчаник", "kk": "Құмтас", "en": "Sandstone"},
        source_language="ru",
    )

    field_id = FIELD.format(interval_id=interval.interval_id)
    depth_id = DEPTH.format(interval_id=interval.interval_id)
    lithotype_id = LITHOTYPE.format(interval_id=interval.interval_id)
    assert well.authored_field_source_languages[field_id] == "ru"
    assert well.authored_field_revisions[field_id] == 1
    assert well.authored_field_revisions[depth_id] == 1
    assert well.authored_field_revisions[lithotype_id] == 1
    assert well.translation_statuses[field_id]["kk"].state is TranslationState.DRAFT
    assert well.translation_statuses[field_id]["en"].state is TranslationState.DRAFT
    assert "ru" not in well.translation_statuses[field_id]
    assert well.content_revision == revision_before + 1


def test_translation_edit_keeps_source_revision_and_advances_target_draft() -> None:
    controller = _controller()
    interval = controller.add(
        100.0,
        150.0,
        "sandstone",
        description_i18n={"ru": "Песчаник", "kk": "Құмтас", "en": "Sandstone"},
        source_language="ru",
    )
    well = controller.session.current_well
    assert well is not None
    field_id = FIELD.format(interval_id=interval.interval_id)
    first_status = well.translation_statuses[field_id]["kk"]

    controller.update(
        interval.interval_id,
        top_depth=100.0,
        bottom_depth=150.0,
        lithotype_id="sandstone",
        description_i18n={
            "ru": "Песчаник",
            "kk": "Ұсақ түйірлі құмтас",
            "en": "Sandstone",
        },
        source_language="ru",
    )

    second_status = well.translation_statuses[field_id]["kk"]
    assert well.authored_field_revisions[field_id] == 1
    assert second_status.state is TranslationState.DRAFT
    assert second_status.translation_revision == first_status.translation_revision + 1
    assert well.translation_statuses[field_id]["en"].translation_revision == 1


def test_source_edit_stales_only_unchanged_target_translations() -> None:
    controller = _controller()
    interval = controller.add(
        100.0,
        150.0,
        "sandstone",
        description_i18n={"ru": "Песчаник", "kk": "Құмтас", "en": "Sandstone"},
        source_language="ru",
    )
    well = controller.session.current_well
    assert well is not None
    field_id = FIELD.format(interval_id=interval.interval_id)

    controller.update(
        interval.interval_id,
        top_depth=100.0,
        bottom_depth=150.0,
        lithotype_id="sandstone",
        description_i18n={
            "ru": "Песчаник серый",
            "kk": "Құмтас",
            "en": "Sandstone",
        },
        source_language="ru",
    )

    assert well.authored_field_revisions[field_id] == 2
    assert well.translation_statuses[field_id]["kk"].state is TranslationState.STALE
    assert well.translation_statuses[field_id]["en"].state is TranslationState.STALE


def test_depth_change_stales_only_translations_for_that_interval() -> None:
    controller = _controller()
    first = controller.add(
        100.0,
        140.0,
        "sandstone",
        description_i18n={"ru": "A", "kk": "A kk"},
        source_language="ru",
    )
    second = controller.add(
        150.0,
        190.0,
        "claystone",
        description_i18n={"ru": "B", "kk": "B kk"},
        source_language="ru",
    )
    well = controller.session.current_well
    assert well is not None
    first_field = FIELD.format(interval_id=first.interval_id)
    second_field = FIELD.format(interval_id=second.interval_id)
    first_depth = DEPTH.format(interval_id=first.interval_id)

    controller.update(
        first.interval_id,
        top_depth=100.0,
        bottom_depth=145.0,
        lithotype_id="sandstone",
        description_i18n={"ru": "A", "kk": "A kk"},
        source_language="ru",
    )

    assert well.authored_field_revisions[first_depth] == 2
    assert well.translation_statuses[first_field]["kk"].state is TranslationState.STALE
    assert well.translation_statuses[second_field]["kk"].state is TranslationState.DRAFT


def test_invalid_source_language_save_is_atomic() -> None:
    controller = _controller()
    interval = controller.add(
        100.0,
        150.0,
        "sandstone",
        description_i18n={"ru": "Песчаник", "kk": "Құмтас"},
        source_language="ru",
    )
    well = controller.session.current_well
    assert well is not None
    interval_before = deepcopy(interval)
    statuses_before = deepcopy(well.translation_statuses)
    revisions_before = dict(well.authored_field_revisions)
    sources_before = dict(well.authored_field_source_languages)
    content_revision_before = well.content_revision

    with pytest.raises(ValueError, match="язык оригинала"):
        controller.update(
            interval.interval_id,
            top_depth=110.0,
            bottom_depth=140.0,
            lithotype_id="claystone",
            description_i18n={"kk": "Құмтас"},
            source_language="ru",
        )

    assert interval == interval_before
    assert well.translation_statuses == statuses_before
    assert well.authored_field_revisions == revisions_before
    assert well.authored_field_source_languages == sources_before
    assert well.content_revision == content_revision_before


def test_legacy_lithology_without_source_language_keeps_fallback_unclassified() -> None:
    interval = LithologyInterval(
        "legacy",
        100.0,
        110.0,
        "sandstone",
        description="Legacy authored description",
        description_i18n={"und": "Unclassified authored description"},
    )
    well = Well("well", "Well", lithology=[interval])
    session = ProjectSession()
    session.project.wells[well.well_id] = well
    session.current_well_id = well.well_id
    controller = LithologyController(session)

    controller.update(
        interval.interval_id,
        top_depth=100.0,
        bottom_depth=111.0,
        lithotype_id="sandstone",
        description_i18n={"und": "Unclassified authored description"},
        source_language=None,
    )

    assert interval.description == "Legacy authored description"
    assert interval.description_i18n == {"und": "Unclassified authored description"}
    assert well.authored_field_source_languages == {}
    assert well.translation_statuses == {}


def test_remove_tracked_interval_cleans_translation_metadata() -> None:
    controller = _controller()
    interval = controller.add(
        100.0,
        150.0,
        "sandstone",
        description_i18n={"ru": "Песчаник", "kk": "Құмтас"},
        source_language="ru",
    )
    well = controller.session.current_well
    assert well is not None
    field_id = FIELD.format(interval_id=interval.interval_id)

    controller.remove(interval.interval_id)

    assert field_id not in well.translation_statuses
    assert field_id not in well.authored_field_source_languages
    assert not any(interval.interval_id in key for key in well.authored_field_revisions)
