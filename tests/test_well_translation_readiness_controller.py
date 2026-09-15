from __future__ import annotations

from copy import deepcopy

import numpy as np

from geoworkbench.domain.models import (
    CuttingsSample,
    Dataset,
    DatasetKind,
    DepthDomain,
    InterpretationInterval,
    LithologyInterval,
    StratigraphyInterval,
    WellInterpretation,
)
from geoworkbench.domain.translation_status import TranslationState, TranslationStatus
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.translation_field_catalog import WellTranslationFieldCatalog
from geoworkbench.project.well_translation_readiness_controller import (
    WellTranslationReadinessController,
)


def _session() -> ProjectSession:
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
    return session


def test_catalog_projects_real_multilingual_fields_and_skips_empty_optional_text() -> None:
    session = _session()
    well = session.current_well
    assert well is not None

    well.lithology.append(
        LithologyInterval(
            "lith-1",
            100.0,
            110.0,
            "sandstone",
            description_i18n={"ru": "Песчаник", "kk": "Құмтас"},
        )
    )
    well.cuttings.append(
        CuttingsSample(
            "sample-1",
            110.0,
            120.0,
            description_i18n={"ru": "Описание шлама"},
        )
    )
    well.stratigraphy.append(
        StratigraphyInterval(
            "strat-1",
            120.0,
            130.0,
            "K1",
            name_i18n={"ru": "Апт"},
        )
    )
    interpretation = WellInterpretation(
        "interp-1",
        "Объект A",
        name_i18n={"ru": "Объект A"},
    )
    interpretation.intervals.append(
        InterpretationInterval(
            "zone-1",
            130.0,
            140.0,
            "reservoir",
            "Пласт A",
            label_i18n={"ru": "Пласт A"},
        )
    )
    well.interpretations[interpretation.interpretation_id] = interpretation

    fields = WellTranslationFieldCatalog.fields(well)
    by_id = {field.field_id: field for field in fields}

    assert set(by_id) == {
        "lithology/lith-1/description",
        "cuttings/sample-1/description",
        "stratigraphy/strat-1/name",
        "interpretation/interp-1/name",
        "interpretation/interp-1/interval/zone-1/label",
    }
    assert by_id["lithology/lith-1/description"].top_depth == 100.0
    assert by_id["cuttings/sample-1/description"].bottom_depth == 120.0
    assert by_id["interpretation/interp-1/name"].top_depth is None
    assert "cuttings/sample-1/lba_description" not in by_id
    assert "stratigraphy/strat-1/description" not in by_id


def test_catalog_keeps_legacy_authored_text_without_promoting_fallback_language() -> None:
    session = _session()
    well = session.current_well
    assert well is not None
    well.lithology.append(
        LithologyInterval(
            "legacy",
            100.0,
            110.0,
            "sandstone",
            description="Legacy authored text",
        )
    )

    fields = WellTranslationFieldCatalog.fields(well)

    assert [field.field_id for field in fields] == ["lithology/legacy/description"]
    assert well.lithology[0].description_i18n == {}


def test_current_well_readiness_is_range_aware_and_does_not_mutate_project() -> None:
    session = _session()
    well = session.current_well
    assert well is not None
    well.lithology.extend(
        [
            LithologyInterval(
                "inside",
                100.0,
                110.0,
                "sandstone",
                description_i18n={"ru": "Песчаник"},
            ),
            LithologyInterval(
                "outside",
                150.0,
                160.0,
                "shale",
                description_i18n={"ru": "Аргиллит"},
            ),
        ]
    )
    interpretation = WellInterpretation(
        "interp",
        "Основная интерпретация",
        name_i18n={"ru": "Основная интерпретация"},
    )
    well.interpretations[interpretation.interpretation_id] = interpretation

    field_id = "lithology/inside/description"
    dependency_id = "lithology/inside/depth"
    well.translation_statuses[field_id] = {
        "kk": TranslationStatus(
            state=TranslationState.REVIEWED,
            source_language="ru",
            source_revision=3,
            translation_revision=2,
            dependency_revisions={dependency_id: 4},
        )
    }
    well.authored_field_revisions[field_id] = 3
    well.authored_field_revisions[dependency_id] = 5

    controller = WellTranslationReadinessController(session)
    statuses_before = deepcopy(well.translation_statuses)
    revisions_before = dict(well.authored_field_revisions)
    content_revision_before = well.content_revision
    dirty_before = session.dirty

    summary = controller.summarize(
        target_languages=["kk"],
        depth_range=(100.0, 120.0),
    )

    # The interval translation is stale because its depth dependency changed.
    # The interpretation name is global and is therefore still included for a
    # selected depth range, where its absent status remains missing.
    assert summary.total_required == 2
    assert summary.stale_count == 1
    assert summary.missing_count == 1
    assert {item.state for item in summary.items} == {
        TranslationState.STALE,
        TranslationState.MISSING,
    }
    assert well.translation_statuses == statuses_before
    assert well.authored_field_revisions == revisions_before
    assert well.content_revision == content_revision_before
    assert session.dirty is dirty_before


def test_readiness_requires_current_well() -> None:
    controller = WellTranslationReadinessController(ProjectSession())

    try:
        controller.fields()
    except RuntimeError as exc:
        assert "выберите скважину" in str(exc)
    else:
        raise AssertionError("Expected missing-well RuntimeError")
