from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.authored_field_source_language_controller import (
    AuthoredFieldSourceLanguageController,
)
from geoworkbench.project.session import ProjectSession


FIELD_ID = "lithology/interval-1/description"


def _controller() -> AuthoredFieldSourceLanguageController:
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
    return AuthoredFieldSourceLanguageController(session)


def test_set_source_language_is_normalized_isolated_and_idempotent() -> None:
    controller = _controller()
    well = controller.session.current_well
    assert well is not None
    well.translation_statuses = {"other": {}}
    well.authored_field_revisions = {FIELD_ID: 7}
    well.language_revisions = {"ru": 3}
    statuses_before = dict(well.translation_statuses)
    field_revisions_before = dict(well.authored_field_revisions)
    language_revisions_before = dict(well.language_revisions)
    initial_revision = well.content_revision

    assert controller.source_language(FIELD_ID) is None
    assert controller.set_source_language(f"  {FIELD_ID}  ", " RU ") == "ru"
    assert controller.source_language(FIELD_ID) == "ru"
    assert well.authored_field_source_languages == {FIELD_ID: "ru"}
    assert well.content_revision == initial_revision + 1
    assert controller.session.dirty is True
    assert well.translation_statuses == statuses_before
    assert well.authored_field_revisions == field_revisions_before
    assert well.language_revisions == language_revisions_before

    controller.session.dirty = False
    assert controller.set_source_language(FIELD_ID, "ru") == "ru"
    assert well.content_revision == initial_revision + 1
    assert controller.session.dirty is False

    assert controller.set_source_language(FIELD_ID, "en") == "en"
    assert controller.source_language(FIELD_ID) == "en"
    assert well.content_revision == initial_revision + 2
    assert controller.session.dirty is True
    assert well.translation_statuses == statuses_before
    assert well.authored_field_revisions == field_revisions_before
    assert well.language_revisions == language_revisions_before


def test_clear_source_language_changes_only_existing_metadata() -> None:
    controller = _controller()
    well = controller.session.current_well
    assert well is not None
    controller.set_source_language(FIELD_ID, "kk")
    revision = well.content_revision

    controller.session.dirty = False
    assert controller.clear_source_language(FIELD_ID) is True
    assert controller.source_language(FIELD_ID) is None
    assert well.content_revision == revision + 1
    assert controller.session.dirty is True

    controller.session.dirty = False
    revision = well.content_revision
    assert controller.clear_source_language(FIELD_ID) is False
    assert well.content_revision == revision
    assert controller.session.dirty is False


@pytest.mark.parametrize("field_id", ["", "   "])
def test_source_language_rejects_blank_field_id(field_id: str) -> None:
    controller = _controller()

    with pytest.raises(ValueError, match="ID авторского поля"):
        controller.set_source_language(field_id, "ru")


@pytest.mark.parametrize("language", ["de", "und", ""])
def test_source_language_rejects_non_authored_language(language: str) -> None:
    controller = _controller()

    with pytest.raises(ValueError, match="Неподдерживаемый язык содержимого"):
        controller.set_source_language(FIELD_ID, language)


def test_source_language_requires_current_well() -> None:
    controller = AuthoredFieldSourceLanguageController(ProjectSession())

    with pytest.raises(RuntimeError, match="Сначала выберите скважину"):
        controller.source_language(FIELD_ID)
