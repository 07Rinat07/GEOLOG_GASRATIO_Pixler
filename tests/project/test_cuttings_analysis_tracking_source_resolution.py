from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.cuttings_analysis_tracking_coordinator import (
    CuttingsAnalysisTrackingCoordinator,
)
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.session import ProjectSession


def _controller() -> tuple[CuttingsController, CuttingsAnalysisTrackingCoordinator]:
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
    return CuttingsController(session), CuttingsAnalysisTrackingCoordinator(session)


def test_new_sample_uses_only_explicit_source_languages() -> None:
    _, coordinator = _controller()

    sources = coordinator.resolve_sources(
        None,
        lba_description_source_language="kk",
        interpretation_source_language=None,
    )

    assert sources.lba_description == "kk"
    assert sources.interpretation is None
    assert sources.tracked is True


def test_existing_sample_inherits_persisted_sources_when_not_explicit() -> None:
    controller, coordinator = _controller()
    sample = controller.set_analysis(
        100.0,
        110.0,
        lba_group=2,
        lba_intensity=3,
        lba_description_i18n={"ru": "Свечение", "kk": "Люминесценция"},
        analysis_interpretation_i18n={"ru": "Заключение", "en": "Conclusion"},
    )
    plan = coordinator.plan(
        None,
        sample,
        lba_description_source_language="ru",
        interpretation_source_language="ru",
    )
    coordinator.apply(plan)

    sources = coordinator.resolve_sources(
        sample.sample_id,
        lba_description_source_language=None,
        interpretation_source_language=None,
    )

    assert sources.lba_description == "ru"
    assert sources.interpretation == "ru"
    assert sources.tracked is True


def test_explicit_source_overrides_only_requested_field() -> None:
    controller, coordinator = _controller()
    sample = controller.set_analysis(
        100.0,
        110.0,
        lba_group=2,
        lba_intensity=3,
        lba_description_i18n={"ru": "Свечение", "kk": "Люминесценция"},
        analysis_interpretation_i18n={"ru": "Заключение", "en": "Conclusion"},
    )
    plan = coordinator.plan(
        None,
        sample,
        lba_description_source_language="ru",
        interpretation_source_language="ru",
    )
    coordinator.apply(plan)

    sources = coordinator.resolve_sources(
        sample.sample_id,
        lba_description_source_language="kk",
        interpretation_source_language=None,
    )

    assert sources.lba_description == "kk"
    assert sources.interpretation == "ru"


def test_untracked_existing_sample_remains_untracked_without_explicit_sources() -> None:
    controller, coordinator = _controller()
    sample = controller.set_analysis(100.0, 110.0, calcite_percent=15.0)

    sources = coordinator.resolve_sources(
        sample.sample_id,
        lba_description_source_language=None,
        interpretation_source_language=None,
    )

    assert sources.lba_description is None
    assert sources.interpretation is None
    assert sources.tracked is False
