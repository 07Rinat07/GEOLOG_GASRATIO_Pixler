from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.domain.translation_status import TranslationState, TranslationStatusError
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
