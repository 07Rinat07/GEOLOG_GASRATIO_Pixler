from dataclasses import asdict, replace
from copy import deepcopy

import pytest

from geoworkbench.domain.analysis_update import AnalysisField
from geoworkbench.domain.models import CuttingsSample, Well
from geoworkbench.services.well_analysis_update import (
    AnalysisSourceSample,
    AnalysisSourceValue,
    AnalysisUpdateError,
    analyze_well_analysis_update,
    prepare_well_analysis_update,
    well_analysis_state_sha256,
)


SHA = "a" * 64


def values(**items):
    return tuple(
        AnalysisSourceValue(AnalysisField(field), value)
        for field, value in items.items()
    )


def source(top, bottom, *, sample_id=None, **items):
    return AnalysisSourceSample(top, bottom, values(**items), sample_id)


def review(well, samples, *fields):
    return analyze_well_analysis_update(
        well,
        tuple(samples),
        selected_fields=tuple(AnalysisField(field) for field in fields),
        source_name="late-analysis.json",
        source_sha256=SHA,
    )


def prepare(well, samples, plan, selected=None):
    return prepare_well_analysis_update(
        well,
        tuple(samples),
        plan,
        source_name="late-analysis.json",
        source_sha256=SHA,
        selected_changes=plan.changes if selected is None else tuple(selected),
    )


def test_fill_only_preview_prepare_and_repeat_noop_preserve_manual_content():
    sample = CuttingsSample(
        "s1",
        100.0,
        101.0,
        calcite_percent=None,
        dolomite_percent=20.0,
        description="Manual geology text",
        description_i18n={"ru": "Ручное описание"},
    )
    well = Well("w1", "Well", cuttings=[sample])
    incoming = (source(100, 101, calcite_percent=30.0, dolomite_percent=20.0),)
    before = deepcopy(asdict(well))

    plan = review(well, incoming, "calcite_percent", "dolomite_percent")
    assert plan.fill_count == 1
    assert plan.conflict_count == 0
    assert plan.equal_values == 1
    assert plan.changes[0].field is AnalysisField.CALCITE_PERCENT

    prepared = prepare(well, incoming, plan)
    assert asdict(well) == before
    assert prepared is not None
    assert prepared.cuttings[0].calcite_percent == 30.0
    assert prepared.cuttings[0].dolomite_percent == 20.0
    assert prepared.cuttings[0].description == "Manual geology text"
    assert prepared.cuttings[0].description_i18n == {"ru": "Ручное описание"}
    assert prepared.record.well_sha256_before == plan.target_state_sha256
    assert prepared.record.well_sha256_after != prepared.record.well_sha256_before

    well.cuttings = prepared.cuttings
    well.content_revision = prepared.revision
    repeated = review(well, incoming, "calcite_percent", "dolomite_percent")
    assert repeated.changes == ()
    assert repeated.conflicts == ()
    assert repeated.equal_values == 2
    assert prepare(well, incoming, repeated, ()) is None


def test_existing_different_value_is_conflict_and_never_overwritten():
    sample = CuttingsSample("s1", 10, 11, calcite_percent=25.0, description="keep")
    well = Well("w1", "Well", cuttings=[sample])
    incoming = (source(10, 11, calcite_percent=40.0),)

    plan = review(well, incoming, "calcite_percent")
    assert plan.changes == ()
    assert plan.conflict_count == 1
    assert plan.conflicts[0].existing_value == 25.0
    assert plan.conflicts[0].incoming_value == 40.0
    assert prepare(well, incoming, plan, ()) is None
    assert well.cuttings[0] is sample
    assert well.cuttings[0].calcite_percent == 25.0
    assert well.cuttings[0].description == "keep"


def test_only_selected_fields_are_considered_and_only_selected_changes_are_applied():
    well = Well("w", "Well", cuttings=[CuttingsSample("s", 1, 2)])
    incoming = (source(1, 2, calcite_percent=35, dolomite_percent=25, lba_odour="oil"),)
    plan = review(well, incoming, "calcite_percent", "dolomite_percent")
    assert [item.field for item in plan.changes] == [
        AnalysisField.CALCITE_PERCENT,
        AnalysisField.DOLOMITE_PERCENT,
    ]

    prepared = prepare(well, incoming, plan, (plan.changes[0],))
    assert prepared is not None
    assert prepared.cuttings[0].calcite_percent == 35.0
    assert prepared.cuttings[0].dolomite_percent is None
    assert prepared.cuttings[0].lba_odour is None
    assert prepared.record.selected_fields == (AnalysisField.CALCITE_PERCENT,)
    assert prepared.record.changes == (plan.changes[0],)


def test_blank_source_is_ignored_but_numeric_zero_is_valid_data():
    well = Well("w", "Well", cuttings=[CuttingsSample("s", 1, 2)])
    incoming = (source(1, 2, calcite_percent=0, lba_odour="   "),)
    plan = review(well, incoming, "calcite_percent", "lba_odour")
    assert len(plan.changes) == 1
    assert plan.changes[0].new_value == 0.0
    assert plan.ignored_empty_values == 1


def test_missing_interval_is_reported_without_creating_new_sample():
    well = Well("w", "Well", cuttings=[CuttingsSample("s", 1, 2)])
    incoming = (source(5, 6, calcite_percent=10),)
    plan = review(well, incoming, "calcite_percent")
    assert plan.missing_source_intervals == 1
    assert not plan.changes
    assert len(well.cuttings) == 1


@pytest.mark.parametrize("change", ["target", "source"])
def test_stale_target_or_source_rejects_prepare_without_mutation(change):
    well = Well("w", "Well", cuttings=[CuttingsSample("s", 1, 2)])
    incoming = (source(1, 2, calcite_percent=20),)
    plan = review(well, incoming, "calcite_percent")
    before = deepcopy(asdict(well))

    if change == "target":
        well.cuttings[0].description = "edited after preview"
        expected = deepcopy(asdict(well))
        candidate = incoming
    else:
        expected = before
        candidate = (source(1, 2, calcite_percent=21),)

    with pytest.raises(AnalysisUpdateError, match="повторите просмотр"):
        prepare(well, candidate, plan)
    assert asdict(well) == expected


def test_unapproved_change_cannot_be_injected_into_apply_selection():
    well = Well("w", "Well", cuttings=[CuttingsSample("s", 1, 2)])
    incoming = (source(1, 2, calcite_percent=20, dolomite_percent=10),)
    plan = review(well, incoming, "calcite_percent", "dolomite_percent")
    forged = replace(plan.changes[0], new_value=99.0)
    before = deepcopy(asdict(well))
    with pytest.raises(AnalysisUpdateError, match="отсутствующее"):
        prepare(well, incoming, plan, (forged,))
    assert asdict(well) == before


def test_calcimetry_validation_uses_staged_existing_plus_late_value():
    well = Well(
        "w",
        "Well",
        cuttings=[CuttingsSample("s", 1, 2, calcite_percent=60.0)],
    )
    incoming = (source(1, 2, dolomite_percent=50.0),)
    with pytest.raises(AnalysisUpdateError, match="превышать 100"):
        review(well, incoming, "dolomite_percent")


@pytest.mark.parametrize(
    ("items", "message"),
    [
        ({"lba_group": 6}, "Группа ЛБА"),
        ({"lba_intensity": 0}, "Интенсивность ЛБА"),
        ({"lba_type_id": "unknown"}, "Неизвестный тип ЛБА"),
        ({"lba_color": "not-a-colour"}, "Неизвестный цвет ЛБА"),
        ({"lba_group": 1, "lba_type_id": "oily"}, "Несогласованные поля ЛБА"),
    ],
)
def test_source_lba_is_validated_by_existing_standard(items, message):
    well = Well("w", "Well", cuttings=[CuttingsSample("s", 1, 2)])
    incoming = (source(1, 2, **items),)
    fields = tuple(items)
    with pytest.raises(AnalysisUpdateError, match=message):
        review(well, incoming, *fields)


def test_late_lba_field_cannot_make_existing_standard_state_inconsistent():
    well = Well(
        "w",
        "Well",
        cuttings=[CuttingsSample("s", 1, 2, lba_group=1)],
    )
    incoming = (source(1, 2, lba_type_id="oily"),)
    with pytest.raises(AnalysisUpdateError, match="несогласованный ЛБА"):
        review(well, incoming, "lba_type_id")


def test_sample_id_binding_is_checked_against_interval():
    well = Well("w", "Well", cuttings=[CuttingsSample("s", 1, 2)])
    incoming = (source(10, 11, sample_id="s", calcite_percent=20),)
    with pytest.raises(AnalysisUpdateError, match="не совпадает с интервалом"):
        review(well, incoming, "calcite_percent")


def test_same_target_cannot_be_referenced_twice_by_id_and_interval():
    well = Well("w", "Well", cuttings=[CuttingsSample("s", 1, 2)])
    incoming = (
        source(1, 2, sample_id="s", calcite_percent=20),
        source(1, 2, calcite_percent=20),
    )
    with pytest.raises(AnalysisUpdateError, match="повтор"):
        review(well, incoming, "calcite_percent")


def test_state_digest_is_deterministic_and_covers_manual_cuttings_context():
    well = Well("w", "Well", cuttings=[CuttingsSample("s", 1, 2, calcite_percent=10)])
    first = well_analysis_state_sha256(well)
    second = well_analysis_state_sha256(well)
    assert first == second
    well.cuttings[0].description = "manual edit"
    assert well_analysis_state_sha256(well) != first
