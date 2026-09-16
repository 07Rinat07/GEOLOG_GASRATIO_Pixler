from copy import deepcopy

import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.domain.stratigraphy_description_tracking import (
    StratigraphyDescriptionTrackingWorkflow,
)
from geoworkbench.domain.translation_status import TranslationState
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.stratigraphy_controller import StratigraphyController


def _controller() -> StratigraphyController:
    session = ProjectSession()
    session.add_dataset(
        Dataset("dataset", "Well", DatasetKind.GTI, DepthDomain.MD, np.array([100.0, 300.0]))
    )
    session.dirty = False
    return StratigraphyController(session)


def test_stratigraphy_crud_allows_nested_different_ranks() -> None:
    controller = _controller()
    period = controller.add(
        100.0,
        300.0,
        "K",
        rank="System / Period",
        name="Cretaceous",
        color="#7fc64e",
    )
    stage = controller.add(
        150.0,
        200.0,
        "K1a",
        rank="Stage / Age",
        name="Albian",
        description="Reservoir interval",
        text_orientation="vertical_bottom_to_top",
        text_position="top",
    )

    assert controller.available() == (period, stage)
    controller.update(
        stage.interval_id,
        top_depth=155.0,
        bottom_depth=205.0,
        code="K1a",
        rank="Stage / Age",
        name="Albian",
        color="#abcdef",
        description="Updated",
        text_orientation="vertical_top_to_bottom",
        text_position="bottom",
    )
    assert stage.top_depth == 155.0
    assert stage.color == "#abcdef"
    assert stage.text_orientation == "vertical_top_to_bottom"
    assert stage.text_position == "bottom"
    assert controller.remove(period.interval_id) is period
    assert controller.session.dirty is True


def test_stratigraphy_rejects_overlap_within_same_rank_and_invalid_values() -> None:
    controller = _controller()
    controller.add(100.0, 180.0, "K1", rank="Series / Epoch")

    with pytest.raises(ValueError, match="того же ранга"):
        controller.add(170.0, 200.0, "K2", rank="Series / Epoch")
    with pytest.raises(ValueError, match="диапазон"):
        controller.add(90.0, 110.0, "K0", rank="Stage / Age")
    with pytest.raises(ValueError, match="#RRGGBB"):
        controller.add(200.0, 250.0, "K3", color="green")
    with pytest.raises(ValueError, match="меньше"):
        controller.add(250.0, 250.0, "K4")


def test_stratigraphy_rejects_unknown_text_presentation() -> None:
    controller = _controller()
    with pytest.raises(ValueError, match="направление текста"):
        controller.add(100.0, 120.0, "K1", text_orientation="diagonal")
    with pytest.raises(ValueError, match="положение текста"):
        controller.add(120.0, 140.0, "K2", text_position="outside")


def test_stratigraphy_saves_all_localized_texts_atomically() -> None:
    controller = _controller()
    interval = controller.add(
        100.0,
        180.0,
        "K1",
        rank="Series / Epoch",
        name_i18n={"ru": "Нижний мел", "kk": "Төменгі бор", "en": "Lower Cretaceous"},
        description_i18n={"ru": "Коллектор", "kk": "Коллектор", "en": "Reservoir"},
    )

    assert interval.name_i18n["kk"] == "Төменгі бор"
    assert interval.name == "Нижний мел"
    controller.update(
        interval.interval_id,
        top_depth=110.0,
        bottom_depth=190.0,
        code="K1 updated",
        rank="Series / Epoch",
        name_i18n={"kk": "Төменгі бор", "en": "Lower Cretaceous"},
        description_i18n={"en": "Updated reservoir"},
    )

    assert interval.name is None
    assert interval.description is None
    assert interval.name_i18n == {"kk": "Төменгі бор", "en": "Lower Cretaceous"}


def test_invalid_localized_stratigraphy_update_does_not_mutate_interval() -> None:
    controller = _controller()
    interval = controller.add(100.0, 180.0, "K1", name="Legacy")

    with pytest.raises(ValueError, match="язык"):
        controller.update(
            interval.interval_id,
            top_depth=120.0,
            bottom_depth=200.0,
            code="changed",
            name_i18n={"invalid": "Broken"},
        )

    assert interval.top_depth == 100.0
    assert interval.bottom_depth == 180.0
    assert interval.code == "K1"
    assert interval.name == "Legacy"


def test_tracked_stratigraphy_add_commits_provenance_once() -> None:
    controller = _controller()
    well = controller.session.current_well
    assert well is not None
    before_content_revision = well.content_revision
    before_language_revisions = dict(well.language_revisions)

    interval = controller.add(
        100.0,
        180.0,
        "K1",
        rank="Series / Epoch",
        description_i18n={"ru": "Коллектор", "kk": "Коллектор"},
        description_source_language="ru",
    )

    field_id = StratigraphyDescriptionTrackingWorkflow.field_id(interval.interval_id)
    depth_id = StratigraphyDescriptionTrackingWorkflow.depth_dependency_id(interval.interval_id)
    classification_id = StratigraphyDescriptionTrackingWorkflow.classification_dependency_id(
        interval.interval_id
    )
    assert controller.description_source_language(interval.interval_id) == "ru"
    assert well.content_revision == before_content_revision + 1
    assert well.language_revisions.get("ru", 0) == before_language_revisions.get("ru", 0) + 1
    assert well.language_revisions.get("kk", 0) == before_language_revisions.get("kk", 0) + 1
    assert well.authored_field_revisions[field_id] == 1
    assert well.authored_field_revisions[depth_id] == 1
    assert well.authored_field_revisions[classification_id] == 1
    assert well.authored_field_source_languages[field_id] == "ru"
    assert well.translation_statuses[field_id]["ru"].state is TranslationState.REVIEWED
    assert well.translation_statuses[field_id]["kk"].state is TranslationState.DRAFT
    assert well.translation_statuses[field_id]["en"].state is TranslationState.MISSING


def test_tracked_stratigraphy_context_change_stales_target_once() -> None:
    controller = _controller()
    well = controller.session.current_well
    assert well is not None
    interval = controller.add(
        100.0,
        180.0,
        "K1",
        rank="Series / Epoch",
        description_i18n={"ru": "Коллектор", "kk": "Коллектор"},
        description_source_language="ru",
    )
    field_id = StratigraphyDescriptionTrackingWorkflow.field_id(interval.interval_id)
    depth_id = StratigraphyDescriptionTrackingWorkflow.depth_dependency_id(interval.interval_id)
    classification_id = StratigraphyDescriptionTrackingWorkflow.classification_dependency_id(
        interval.interval_id
    )
    source_revision = well.authored_field_revisions[field_id]
    depth_revision = well.authored_field_revisions[depth_id]
    classification_revision = well.authored_field_revisions[classification_id]
    before_content_revision = well.content_revision

    controller.update(
        interval.interval_id,
        top_depth=110.0,
        bottom_depth=190.0,
        code="K1-updated",
        rank="Series / Epoch",
        description_i18n={"ru": "Коллектор", "kk": "Коллектор"},
    )

    assert well.content_revision == before_content_revision + 1
    assert well.authored_field_revisions[field_id] == source_revision
    assert well.authored_field_revisions[depth_id] == depth_revision + 1
    assert well.authored_field_revisions[classification_id] == classification_revision + 1
    assert well.translation_statuses[field_id]["ru"].state is TranslationState.REVIEWED
    assert well.translation_statuses[field_id]["kk"].state is TranslationState.STALE


def test_tracked_stratigraphy_source_change_failure_is_atomic() -> None:
    controller = _controller()
    well = controller.session.current_well
    assert well is not None
    interval = controller.add(
        100.0,
        180.0,
        "K1",
        rank="Series / Epoch",
        description_i18n={"ru": "Коллектор", "kk": "Коллектор"},
        description_source_language="ru",
    )
    before_interval = deepcopy(interval)
    before_statuses = deepcopy(well.translation_statuses)
    before_revisions = dict(well.authored_field_revisions)
    before_sources = dict(well.authored_field_source_languages)
    before_language_revisions = dict(well.language_revisions)
    before_content_revision = well.content_revision

    with pytest.raises(ValueError, match="язык оригинала"):
        controller.update(
            interval.interval_id,
            top_depth=120.0,
            bottom_depth=200.0,
            code="K1-changed",
            rank="Stage / Age",
            description_i18n={"ru": "Коллектор", "kk": "Коллектор"},
            description_source_language="en",
        )

    assert interval == before_interval
    assert well.translation_statuses == before_statuses
    assert well.authored_field_revisions == before_revisions
    assert well.authored_field_source_languages == before_sources
    assert well.language_revisions == before_language_revisions
    assert well.content_revision == before_content_revision


def test_remove_tracked_stratigraphy_cleans_description_metadata() -> None:
    controller = _controller()
    well = controller.session.current_well
    assert well is not None
    interval = controller.add(
        100.0,
        180.0,
        "K1",
        description_i18n={"ru": "Коллектор"},
        description_source_language="ru",
    )
    revision_ids = {
        StratigraphyDescriptionTrackingWorkflow.field_id(interval.interval_id),
        StratigraphyDescriptionTrackingWorkflow.depth_dependency_id(interval.interval_id),
        StratigraphyDescriptionTrackingWorkflow.classification_dependency_id(interval.interval_id),
    }

    controller.remove(interval.interval_id)

    assert all(revision_id not in well.authored_field_revisions for revision_id in revision_ids)
    assert all(revision_id not in well.authored_field_source_languages for revision_id in revision_ids)
    assert all(revision_id not in well.translation_statuses for revision_id in revision_ids)
