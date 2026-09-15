from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.domain.translation_status import TranslationState, TranslationStatusError
from geoworkbench.domain.translation_readiness import TranslatableField
from geoworkbench.project.authored_field_source_language_controller import (
    AuthoredFieldSourceLanguageController,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.translation_status_controller import TranslationStatusController


FIELD_ID = "lithology/interval-1/description"


def _controller() -> TranslationStatusController:
    session = ProjectSession()
    session.add_dataset(
        Dataset(
            "dataset",
            "Well A",
            DatasetKind.GTI,
            DepthDomain.MD,
            np.array([100.0, 200.0]),
        )
    )
    session.dirty = False
    return TranslationStatusController(session)


def test_controller_applies_review_with_revision_and_undo_redo() -> None:
    controller = _controller()
    well = controller.session.current_well
    assert well is not None
    initial_revision = well.content_revision

    draft = controller.begin_draft(
        field_id=FIELD_ID,
        language="kk",
        source_language="ru",
        source_revision=4,
        dependency_revisions={"interval-1/depth": 2},
    )
    reviewed = controller.review(
        field_id=FIELD_ID,
        language="kk",
        current_source_revision=4,
        current_dependency_revisions={"interval-1/depth": 2},
    )

    assert draft.state is TranslationState.DRAFT
    assert reviewed.state is TranslationState.REVIEWED
    assert well.content_revision == initial_revision + 2
    assert controller.session.dirty is True

    controller.undo()
    assert controller.status(FIELD_ID, "kk") == draft
    assert well.content_revision == initial_revision + 1
    controller.undo()
    assert controller.status(FIELD_ID, "kk") is None
    assert well.content_revision == initial_revision

    controller.redo()
    controller.redo()
    assert controller.status(FIELD_ID, "kk") == reviewed
    assert well.content_revision == initial_revision + 2


def test_failed_review_is_atomic_and_does_not_enter_history() -> None:
    controller = _controller()
    controller.begin_draft(
        field_id=FIELD_ID,
        language="en",
        source_language="ru",
        source_revision=1,
    )
    well = controller.session.current_well
    assert well is not None
    before = dict(well.translation_statuses)
    revision = well.content_revision

    with pytest.raises(TranslationStatusError, match="Исходный текст изменился"):
        controller.review(
            field_id=FIELD_ID,
            language="en",
            current_source_revision=2,
        )

    assert well.translation_statuses == before
    assert well.content_revision == revision
    controller.undo()
    assert controller.can_undo is False


def test_review_rejects_changed_source_language_from_well_metadata() -> None:
    controller = _controller()
    source_languages = AuthoredFieldSourceLanguageController(controller.session)
    source_languages.set_source_language(FIELD_ID, "ru")
    controller.begin_draft(
        field_id=FIELD_ID,
        language="kk",
        source_language="ru",
        source_revision=0,
    )
    well = controller.session.current_well
    assert well is not None
    source_languages.set_source_language(FIELD_ID, "en")
    before = dict(well.translation_statuses)
    revision = well.content_revision

    with pytest.raises(TranslationStatusError, match="Язык исходного текста изменился"):
        controller.review(
            field_id=FIELD_ID,
            language="kk",
            current_source_revision=0,
        )

    assert well.translation_statuses == before
    assert controller.status(FIELD_ID, "kk").state is TranslationState.DRAFT
    assert well.content_revision == revision


def test_invalidation_is_noop_for_unrelated_change_and_records_related_change() -> None:
    controller = _controller()
    controller.begin_draft(
        field_id=FIELD_ID,
        language="kk",
        source_language="ru",
        source_revision=2,
        dependency_revisions={"interval-1/depth": 7},
    )
    well = controller.session.current_well
    assert well is not None
    revision = well.content_revision

    assert (
        controller.invalidate_changed_revisions(
            source_revisions={"lithology/interval-2/description": 3},
            dependency_revisions={"interval-2/depth": 8},
        )
        == 0
    )
    assert well.content_revision == revision
    assert (
        controller.invalidate_changed_revisions(
            source_revisions={},
            dependency_revisions={"interval-1/depth": 8},
        )
        == 1
    )
    assert controller.status(FIELD_ID, "kk").state is TranslationState.STALE
    assert well.content_revision == revision + 1


def test_undo_is_blocked_after_external_status_change() -> None:
    controller = _controller()
    controller.mark_missing(
        field_id=FIELD_ID,
        language="en",
        source_language="ru",
        source_revision=1,
    )
    well = controller.session.current_well
    assert well is not None
    well.content_revision += 1

    with pytest.raises(RuntimeError, match="вне истории"):
        controller.undo()


def test_authored_field_change_stales_only_linked_translation_and_is_undoable() -> None:
    controller = _controller()
    assert controller.record_authored_field_change(FIELD_ID) == 1
    controller.begin_draft(
        field_id=FIELD_ID,
        language="kk",
        source_language="ru",
        source_revision=1,
    )
    other_field = "lithology/interval-2/description"
    controller.begin_draft(
        field_id=other_field,
        language="kk",
        source_language="ru",
        source_revision=1,
    )

    assert controller.record_authored_field_change(FIELD_ID) == 2
    assert controller.status(FIELD_ID, "kk").state is TranslationState.STALE
    assert controller.status(other_field, "kk").state is TranslationState.DRAFT
    assert controller.authored_field_revision(FIELD_ID) == 2

    controller.undo()
    assert controller.status(FIELD_ID, "kk").state is TranslationState.DRAFT
    assert controller.authored_field_revision(FIELD_ID) == 1
    controller.redo()
    assert controller.status(FIELD_ID, "kk").state is TranslationState.STALE
    assert controller.authored_field_revision(FIELD_ID) == 2


def test_controller_readiness_is_range_aware_and_read_only() -> None:
    controller = _controller()
    controller.begin_draft(
        field_id=FIELD_ID,
        language="kk",
        source_language="ru",
        source_revision=0,
    )
    well = controller.session.current_well
    assert well is not None
    revision = well.content_revision
    dirty = controller.session.dirty

    summary = controller.readiness(
        [
            TranslatableField(FIELD_ID, "Описание", 100.0, 110.0),
            TranslatableField("lithology/interval-2/description", "Вне диапазона", 120.0, 130.0),
        ],
        target_languages=["kk", "en"],
        depth_range=(100.0, 115.0),
    )

    assert summary.total_required == 2
    assert summary.draft_count == 1
    assert summary.missing_count == 1
    assert well.content_revision == revision
    assert controller.session.dirty is dirty


def test_controller_readiness_uses_current_source_language_without_mutation() -> None:
    controller = _controller()
    controller.begin_draft(
        field_id=FIELD_ID,
        language="kk",
        source_language="ru",
        source_revision=0,
    )
    well = controller.session.current_well
    assert well is not None
    well.authored_field_source_languages[FIELD_ID] = "en"
    revision = well.content_revision
    dirty = controller.session.dirty
    saved_status = controller.status(FIELD_ID, "kk")

    summary = controller.readiness(
        [TranslatableField(FIELD_ID, "Описание", 100.0, 110.0)],
        target_languages=["kk"],
    )

    assert summary.total_required == 1
    assert summary.stale_count == 1
    assert summary.items[0].state is TranslationState.STALE
    assert controller.status(FIELD_ID, "kk") == saved_status
    assert well.content_revision == revision
    assert controller.session.dirty is dirty
