from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from geoworkbench.domain.models import CuttingsSample, Dataset, DatasetKind, DepthDomain
from geoworkbench.domain.translation_status import TranslationState
from geoworkbench.project.cuttings_analysis_tracking_coordinator import (
    CuttingsAnalysisTrackingSources,
)
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.cuttings_tracked_analysis_writer import (
    CuttingsTrackedAnalysisWriter,
)
from geoworkbench.project.session import ProjectSession


def _writer() -> tuple[CuttingsController, CuttingsTrackedAnalysisWriter]:
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
    return CuttingsController(session), CuttingsTrackedAnalysisWriter(session)


def _staged(sample_id: str = "sample-1") -> CuttingsSample:
    sample = CuttingsSample(sample_id, 100.0, 110.0)
    sample.calcite_percent = 20.0
    sample.dolomite_percent = 10.0
    sample.lba_group = 2
    sample.lba_type_id = "oil"
    sample.lba_intensity = 3
    sample.lba_color = "brown"
    sample.lba_distribution = "uniform"
    sample.lba_description_i18n.update(
        {
            "ru": "Равномерное коричневое свечение",
            "kk": "Біркелкі қоңыр люминесценция",
        }
    )
    sample.analysis_interpretation_i18n.update(
        {
            "ru": "Признаки нефтенасыщения подтверждены",
            "kk": "Мұнайға қанығу белгілері расталды",
        }
    )
    return sample


def test_commit_new_sample_applies_model_and_composite_provenance_once() -> None:
    controller, writer = _writer()
    well = controller.session.current_well
    assert well is not None
    staged = _staged()
    baseline_content_revision = well.content_revision

    saved = writer.commit(
        None,
        staged,
        sources=CuttingsAnalysisTrackingSources("ru", "ru"),
    )

    assert saved is not staged
    assert saved.sample_id == staged.sample_id
    assert len(well.cuttings) == 1
    lba_field = f"cuttings/{saved.sample_id}/lba_description"
    interpretation_field = f"cuttings/{saved.sample_id}/analysis_interpretation"
    assert well.authored_field_source_languages[lba_field] == "ru"
    assert well.authored_field_source_languages[interpretation_field] == "ru"
    assert well.translation_statuses[lba_field]["kk"].state is TranslationState.DRAFT
    assert (
        well.translation_statuses[interpretation_field]["kk"].state
        is TranslationState.DRAFT
    )
    assert well.content_revision == baseline_content_revision + 1
    assert well.language_revisions["ru"] == 1
    assert well.language_revisions["kk"] == 1
    assert controller.session.dirty is True


def test_existing_sample_update_is_atomic_when_provenance_plan_is_invalid() -> None:
    controller, writer = _writer()
    original = controller.set_analysis(
        100.0,
        110.0,
        calcite_percent=20.0,
        analysis_interpretation_i18n={"ru": "Исходное заключение"},
    )
    well = controller.session.current_well
    assert well is not None
    controller.session.dirty = False
    before_sample = deepcopy(original)
    before_statuses = deepcopy(well.translation_statuses)
    before_revisions = dict(well.authored_field_revisions)
    staged = deepcopy(original)
    staged.calcite_percent = 25.0
    staged.analysis_interpretation_i18n["ru"] = "Новое заключение"

    with pytest.raises(ValueError):
        writer.commit(
            original,
            staged,
            sources=CuttingsAnalysisTrackingSources(None, "und"),
        )

    assert original == before_sample
    assert well.translation_statuses == before_statuses
    assert well.authored_field_revisions == before_revisions
    assert controller.session.dirty is False


def test_calcimetry_update_stales_only_interpretation_translation() -> None:
    controller, writer = _writer()
    saved = writer.commit(
        None,
        _staged(),
        sources=CuttingsAnalysisTrackingSources("ru", "ru"),
    )
    well = controller.session.current_well
    assert well is not None
    staged = deepcopy(saved)
    staged.calcite_percent = 25.0

    writer.commit(
        saved,
        staged,
        sources=CuttingsAnalysisTrackingSources("ru", "ru"),
    )

    lba_field = f"cuttings/{saved.sample_id}/lba_description"
    interpretation_field = f"cuttings/{saved.sample_id}/analysis_interpretation"
    assert well.translation_statuses[lba_field]["kk"].state is TranslationState.DRAFT
    assert (
        well.translation_statuses[interpretation_field]["kk"].state
        is TranslationState.STALE
    )


def test_resolve_and_commit_inherits_persisted_sources() -> None:
    controller, writer = _writer()
    saved = writer.commit(
        None,
        _staged(),
        sources=CuttingsAnalysisTrackingSources("ru", "ru"),
    )
    staged = deepcopy(saved)
    staged.lba_intensity = 4

    updated = writer.resolve_and_commit(
        saved,
        staged,
        lba_description_source_language=None,
        interpretation_source_language=None,
    )

    assert updated.lba_intensity == 4
    well = controller.session.current_well
    assert well is not None
    lba_field = f"cuttings/{saved.sample_id}/lba_description"
    interpretation_field = f"cuttings/{saved.sample_id}/analysis_interpretation"
    assert well.authored_field_source_languages[lba_field] == "ru"
    assert well.authored_field_source_languages[interpretation_field] == "ru"


def test_repeated_identical_save_is_a_true_noop() -> None:
    controller, writer = _writer()
    saved = writer.commit(
        None,
        _staged(),
        sources=CuttingsAnalysisTrackingSources("ru", "ru"),
    )
    well = controller.session.current_well
    assert well is not None
    controller.session.dirty = False
    before_content_revision = well.content_revision
    before_language_revisions = dict(well.language_revisions)
    before_statuses = deepcopy(well.translation_statuses)
    before_field_revisions = dict(well.authored_field_revisions)

    repeated = writer.resolve_and_commit(
        saved,
        deepcopy(saved),
        lba_description_source_language=None,
        interpretation_source_language=None,
    )

    assert repeated is saved
    assert well.content_revision == before_content_revision
    assert well.language_revisions == before_language_revisions
    assert well.translation_statuses == before_statuses
    assert well.authored_field_revisions == before_field_revisions
    assert controller.session.dirty is False


def test_source_language_change_is_metadata_only_but_still_material() -> None:
    controller, writer = _writer()
    saved = writer.commit(
        None,
        _staged(),
        sources=CuttingsAnalysisTrackingSources("ru", "ru"),
    )
    well = controller.session.current_well
    assert well is not None
    controller.session.dirty = False
    before_content_revision = well.content_revision
    before_language_revisions = dict(well.language_revisions)

    updated = writer.commit(
        saved,
        deepcopy(saved),
        sources=CuttingsAnalysisTrackingSources("kk", "ru"),
    )

    assert updated is saved
    lba_field = f"cuttings/{saved.sample_id}/lba_description"
    assert well.authored_field_source_languages[lba_field] == "kk"
    assert well.content_revision == before_content_revision + 1
    assert well.language_revisions == before_language_revisions
    assert controller.session.dirty is True
