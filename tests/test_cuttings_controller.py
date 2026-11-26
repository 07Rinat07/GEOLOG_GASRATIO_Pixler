from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from geoworkbench.domain.cuttings_description_tracking import CuttingsDescriptionTrackingWorkflow
from geoworkbench.domain.models import CuttingsSample, Dataset, DatasetKind, DepthDomain
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.session import ProjectSession
from geoworkbench.storage.package_project_repository import PackageProjectRepository
from geoworkbench.storage.project_codec import ProjectDocument


def _controller() -> CuttingsController:
    session = ProjectSession()
    session.add_dataset(
        Dataset("data", "Log", DatasetKind.GTI, DepthDomain.MD, np.array([0.0, 1000.0])),
        "Well",
    )
    return CuttingsController(session)


def test_cuttings_interval_stores_percent_composition() -> None:
    controller = _controller()

    sample = controller.add(500, 510, {"sandstone": 70, "clay": 30})

    assert [(item.lithotype_id, item.percentage) for item in sample.components] == [
        ("sandstone", 70.0),
        ("clay", 30.0),
    ]
    assert controller.session.dirty is True


def test_sample_analysis_saves_all_author_text_languages_atomically() -> None:
    controller = _controller()
    sample = controller.set_analysis(
        500,
        510,
        calcite_percent=62.5,
        lba_description_i18n={"ru": "Свечение", "kk": "Жарқырау", "en": "Fluorescence"},
        analysis_interpretation_i18n={"ru": "Нефть", "kk": "Мұнай", "en": "Oil show"},
    )

    assert sample.lba_description_i18n["en"] == "Fluorescence"
    assert sample.analysis_interpretation_i18n["kk"] == "Мұнай"
    assert sample.lba_description == "Свечение"
    assert sample.analysis_interpretation == "Нефть"

    with pytest.raises(ValueError, match="язык"):
        controller.set_analysis(
            500,
            510,
            calcite_percent=10.0,
            lba_description_i18n={"invalid": "broken"},
        )

    assert sample.calcite_percent == 62.5
    assert sample.lba_description_i18n["en"] == "Fluorescence"


def test_cuttings_requires_hundred_percent_and_non_overlapping_interval() -> None:
    controller = _controller()

    with pytest.raises(ValueError, match="100%"):
        controller.add(500, 510, {"sandstone": 90})
    controller.add(500, 510, {"sandstone": 100})
    with pytest.raises(ValueError, match="пересекается"):
        controller.add(505, 515, {"clay": 100})


def test_sample_analysis_stores_calcimetry_and_lba_in_same_interval() -> None:
    controller = _controller()
    existing = controller.add(500, 510, {"sandstone": 100})

    sample = controller.set_analysis(
        500,
        510,
        calcite_percent=62.5,
        dolomite_percent=17.5,
        lba_group=3,
        lba_type_id="Oil show",
        lba_intensity=4,
        lba_color="yellow-white",
        lba_distribution="spotted",
        lba_cut="Streaming",
        lba_cut_speed="Fast",
        lba_cut_color="Straw",
        lba_residue_type="Good",
        lba_residue_color="Amber",
        lba_odour="Moderate",
        lba_stain="Spotty",
        lba_description="bright direct fluorescence",
        analysis_interpretation="Carbonate interval with a documented oil show",
    )

    assert sample is existing
    assert len(controller.session.current_well.cuttings) == 1
    assert sample.calcite_percent == 62.5
    assert sample.dolomite_percent == 17.5
    assert sample.insoluble_residue_percent == 20.0
    assert sample.lba_group == 3
    assert sample.lba_type_id == "Oil show"
    assert sample.lba_intensity == 4
    assert sample.lba_color == "yellow-white"
    assert sample.lba_distribution == "spotted"
    assert sample.lba_cut == "Streaming"
    assert sample.lba_cut_speed == "Fast"
    assert sample.lba_cut_color == "Straw"
    assert sample.lba_residue_type == "Good"
    assert sample.lba_residue_color == "Amber"
    assert sample.lba_odour == "Moderate"
    assert sample.lba_stain == "Spotty"
    assert sample.lba_description == "bright direct fluorescence"
    assert sample.analysis_interpretation == ("Carbonate interval with a documented oil show")
    assert controller.session.dirty is True


def test_analysis_interval_can_overlay_imported_cuttings_interval() -> None:
    controller = _controller()
    imported = controller.add(500, 510, {"sandstone": 100})

    analysis = controller.set_analysis(503, 507, calcite_percent=62.5)

    assert analysis is not imported
    assert (analysis.top_depth, analysis.bottom_depth) == (503.0, 507.0)
    assert analysis.calcite_percent == 62.5
    assert imported.components


def test_description_interval_can_overlay_imported_cuttings_interval() -> None:
    controller = _controller()
    imported = controller.add(500, 510, {"sandstone": 100})

    description = controller.set_description(502, 506, "Изменение литологии")

    assert description is not imported
    assert (description.top_depth, description.bottom_depth) == (502.0, 506.0)
    assert description.description == "Изменение литологии"


def test_cuttings_composition_can_be_added_after_interval_analysis() -> None:
    controller = _controller()
    sample = controller.set_analysis(500, 510, calcite_percent=60.0)

    updated = controller.add(500, 510, {"sandstone": 70, "clay": 30})

    assert updated is sample
    assert len(controller.session.current_well.cuttings) == 1
    assert [(item.lithotype_id, item.percentage) for item in updated.components] == [
        ("sandstone", 70.0),
        ("clay", 30.0),
    ]
    assert updated.calcite_percent == 60.0
    assert updated.insoluble_residue_percent is None


@pytest.mark.parametrize("overlay_kind", ["analysis", "description"])
def test_create_full_sample_rejects_occupied_exact_interval(overlay_kind: str) -> None:
    controller = _controller()
    top, bottom = 500.0, 510.0
    if overlay_kind == "analysis":
        overlay = controller.set_analysis(
            top,
            bottom,
            calcite_percent=62.5,
            lba_description_source_language="en",
            lba_description_i18n={"en": "Fluorescence"},
        )
    else:
        overlay = controller.set_description(
            top, bottom, "Interval description", language="en", source_language="en"
        )
    well = controller.session.current_well
    assert well is not None
    overlay_before = deepcopy(overlay)
    sources_before = dict(well.authored_field_source_languages)
    revisions_before = dict(well.authored_field_revisions)
    statuses_before = deepcopy(well.translation_statuses)
    content_revision_before = well.content_revision
    controller.session.dirty = False

    with pytest.raises(ValueError, match="существует другая проба"):
        controller.create_full_sample(top, bottom, {"sandstone": 100}, calcite_percent=20)

    assert controller.available() == (overlay_before,)
    assert well.authored_field_source_languages == sources_before
    assert well.authored_field_revisions == revisions_before
    assert well.translation_statuses == statuses_before
    assert well.content_revision == content_revision_before
    assert not controller.session.dirty

    distinct_top = top + 0.0002
    created = controller.create_full_sample(distinct_top, bottom, {"sandstone": 100})

    assert (created.top_depth, created.bottom_depth) == (distinct_top, bottom)
    assert controller.available() == (overlay_before, created)
    assert created.sample_id != overlay.sample_id
    assert controller.session.dirty


@pytest.mark.parametrize("overlay_kind", ["analysis", "description"])
def test_adding_composition_to_overlapping_overlay_is_rejected(overlay_kind: str) -> None:
    controller = _controller()
    controller.add(500, 510, {"sandstone": 100})
    if overlay_kind == "analysis":
        controller.set_analysis(503, 507, calcite_percent=62.5)
    else:
        controller.set_description(503, 507, "Original description")
    before = deepcopy(controller.available())
    controller.session.dirty = False

    with pytest.raises(ValueError, match="пересекается"):
        controller.add(503, 507, {"clay": 100}, description="New description")

    assert controller.available() == before
    assert not controller.session.dirty


@pytest.mark.parametrize("tracked", [False, True], ids=["untracked", "tracked"])
def test_adding_composition_checks_stored_overlay_bounds_when_request_only_touches(
    tracked: bool,
) -> None:
    controller = _controller()
    controller.add(500, 510, {"sandstone": 100})
    controller.set_analysis(509.999, 520, calcite_percent=62.5)
    if tracked:
        controller.set_description(509.999, 520, "Original description", source_language="ru")
    before = deepcopy(controller.available())
    controller.session.dirty = False

    with pytest.raises(ValueError, match="пересекается"):
        controller.add(510, 520.001, {"clay": 100})

    assert controller.available() == before
    assert not controller.session.dirty


@pytest.mark.parametrize("tracked", [False, True], ids=["untracked", "tracked"])
def test_adding_composition_preserves_touching_overlay_when_request_overlaps(tracked: bool) -> None:
    controller = _controller()
    neighbor = controller.add(500, 510, {"sandstone": 100})
    neighbor_before = deepcopy(neighbor)
    overlay = controller.set_analysis(
        510, 520, calcite_percent=62.5, lba_description="Original LBA"
    )
    controller.set_description(
        510, 520, "Original description", source_language="ru" if tracked else None
    )
    controller.session.dirty = False

    updated = controller.add(509.999, 520.001, {"clay": 100})

    assert updated is overlay
    assert controller.available() == (neighbor, overlay)
    assert neighbor == neighbor_before
    assert (updated.top_depth, updated.bottom_depth) == (510.0, 520.0)
    assert (updated.calcite_percent, updated.lba_description) == (62.5, "Original LBA")
    assert updated.description == "Original description"
    assert [(item.lithotype_id, item.percentage) for item in updated.components] == [("clay", 100.0)]
    assert controller.session.dirty


def test_cuttings_description_can_be_entered_before_composition_and_is_preserved() -> None:
    controller = _controller()

    sample = controller.set_description(500, 510, "Fine sandstone with oil stain")
    updated = controller.add(500, 510, {"sandstone": 100})

    assert updated is sample
    assert updated.description == "Fine sandstone with oil stain"
    assert updated.components[0].percentage == 100.0


def test_adding_composition_keeps_saved_bounds_at_the_active_dataset_edge() -> None:
    controller = _controller()
    sample = controller.set_description(500, 510, "Original description", source_language="ru")
    controller.session.add_dataset(
        Dataset("subset", "Subset", DatasetKind.GTI, DepthDomain.MD, np.array([500.001, 600.0]))
    )

    updated = controller.add(500.001, 510, {"sandstone": 100})

    assert updated is sample
    assert (updated.top_depth, updated.bottom_depth) == (500.0, 510.0)
    assert updated.components[0].percentage == 100.0


@pytest.mark.parametrize("source_language", [None, "ru"], ids=["untracked", "tracked"])
def test_setting_description_keeps_saved_bounds_at_the_active_dataset_edge(
    source_language: str | None,
) -> None:
    controller = _controller()
    sample = controller.set_analysis(500.0, 510.0, calcite_percent=22.5)
    controller.session.add_dataset(
        Dataset("subset", "Subset", DatasetKind.GTI, DepthDomain.MD, np.array([500.001, 600.0]))
    )

    updated = controller.set_description(
        500.001, 510.001, "Rock description", language="ru", source_language=source_language
    )

    assert controller.available() == (sample,)
    assert updated is sample
    assert (sample.top_depth, sample.bottom_depth) == (500.0, 510.0)
    assert sample.calcite_percent == 22.5
    assert sample.description_i18n == {"ru": "Rock description"}
    assert controller.description_source_language(sample.sample_id) == source_language


def test_cuttings_description_can_be_edited_and_cleared() -> None:
    controller = _controller()
    sample = controller.add(
        500,
        510,
        {"sandstone": 100},
        description="Initial",
        description_word_wrap=False,
    )

    assert controller.set_description(500, 510, "  Updated  ") is sample
    assert sample.description == "Updated"
    assert sample.description_word_wrap is False
    controller.set_description(500, 510, "Updated", description_word_wrap=True)
    assert sample.description_word_wrap is True
    controller.set_description(500, 510, "")
    assert sample.description is None


def test_empty_cuttings_description_does_not_create_an_interval() -> None:
    controller = _controller()

    with pytest.raises(ValueError, match="описание шлама"):
        controller.set_description(500, 510, "  ")

    with pytest.raises(ValueError, match="2000000"):
        controller.set_description(500, 510, "x" * 2_000_001)


def test_delete_description_preserves_sample_analysis() -> None:
    controller = _controller()
    sample = controller.add(500, 510, {"sandstone": 100}, description="Описание")
    controller.set_analysis(500, 510, calcite_percent=60.0)

    deleted = controller.delete_description(sample.sample_id)

    assert deleted is sample
    assert sample.description is None
    assert sample.calcite_percent == 60.0
    assert controller.get(sample.sample_id) is sample


@pytest.mark.parametrize("measurement", ["calcite_percent", "dolomite_percent"])
@pytest.mark.parametrize("tracked", [False, True], ids=["untracked", "tracked"])
def test_delete_description_preserves_zero_calcimetry_sample(
    tmp_path: Path, measurement: str, tracked: bool
) -> None:
    controller = _controller()
    sample = controller.set_analysis(500, 510, **{measurement: 0.0})
    source_language = "ru" if tracked else None
    controller.set_description(
        500, 510, "Описание", language="ru", source_language=source_language
    )
    assert controller.description_source_language(sample.sample_id) == source_language
    assert not sample.components

    deleted = controller.delete_description(sample.sample_id, language=None if tracked else "ru")

    assert deleted is sample
    assert controller.get(sample.sample_id) is sample
    assert sample.description is None
    assert sample.description_i18n == {}
    assert controller.description_source_language(sample.sample_id) is None
    assert getattr(sample, measurement) == 0.0

    repository = PackageProjectRepository()
    path = tmp_path / "zero-calcimetry.geologpkg"
    repository.save(ProjectDocument(project=controller.session.project), path)
    well = controller.session.current_well
    assert well is not None
    assert repository.load(path).project.wells[well.well_id].cuttings == [sample]


def test_delete_description_preserves_total_carbonate_only_sample() -> None:
    controller = _controller()
    sample = controller.set_description(500, 510, "Imported rock description")
    sample.total_carbonate_percent = 0.0

    controller.delete_description(sample.sample_id)

    assert controller.get(sample.sample_id) is sample
    assert sample.description is None
    assert sample.total_carbonate_percent == 0.0


def test_delete_description_removes_description_only_interval() -> None:
    controller = _controller()
    sample = controller.set_description(500, 510, "Описание")

    controller.delete_description(sample.sample_id)

    assert controller.available() == ()


@pytest.mark.parametrize("tracked", [False, True], ids=["untracked", "tracked"])
def test_delete_description_without_saved_language_is_noop(tracked: bool) -> None:
    controller = _controller()
    sample = controller.set_description(
        500, 510, "English description", language="en", source_language="en" if tracked else None
    )
    well = controller.session.current_well
    assert well is not None
    before = deepcopy(well)
    controller.session.dirty = False

    assert controller.delete_description(sample.sample_id, language="kk") is sample

    assert not controller.session.dirty
    assert well.cuttings == before.cuttings
    assert well.content_revision == before.content_revision
    assert well.language_revisions == before.language_revisions
    assert well.translation_statuses == before.translation_statuses
    assert well.authored_field_revisions == before.authored_field_revisions
    assert well.authored_field_source_languages == before.authored_field_source_languages


@pytest.mark.parametrize("calcite", [None, 0.0], ids=["description-only", "zero-calcite"])
def test_clearing_last_saved_description_preserves_only_samples_with_data(
    calcite: float | None,
) -> None:
    controller = _controller()
    sample = controller.set_description(500, 510, "English description", language="en")
    if calcite is not None:
        controller.set_analysis(500, 510, calcite_percent=calcite)

    updated = controller.update_description(
        sample.sample_id, top_depth=500, bottom_depth=510, description="", language="en"
    )

    assert updated is sample
    assert sample.description is None
    assert sample.description_i18n == {}
    if calcite is None:
        assert controller.find_sample_for_interval(500, 510) is None
    else:
        assert controller.get(sample.sample_id) is sample
        assert sample.calcite_percent == 0.0


@pytest.mark.parametrize(
    ("new_top", "word_wrap"),
    [(500, True), (501, True), (500, False)],
    ids=["no-op", "move", "wrap"],
)
def test_clearing_unsaved_fallback_keeps_language_revisions(
    new_top: float, word_wrap: bool
) -> None:
    controller = _controller()
    sample = controller.set_description(500, 510, "English description", language="en")
    well = controller.session.current_well
    assert well is not None
    before = deepcopy(well)
    controller.session.dirty = False

    updated = controller.update_description(
        sample.sample_id,
        top_depth=new_top,
        bottom_depth=510,
        description=None,
        description_word_wrap=word_wrap,
        language="kk",
    )

    assert updated is sample
    assert sample.description_i18n == before.cuttings[0].description_i18n
    assert (sample.top_depth, sample.bottom_depth) == (new_top, 510)
    assert sample.description_word_wrap is word_wrap
    geometry_changed = new_top != 500 or not word_wrap
    assert controller.session.dirty is geometry_changed
    assert well.content_revision == before.content_revision + int(geometry_changed)
    assert well.language_revisions == before.language_revisions


def test_sample_analysis_validates_percentages_intensity_and_empty_input() -> None:
    controller = _controller()

    with pytest.raises(ValueError, match="не должна превышать"):
        controller.set_analysis(500, 510, calcite_percent=70, dolomite_percent=40)
    with pytest.raises(ValueError, match="от 1 до 5"):
        controller.set_analysis(500, 510, lba_intensity=6)
    with pytest.raises(ValueError, match="Группа ЛБА"):
        controller.set_analysis(500, 510, lba_group=0)
    with pytest.raises(ValueError, match="хотя бы один"):
        controller.set_analysis(500, 510)


def test_existing_cuttings_sample_can_change_interval_and_rocks_without_losing_analysis() -> None:
    controller = _controller()
    sample = controller.add(500, 510, {"sandstone": 70, "clay": 30}, description="Saved text")
    controller.set_analysis(
        500,
        510,
        calcite_percent=55.0,
        dolomite_percent=20.0,
        lba_type_id="ЛБ",
        lba_intensity=3,
    )

    updated = controller.update_composition(
        sample.sample_id,
        top_depth=502,
        bottom_depth=512,
        components={"clay": 100},
    )

    assert updated is sample
    assert (sample.top_depth, sample.bottom_depth) == (502.0, 512.0)
    assert [(item.lithotype_id, item.percentage) for item in sample.components] == [("clay", 100.0)]
    assert sample.description == "Saved text"
    assert sample.calcite_percent == 55.0
    assert sample.dolomite_percent == 20.0
    assert sample.lba_type_id == "ЛБ"
    assert sample.lba_intensity == 3
    assert controller.get(sample.sample_id) is sample


def test_cuttings_update_ignores_own_interval_but_rejects_other_sample_overlap() -> None:
    controller = _controller()
    first = controller.add(100, 110, {"sandstone": 100})
    controller.add(120, 130, {"clay": 100})

    controller.update_composition(
        first.sample_id,
        top_depth=101,
        bottom_depth=111,
        components={"clay": 100},
    )

    with pytest.raises(ValueError, match="пересекается"):
        controller.update_composition(
            first.sample_id,
            top_depth=115,
            bottom_depth=125,
            components={"clay": 100},
        )


def test_update_analysis_preserves_shared_sample_geology_and_identity() -> None:
    controller = _controller()
    sample = controller.add(
        500,
        510,
        {"sandstone": 100},
        description="Авторское описание",
    )
    controller.set_analysis(
        500,
        510,
        calcite_percent=60.0,
        lba_group=2,
        lba_description="Initial LBA",
    )

    updated = controller.update_analysis(
        sample.sample_id,
        top_depth=501,
        bottom_depth=511,
        calcite_percent=70.0,
        dolomite_percent=10.0,
        lba_group=3,
        lba_description="Updated LBA",
    )

    assert updated is sample
    assert updated.sample_id == sample.sample_id
    assert (updated.top_depth, updated.bottom_depth) == (501.0, 511.0)
    assert [(item.lithotype_id, item.percentage) for item in updated.components] == [
        ("sandstone", 100.0)
    ]
    assert updated.description == "Авторское описание"
    assert updated.calcite_percent == 70.0
    assert updated.dolomite_percent == 10.0
    assert updated.lba_group == 3
    assert updated.lba_description == "Updated LBA"
    assert len(controller.available()) == 1


def test_update_analysis_can_move_overlay_without_replacing_imported_cuttings() -> None:
    controller = _controller()
    imported = controller.add(500, 510, {"sandstone": 100})
    analysis = controller.set_analysis(503, 507, calcite_percent=62.5)

    updated = controller.update_analysis(
        analysis.sample_id,
        top_depth=504,
        bottom_depth=508,
        calcite_percent=55.0,
    )

    assert updated is analysis
    assert (updated.top_depth, updated.bottom_depth) == (504.0, 508.0)
    assert updated.calcite_percent == 55.0
    assert imported.components[0].lithotype_id == "sandstone"
    assert (imported.top_depth, imported.bottom_depth) == (500.0, 510.0)


def _adjacent_samples_with_analysis() -> tuple[CuttingsController, CuttingsSample, CuttingsSample]:
    controller = _controller()
    first = controller.create_full_sample(
        500.0, 500.004, {"sandstone": 100.0}, calcite_percent=10.0
    )
    second = controller.create_full_sample(
        500.004, 500.008, {"clay": 100.0}, calcite_percent=20.0
    )
    controller.session.dirty = False
    return controller, first, second


def test_update_analysis_rejects_small_move_overlapping_neighbor() -> None:
    controller, first, _second = _adjacent_samples_with_analysis()
    before = deepcopy(controller.available())

    with pytest.raises(ValueError, match="пересекается"):
        controller.update_analysis(
            first.sample_id, top_depth=500.0, bottom_depth=500.0042, calcite_percent=37.0
        )

    assert controller.available() == before
    assert not controller.session.dirty


@pytest.mark.parametrize("top_depth", [500.004, 500.0042], ids=["touching", "gap"])
def test_update_analysis_accepts_small_move_to_distinct_interval(top_depth: float) -> None:
    controller, first, second = _adjacent_samples_with_analysis()
    first_before = deepcopy(first)

    updated = controller.update_analysis(
        second.sample_id, top_depth=top_depth, bottom_depth=500.0082, calcite_percent=37.0
    )

    assert updated is second
    assert (updated.top_depth, updated.bottom_depth, updated.calcite_percent) == (
        top_depth, 500.0082, 37.0
    )
    assert first == first_before
    assert controller.available() == (first, second)
    assert controller.session.dirty


def test_update_analysis_rejects_move_to_exact_occupied_interval() -> None:
    controller, first, _second = _adjacent_samples_with_analysis()
    overlay = controller.set_analysis(500.2, 500.3, calcite_percent=30.0)
    assert not overlay.components
    before = deepcopy(controller.available())
    controller.session.dirty = False

    with pytest.raises(ValueError, match="существует другая проба"):
        controller.update_analysis(
            overlay.sample_id,
            top_depth=first.top_depth,
            bottom_depth=first.bottom_depth,
            calcite_percent=37.0,
        )

    assert controller.available() == before
    assert not controller.session.dirty


@pytest.mark.parametrize(
    ("editor", "values"),
    [
        ("update_composition", {"components": {"clay": 100.0}}),
        ("update_description", {"description": "Edited description", "language": "en"}),
        ("update_full_sample", {"components": {"clay": 100.0}, "calcite_percent": 35.0}),
    ],
    ids=["composition", "description", "full-sample"],
)
@pytest.mark.parametrize("destination", ["analysis-only", "description-only"])
def test_edit_rejects_occupied_depths_and_allows_nearby_distinct_depths(
    editor: str, values: dict[str, object], destination: str
) -> None:
    controller = _controller()
    sample = controller.create_full_sample(
        500.0,
        510.0,
        {"sandstone": 100.0},
        calcite_percent=55.0,
        description_i18n={"en": "Sample description", "ru": "Описание пробы"},
        description_source_language="en",
    )
    top, bottom = 520.0, 530.0
    if destination == "analysis-only":
        neighbor = controller.set_analysis(top, bottom, calcite_percent=62.5)
    else:
        neighbor = controller.set_description(top, bottom, "Interval description")

    well = controller.session.current_well
    assert well is not None
    before = deepcopy(well.cuttings)
    revisions_before = dict(well.authored_field_revisions)
    statuses_before = deepcopy(well.translation_statuses)
    content_revision_before = well.content_revision
    controller.session.dirty = False
    save = getattr(controller, editor)

    with pytest.raises(ValueError, match="существует другая проба"):
        save(sample.sample_id, top_depth=top, bottom_depth=bottom, **values)

    assert well.cuttings == before
    assert well.authored_field_revisions == revisions_before
    assert well.translation_statuses == statuses_before
    assert well.content_revision == content_revision_before
    assert not controller.session.dirty

    saved = save(sample.sample_id, top_depth=top + 0.0002, bottom_depth=bottom, **values)

    assert saved is sample
    assert (saved.top_depth, saved.bottom_depth) == (top + 0.0002, bottom)
    assert controller.get(neighbor.sample_id) is neighbor
    assert neighbor == before[1]
    assert len(well.cuttings) == 2
    assert controller.session.dirty


def test_update_analysis_accepts_unchanged_bounds_with_existing_overlap() -> None:
    controller, first, second = _adjacent_samples_with_analysis()
    # A legacy project may contain a preexisting overlap.
    first.bottom_depth = 500.0042
    before = deepcopy(controller.available())

    updated = controller.update_analysis(
        first.sample_id,
        top_depth=first.top_depth,
        bottom_depth=first.bottom_depth,
        calcite_percent=first.calcite_percent,
    )

    assert updated is first
    assert controller.available() == before == (first, second)
    assert not controller.session.dirty


@pytest.mark.parametrize("operation", ["set_analysis", "set_description", "update_analysis"])
def test_cuttings_save_prefers_exact_interval_over_a_nearby_sample(
    tmp_path: Path, operation: str
) -> None:
    controller = _controller()
    earlier = controller.create_full_sample(
        500.0, 500.004, {"sandstone": 100.0}, description="Earlier", calcite_percent=10.0
    )
    target = controller.create_full_sample(
        500.004, 500.008, {"clay": 100.0}, description="Target", calcite_percent=20.0
    )
    earlier_before = deepcopy(earlier)
    top, bottom = target.top_depth, target.bottom_depth

    if operation == "set_description":
        saved = controller.set_description(top, bottom, "Updated description")
    elif operation == "update_analysis":
        saved = controller.update_analysis(
            target.sample_id, top_depth=top, bottom_depth=bottom, calcite_percent=37.0
        )
    else:
        saved = controller.set_analysis(top, bottom, calcite_percent=37.0)

    assert saved is target
    assert earlier == earlier_before
    assert (target.top_depth, target.bottom_depth) == (top, bottom)
    assert target.description == ("Updated description" if operation == "set_description" else "Target")
    assert target.calcite_percent == (20.0 if operation == "set_description" else 37.0)
    assert controller.available() == (earlier, target)

    repository = PackageProjectRepository()
    path = tmp_path / "nearby-cuttings.geologpkg"
    repository.save(ProjectDocument(project=controller.session.project), path)
    well = controller.session.current_well
    assert well is not None
    restored = repository.load(path).project.wells[well.well_id]
    assert restored.cuttings == [earlier_before, target]


def test_set_analysis_accepts_the_sole_approximate_interval_match() -> None:
    controller = _controller()
    sample = controller.set_analysis(500.0, 501.0, calcite_percent=20.0)

    saved = controller.set_analysis(500.00001, 501.00001, calcite_percent=37.0)

    assert saved is sample
    assert sample.calcite_percent == 37.0
    assert controller.available() == (sample,)


@pytest.mark.parametrize("operation", ["add", "set_description", "set_analysis"])
@pytest.mark.parametrize("same_bounds", [False, True], ids=["nearby", "duplicate-exact"])
def test_ambiguous_interval_writes_leave_samples_and_revisions_intact(
    operation: str, same_bounds: bool
) -> None:
    controller = _controller()
    first = (500.0, 510.0)
    controller.set_analysis(*first, calcite_percent=10.0)
    controller.set_description(*first, "Original", language="en", source_language="en")
    well = controller.session.current_well
    assert well is not None
    if same_bounds:
        well.cuttings.append(CuttingsSample("legacy-duplicate", *first, calcite_percent=20.0))
        selection = first
    else:
        controller.set_analysis(500.004, 510.004, calcite_percent=20.0, absolute_tolerance=0.0)
        selection = (500.002, 510.002)
    before = deepcopy(well)
    controller.session.dirty = False

    with pytest.raises(ValueError, match="несколько проб"):
        if operation == "add":
            controller.add(*selection, {"sandstone": 100.0})
        elif operation == "set_description":
            controller.set_description(*selection, "Edited", language="en")
        else:
            controller.set_analysis(*selection, calcite_percent=30.0)

    assert well.cuttings == before.cuttings
    assert well.content_revision == before.content_revision
    assert well.language_revisions == before.language_revisions
    assert well.translation_statuses == before.translation_statuses
    assert well.authored_field_revisions == before.authored_field_revisions
    assert not controller.session.dirty


def test_analysis_lookup_uses_only_the_first_matching_tolerance() -> None:
    controller = _controller()
    tight = controller.set_analysis(500.0000004, 510.0000004, calcite_percent=10.0)
    controller.set_analysis(500.004, 510.004, calcite_percent=20.0, absolute_tolerance=0.0)

    assert controller.find_sample_for_analysis_selection(500.0, 510.0) is tight

    controller.set_analysis(500.0000008, 510.0000008, calcite_percent=30.0, absolute_tolerance=0.0)
    with pytest.raises(ValueError, match="несколько проб"):
        controller.find_sample_for_analysis_selection(500.0, 510.0)


def test_editing_by_sample_id_can_distinguish_legacy_duplicate_bounds() -> None:
    controller = _controller()
    first = controller.set_analysis(500.0, 510.0, calcite_percent=10.0)
    second = CuttingsSample("legacy-duplicate", 500.0, 510.0, calcite_percent=20.0)
    well = controller.session.current_well
    assert well is not None
    well.cuttings.append(second)

    updated = controller.update_analysis(
        second.sample_id, top_depth=500.0, bottom_depth=510.0, calcite_percent=30.0
    )

    assert updated is second
    assert first.calcite_percent == 10.0
    assert second.calcite_percent == 30.0


def test_reediting_cuttings_ignores_analysis_only_overlay_for_overlap_rules() -> None:
    controller = _controller()
    cuttings = controller.add(500, 510, {"sandstone": 100})
    analysis = controller.set_analysis(503, 507, calcite_percent=62.5)

    updated = controller.update_composition(
        cuttings.sample_id,
        top_depth=500,
        bottom_depth=511,
        components={"sandstone": 80, "clay": 20},
    )

    assert updated is cuttings
    assert (updated.top_depth, updated.bottom_depth) == (500.0, 511.0)
    assert analysis.calcite_percent == 62.5
    assert (analysis.top_depth, analysis.bottom_depth) == (503.0, 507.0)


def test_full_sample_reedit_preserves_overlapping_analysis_overlay() -> None:
    controller = _controller()
    cuttings = controller.create_full_sample(
        500,
        510,
        {"sandstone": 100},
        description="Initial",
        calcite_percent=40.0,
    )
    overlay = controller.set_analysis(503, 507, calcite_percent=62.5)

    updated = controller.update_full_sample(
        cuttings.sample_id,
        top_depth=500,
        bottom_depth=511,
        components={"sandstone": 70, "clay": 30},
        description="Updated",
        calcite_percent=45.0,
    )

    assert updated is cuttings
    assert updated.description == "Updated"
    assert updated.calcite_percent == 45.0
    assert overlay.calcite_percent == 62.5
    assert (overlay.top_depth, overlay.bottom_depth) == (503.0, 507.0)


def test_update_analysis_accepts_existing_twenty_thousand_character_interpretation() -> None:
    controller = _controller()
    interpretation = "x" * 20_000
    sample = controller.set_analysis(
        500,
        510,
        calcite_percent=40.0,
        analysis_interpretation=interpretation,
    )

    updated = controller.update_analysis(
        sample.sample_id,
        top_depth=500,
        bottom_depth=510,
        calcite_percent=45.0,
        analysis_interpretation=interpretation,
    )

    assert updated.calcite_percent == 45.0
    assert updated.analysis_interpretation == interpretation


def test_moving_analysis_on_shared_tracked_description_updates_depth_provenance() -> None:
    controller = _controller()
    sample = controller.set_description(
        500,
        510,
        "Tracked rock description",
        language="en",
        source_language="en",
    )
    controller.set_analysis(500, 510, calcite_percent=40.0)

    depth_id = CuttingsDescriptionTrackingWorkflow.depth_dependency_id(
        sample.sample_id
    )
    before = controller.session.current_well.authored_field_revisions[depth_id]

    controller.update_analysis(
        sample.sample_id,
        top_depth=501,
        bottom_depth=511,
        calcite_percent=45.0,
    )

    after = controller.session.current_well.authored_field_revisions[depth_id]
    assert after == before + 1
    assert (sample.top_depth, sample.bottom_depth) == (501.0, 511.0)


def test_clearing_standalone_analysis_removes_invisible_orphan() -> None:
    controller = _controller()
    sample = controller.set_analysis(500, 510, calcite_percent=40.0)

    updated = controller.update_analysis(
        sample.sample_id,
        top_depth=500,
        bottom_depth=510,
    )

    assert updated is sample
    assert controller.available() == ()
