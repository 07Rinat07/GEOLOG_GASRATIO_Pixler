from copy import deepcopy

import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.domain.translation_status import TranslationState
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.cuttings_analysis_tracking_coordinator import (
    CuttingsAnalysisTrackingCoordinator,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.translation_status_controller import TranslationStatusController
from geoworkbench.project.well_translation_readiness_controller import (
    WellTranslationReadinessController,
)
from geoworkbench.storage.package_project_repository import PackageProjectRepository
from geoworkbench.storage.project_codec import ProjectDocument


LANGUAGES = ("ru", "kk", "en")
FIELDS = ("description", "lba_description", "analysis_interpretation")


def _controller():
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
    return CuttingsController(session)


def _reviewed_sample(controller, source_language, fields, top=100.0):
    values = {}
    for field in fields:
        values[f"{field}_i18n"] = {language: f"{field} {language}" for language in LANGUAGES}
        values[f"{field}_source_language"] = source_language
    sample = controller.create_full_sample(
        top,
        top + 10.0,
        {"sandstone": 100.0},
        lba_group=2,
        calcite_percent=20.0,
        **values,
    )
    reviewer = TranslationStatusController(controller.session)
    for field in fields:
        for language in LANGUAGES:
            if language != source_language:
                reviewer.review_current(
                    field_id=f"cuttings/{sample.sample_id}/{field}", language=language
                )
    return sample


def _edit_depth(controller, sample, editor, top, bottom):
    if editor == "composition":
        controller.update_composition(
            sample.sample_id,
            top_depth=top,
            bottom_depth=bottom,
            components={"sandstone": 100.0},
        )
    else:
        source = controller.description_source_language(sample.sample_id)
        controller.update_description(
            sample.sample_id,
            top_depth=top,
            bottom_depth=bottom,
            description=sample.description_i18n.get(source) if source else sample.description,
            language=source,
        )


@pytest.mark.parametrize("editor", ["composition", "description"])
@pytest.mark.parametrize("source_language", LANGUAGES)
@pytest.mark.parametrize("fields", [FIELDS, ("lba_description",), ("analysis_interpretation",)])
def test_sample_depth_edit_stales_all_affected_translations_and_roundtrips(
    tmp_path,
    source_language,
    fields,
    editor,
):
    controller = _controller()
    sample = _reviewed_sample(controller, source_language, fields)
    well = controller.session.current_well
    before = deepcopy(sample)
    statuses = deepcopy(well.translation_statuses)
    # Adding a later interval must preserve the already reviewed translations.
    neighbor = _reviewed_sample(controller, source_language, fields, top=150.0)
    for field_id, translations in statuses.items():
        assert well.translation_statuses[field_id] == translations
    neighbor_statuses = deepcopy(well.translation_statuses)
    revisions = dict(well.authored_field_revisions)
    language_revisions = dict(well.language_revisions)
    content_revision = well.content_revision
    controller.session.dirty = False

    _edit_depth(controller, sample, editor, 101.0, 111.0)

    expected = deepcopy(before)
    expected.top_depth, expected.bottom_depth = 101.0, 111.0
    assert sample == expected
    assert well.content_revision == content_revision + 1
    assert well.language_revisions == language_revisions
    assert controller.session.dirty
    for field in fields:
        field_id = f"cuttings/{sample.sample_id}/{field}"
        assert well.authored_field_revisions[field_id] == revisions[field_id]
        assert (
            well.translation_statuses[field_id][source_language].state is TranslationState.REVIEWED
        )
        for language in set(LANGUAGES) - {source_language}:
            assert well.translation_statuses[field_id][language].state is TranslationState.STALE
        neighbor_id = f"cuttings/{neighbor.sample_id}/{field}"
        assert well.translation_statuses[neighbor_id] == neighbor_statuses[neighbor_id]

    repository = PackageProjectRepository()
    path = tmp_path / "translations.geologpkg"
    repository.save(ProjectDocument(project=controller.session.project), path)
    restored = repository.load(path)
    session = ProjectSession(project=restored.project, current_well_id=well.well_id)
    assert session.current_well.translation_statuses == well.translation_statuses
    assert session.current_well.authored_field_revisions == well.authored_field_revisions
    assert (
        session.current_well.authored_field_source_languages == well.authored_field_source_languages
    )
    assert CuttingsController(session).get(sample.sample_id) == sample
    readiness = WellTranslationReadinessController(session)
    summary = readiness.summarize(target_languages=LANGUAGES, depth_range=(101.0, 111.0))
    assert summary.stale_count == len(fields) * 2
    assert {item.field.field_id for item in summary.items} == {
        f"cuttings/{sample.sample_id}/{field}" for field in fields
    }
    assert readiness.summarize(target_languages=LANGUAGES, depth_range=(150.0, 160.0)).is_ready
    with pytest.raises(ValueError):
        TranslationStatusController(session).review_current(
            field_id=f"cuttings/{sample.sample_id}/{fields[-1]}",
            language=next(language for language in LANGUAGES if language != source_language),
        )


@pytest.mark.parametrize("source_language", LANGUAGES)
def test_composition_only_change_keeps_analysis_translations_reviewed(source_language):
    controller = _controller()
    sample = _reviewed_sample(controller, source_language, FIELDS)
    well = controller.session.current_well
    before = deepcopy(well.translation_statuses)
    controller.update_composition(
        sample.sample_id,
        top_depth=100.0,
        bottom_depth=110.0,
        components={"sandstone": 70.0, "claystone": 30.0},
    )
    for field in ("lba_description", "analysis_interpretation"):
        field_id = f"cuttings/{sample.sample_id}/{field}"
        assert well.translation_statuses[field_id] == before[field_id]
    for language in set(LANGUAGES) - {source_language}:
        assert (
            well.translation_statuses[f"cuttings/{sample.sample_id}/description"][language].state
            is TranslationState.STALE
        )


@pytest.mark.parametrize("editor", ["composition", "description"])
def test_failed_analysis_plan_does_not_partially_move_sample(monkeypatch, editor):
    controller = _controller()
    sample = _reviewed_sample(controller, "ru", FIELDS)
    well = controller.session.current_well
    before = deepcopy(sample)
    statuses = deepcopy(well.translation_statuses)
    revisions = dict(well.authored_field_revisions)
    sources = dict(well.authored_field_source_languages)
    content_revision = well.content_revision
    language_revisions = dict(well.language_revisions)
    controller.session.dirty = False

    def reject_plan(*args, **kwargs):
        raise ValueError("Analysis tracking validation failed")

    monkeypatch.setattr(CuttingsAnalysisTrackingCoordinator, "plan", reject_plan)
    with pytest.raises(ValueError, match="Analysis tracking validation failed"):
        _edit_depth(controller, sample, editor, 101.0, 111.0)
    assert sample == before
    assert well.translation_statuses == statuses
    assert well.authored_field_revisions == revisions
    assert well.authored_field_source_languages == sources
    assert well.content_revision == content_revision
    assert well.language_revisions == language_revisions
    assert controller.session.dirty is False


@pytest.mark.parametrize("editor", ["composition", "description"])
def test_unchanged_sample_edit_preserves_reviewed_status_and_clean_session(editor):
    controller = _controller()
    sample = _reviewed_sample(controller, "ru", FIELDS)
    well = controller.session.current_well
    statuses = deepcopy(well.translation_statuses)
    revisions = dict(well.authored_field_revisions)
    content_revision = well.content_revision
    controller.session.dirty = False
    _edit_depth(controller, sample, editor, 100.0, 110.0)
    assert well.translation_statuses == statuses
    assert well.authored_field_revisions == revisions
    assert well.content_revision == content_revision
    assert controller.session.dirty is False


@pytest.mark.parametrize("source_language", LANGUAGES)
def test_description_text_edit_stales_only_description_translations(source_language):
    controller = _controller()
    sample = _reviewed_sample(controller, source_language, FIELDS)
    well = controller.session.current_well
    statuses = deepcopy(well.translation_statuses)
    controller.update_description(
        sample.sample_id,
        top_depth=100.0,
        bottom_depth=110.0,
        description="Updated source description",
        language=source_language,
    )
    for field in ("lba_description", "analysis_interpretation"):
        field_id = f"cuttings/{sample.sample_id}/{field}"
        assert well.translation_statuses[field_id] == statuses[field_id]
    for language in set(LANGUAGES) - {source_language}:
        assert (
            well.translation_statuses[f"cuttings/{sample.sample_id}/description"][language].state
            is TranslationState.STALE
        )
        assert sample.description_i18n[language] == f"description {language}"


@pytest.mark.parametrize("language", [None, *LANGUAGES])
def test_untracked_description_edit_preserves_analysis_provenance(language):
    controller = _controller()
    sample = _reviewed_sample(controller, "ru", ("lba_description", "analysis_interpretation"))
    well = controller.session.current_well
    statuses = deepcopy(well.translation_statuses)
    controller.update_description(
        sample.sample_id,
        top_depth=100.0,
        bottom_depth=110.0,
        description="Legacy author text",
        language=language,
    )
    assert controller.description_source_language(sample.sample_id) is None
    assert well.translation_statuses == statuses
    if language is None:
        assert sample.description == "Legacy author text"
        assert sample.description_i18n == {}
    else:
        assert sample.description_i18n == {language: "Legacy author text"}


def test_invalid_description_wrap_preserves_untracked_sample_atomically():
    controller = _controller()
    sample = controller.create_full_sample(
        100.0,
        110.0,
        {"sandstone": 100.0},
        description="Legacy text",
    )
    before = deepcopy(sample)
    well = controller.session.current_well
    language_revisions = dict(well.language_revisions)
    content_revision = well.content_revision
    controller.session.dirty = False
    with pytest.raises(ValueError):
        controller.update_description(
            sample.sample_id,
            top_depth=101.0,
            bottom_depth=111.0,
            description="Changed",
            language="ru",
            description_word_wrap="invalid",
        )
    assert sample == before
    assert well.content_revision == content_revision
    assert well.language_revisions == language_revisions
    assert controller.session.dirty is False
