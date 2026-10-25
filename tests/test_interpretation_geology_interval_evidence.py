"""INTERP-GEO-01: depth coverage, traceable measurements, unknown != negative."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from math import nan

import numpy as np
import pytest

from geoworkbench.domain.models import (
    CuttingsComponent,
    CuttingsSample,
    DatasetIndex,
    IndexRole,
    IndexType,
    StratigraphyInterval,
)
from geoworkbench.services.interpretation_geology_interval_evidence import (
    correlate_gas_interval_with_well_geology,
)
from test_report_geology_snapshot import _session


def _intersect(session, top=1002.0, bottom=1010.0):
    return correlate_gas_interval_with_well_geology(
        session, top_depth=top, bottom_depth=bottom,
    )


@pytest.mark.parametrize(("bounds", "expected"), (
    ((), ((1002.0, 1010.0),)),
    (((1004.0, 1006.0),), ((1002.0, 1004.0), (1006.0, 1010.0))),
    (((1000.0, 1004.0), (1006.0, 1008.0)), ((1004.0, 1006.0), (1008.0, 1010.0))),
    (((1000.0, 1006.0), (1004.0, 1007.0), (1005.0, 1006.0)), ((1007.0, 1010.0),)),
    (((1000.0, 1006.0), (1006.0, 1015.0)), ()),
    (((1015.0, 1000.0),), ()),
    (((1000.0, 1002.0), (1010.0, 1015.0)), ((1002.0, 1010.0),)),
))
def test_uncovered_md_intervals_complement_union_without_filling_missing_samples(bounds, expected):
    session = _session()
    well = session.current_well
    well.cuttings[:] = [
        CuttingsSample(str(index), top, bottom, [CuttingsComponent("sandstone", 100.0)])
        for index, (top, bottom) in enumerate(bounds)
    ]
    before = repr(well.cuttings)
    evidence = _intersect(session)
    assert evidence.uncovered_intervals("cuttings") == expected
    gap_length = sum(high - low for low, high in expected)
    assert gap_length + evidence.coverage("cuttings") * 8.0 == pytest.approx(8.0)
    assert repr(well.cuttings) == before


def test_gaps_are_independent_for_each_evidence_kind():
    evidence = _intersect(_session())
    assert evidence.uncovered_intervals("lithology") == ((1008.0, 1010.0),)
    assert evidence.uncovered_intervals("cuttings") == ((1002.0, 1004.0), (1009.0, 1010.0))
    assert evidence.uncovered_intervals("lba") == evidence.uncovered_intervals("cuttings")
    assert evidence.uncovered_intervals("calcimetry") == ((1002.0, 1010.0),)
    assert evidence.uncovered_intervals("stratigraphy") == ((1002.0, 1010.0),)


@pytest.mark.parametrize("changes", ({"depth_unit": "ft"}, {"gas_top": nan}, {"gas_bottom": 1002.0}))
def test_uncovered_intervals_refuse_unverified_units_or_bounds(changes):
    evidence = replace(_intersect(_session()), **changes)
    with pytest.raises(ValueError, match="known kind and finite MD bounds"):
        evidence.uncovered_intervals("lba")


@pytest.mark.parametrize(("top", "bottom"), ((1001.0, 1004.0), (1003.0, 1011.0), (nan, 1004.0), (1004.0, 1004.0)))
def test_uncovered_intervals_refuse_outside_or_invalid_observations(top, bottom):
    evidence = _intersect(_session())
    invalid = replace(evidence.intersections[0], overlap_top=top, overlap_bottom=bottom)
    with pytest.raises(ValueError, match="outside the requested"):
        replace(evidence, intersections=(invalid,)).uncovered_intervals(invalid.kind)


@pytest.mark.parametrize("field", (
    "lba_cut_speed", "lba_cut_color", "lba_residue_type",
    "lba_residue_color", "lba_odour", "lba_stain",
))
@pytest.mark.parametrize("value", ("Saved observation <original>", None, "", "   "))
def test_independent_lba_observation_counts_only_when_recorded(field, value):
    session = _session()
    sample = session.current_well.cuttings[0]
    for name in (
        "lba_group", "lba_type_id", "lba_intensity", "lba_color",
        "lba_distribution", "lba_cut", "lba_description",
    ):
        setattr(sample, name, None)
    setattr(sample, field, value)
    before = repr(sample)
    evidence = _intersect(session)
    observed = [item for item in evidence.intersections if item.kind == "lba"]
    if value and value.strip():
        assert len(observed) == 1
        assert observed[0].source_id == sample.sample_id
        assert observed[0].attributes == ((field, value),)
        assert evidence.coverage("lba") == pytest.approx(5 / 8)
        assert "lba" not in evidence.missing_kinds
    else:
        assert not observed
        assert evidence.coverage("lba") == 0.0
        assert "lba" in evidence.missing_kinds
    assert repr(sample) == before


@pytest.mark.parametrize("field", (
    "lba_cut_speed", "lba_cut_color", "lba_residue_type",
    "lba_residue_color", "lba_odour", "lba_stain",
))
def test_changed_lba_detail_invalidates_confirmed_evidence(field):
    from test_interpretation_geology_evidence_signed_pdf import _actual_source
    from geoworkbench.services.interpretation_geology_evidence_export import verified_session_geology_evidence

    session, report, selected = _actual_source()
    assert verified_session_geology_evidence(session, report, (selected,)) == (selected,)
    setattr(session.current_well.cuttings[0], field, "New recorded detail")
    with pytest.raises(ValueError, match="changed after operator selection"):
        verified_session_geology_evidence(session, report, (selected,))


def test_measured_md_lithology_cuttings_lba_and_stratigraphy_have_traceable_coverage() -> None:
    session = _session()
    well = session.current_well
    assert well is not None
    well.stratigraphy.append(StratigraphyInterval(
        "fam1", 1006.0, 1011.0, "C1", "Carboniferous", "stage",
    ))
    dataset = session.current_dataset
    assert dataset is not None
    original_depth = dataset.depth.copy()
    original_values = dataset.curves["curve-c1"].values.copy()
    source_sample = well.cuttings[0].description

    evidence = _intersect(session)
    assert evidence.well_id == well.well_id
    assert evidence.dataset_id == dataset.dataset_id
    assert evidence.depth_axis_id == dataset.active_index.index_id
    assert evidence.depth_unit == "m"
    assert evidence.coverage("lithology") == pytest.approx(6 / 8)
    assert evidence.coverage("cuttings") == pytest.approx(5 / 8)
    assert evidence.coverage("lba") == pytest.approx(5 / 8)
    assert evidence.coverage("stratigraphy") == pytest.approx(4 / 8)
    assert evidence.coverage("calcimetry") == 0.0
    assert evidence.missing_kinds == ("calcimetry",)

    observed = {(m.kind, m.source_id): m for m in evidence.intersections}
    assert observed["lithology", "lith-in"].overlap_top == 1002.0
    assert observed["lithology", "lith-in"].overlap_bottom == 1008.0
    assert observed["cuttings", "sample-in"].overlap_depth == 5.0
    assert ("lithotype:sandstone", 70.0) in observed["cuttings", "sample-in"].attributes
    assert ("lba_group", 2) in observed["lba", "sample-in"].attributes
    assert ("code", "C1") in observed["stratigraphy", "fam1"].attributes
    assert ("cuttings", "sample-out") not in observed

    with pytest.raises(FrozenInstanceError):
        observed["lba", "sample-in"].source_id = "fake"
    np.testing.assert_array_equal(dataset.depth, original_depth)
    np.testing.assert_array_equal(dataset.curves["curve-c1"].values, original_values)
    assert well.cuttings[0].description == source_sample


def test_individual_assay_field_coverage_never_inherits_sibling_measurements() -> None:
    session = _session()
    sample = session.current_well.cuttings[0]
    sample.calcite_percent = 0.0
    sample.dolomite_percent = None
    sample.total_carbonate_percent = None
    original = repr(sample)

    evidence = _intersect(session)
    assert evidence.coverage("calcimetry") == pytest.approx(5 / 8)
    assert evidence.attribute_coverage("calcimetry", "calcite_percent") == pytest.approx(5 / 8)
    assert evidence.attribute_coverage("calcimetry", "dolomite_percent") == 0.0
    assert evidence.attribute_coverage("calcimetry", "total_carbonate_percent") == 0.0
    assert evidence.attribute_coverage("lba", "lba_group") == pytest.approx(5 / 8)
    assert evidence.attribute_coverage("lba", "lba_odour") == 0.0
    assert repr(sample) == original


def test_individual_fields_use_union_across_partially_overlapping_samples() -> None:
    session = _session()
    well = session.current_well
    well.cuttings[0].calcite_percent = 0.0
    well.cuttings.append(CuttingsSample(
        "second-assay", 1006.0, 1012.0,
        [CuttingsComponent("limestone", 100.0)],
        calcite_percent=20.0,
        dolomite_percent=10.0,
        lba_odour="Recorded odour",
    ))
    before = repr(well.cuttings)

    evidence = _intersect(session)
    assert evidence.coverage("calcimetry") == pytest.approx(6 / 8)
    assert evidence.attribute_coverage("calcimetry", "calcite_percent") == pytest.approx(6 / 8)
    assert evidence.attribute_coverage("calcimetry", "dolomite_percent") == pytest.approx(4 / 8)
    assert evidence.attribute_coverage("calcimetry", "total_carbonate_percent") == 0.0
    assert evidence.coverage("lba") == pytest.approx(6 / 8)
    assert evidence.attribute_coverage("lba", "lba_group") == pytest.approx(5 / 8)
    assert evidence.attribute_coverage("lba", "lba_odour") == pytest.approx(4 / 8)
    assert repr(well.cuttings) == before


def test_field_coverage_rejects_unknown_axis_metadata_and_blank_field() -> None:
    evidence = _intersect(_session())
    with pytest.raises(ValueError, match="attribute name"):
        evidence.attribute_coverage("lba", " ")
    with pytest.raises(ValueError, match="known kind and finite MD bounds"):
        replace(evidence, depth_unit="ft").attribute_coverage("lba", "lba_group")
    with pytest.raises(ValueError, match="known kind and finite MD bounds"):
        evidence.attribute_coverage("nonexistent", "lba_group")  # type: ignore[arg-type]


def test_missing_lba_and_calcimetry_are_unknown_not_negative() -> None:
    session = _session()
    evidence = _intersect(session)
    assert evidence.coverage("calcimetry") == 0
    assert not any(item.kind == "calcimetry" for item in evidence.intersections)
    assert "calcimetry" in evidence.missing_kinds
    assert "lba" not in evidence.missing_kinds


def test_measured_zero_calcite_preserved_without_inventing_total_carbonate() -> None:
    session = _session()
    well = session.current_well
    assert well is not None
    well.cuttings[0].calcite_percent = 0.0
    well.cuttings[0].dolomite_percent = None
    well.cuttings[0].total_carbonate_percent = None
    evidence = _intersect(session)
    measured = [item for item in evidence.intersections if item.kind == "calcimetry"]
    assert len(measured) == 1
    assert measured[0].attributes == (("calcite_percent", 0.0),)
    assert evidence.coverage("calcimetry") == pytest.approx(5 / 8)
    assert "calcimetry" not in evidence.missing_kinds


def test_overlapping_sample_coverage_uses_union_and_preserves_provenance() -> None:
    session = _session()
    well = session.current_well
    assert well is not None
    well.cuttings[0].total_carbonate_percent = 97.0
    well.cuttings.append(
        CuttingsSample("second", 1006.0, 1012.0, [
            CuttingsComponent("limestone", 100.0),
        ], total_carbonate_percent=90.0)
    )
    evidence = _intersect(session)
    assert evidence.coverage("calcimetry") == pytest.approx(6 / 8)
    assert evidence.coverage("cuttings") == pytest.approx(6 / 8)
    carbonate = [item for item in evidence.intersections if item.kind == "calcimetry"]
    assert {item.source_id for item in carbonate} == {"sample-in", "second"}
    assert {item.attributes[0][1] for item in carbonate} == {90.0, 97.0}
    assert all(0 < item.overlap_fraction <= 1 for item in carbonate)


@pytest.mark.parametrize("bad_depth", (float("nan"), float("inf"), float("-inf")))
def test_nonfinite_md_sample_rejects_geology_correlation_without_discarding_row(bad_depth):
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None
    source_values = dataset.curves["curve-c1"].values.copy()
    original_well = repr(session.current_well)
    # The other MD rows still span the gas interval. Dropping this row used
    # to make an incomplete axis appear valid for geological evidence.
    dataset.active_index.values[1] = bad_depth
    before_depth = dataset.active_index.values.copy()
    edited_well = repr(session.current_well)
    # The setup intentionally changes one MD sample. Correlation itself must
    # neither repair nor rewrite that malformed source axis.
    assert edited_well != original_well
    with pytest.raises(ValueError, match="one-dimensional finite numeric MD axis"):
        _intersect(session)
    np.testing.assert_array_equal(dataset.active_index.values, before_depth)
    np.testing.assert_array_equal(dataset.curves["curve-c1"].values, source_values)
    assert repr(session.current_well) == edited_well


@pytest.mark.parametrize("depth", (
    np.array(["1000", "1005", "1010", "1015"]),
    np.array([1000, 1005, 1010, 1015], dtype=object),
    np.array([[1000.0, 1005.0], [1010.0, 1015.0]]),
))
def test_coercible_text_object_or_multidimensional_md_is_not_verified(depth):
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None
    dataset.active_index.values = depth
    original = depth.copy()
    with pytest.raises(ValueError, match="one-dimensional finite numeric MD axis"):
        _intersect(session)
    np.testing.assert_array_equal(dataset.active_index.values, original)


@pytest.mark.parametrize("depth", (
    [1015.0, 1010.0, 1005.0, 1000.0],
    [1000.0, 1005.0, 1005.0, 1015.0],
))
def test_finite_md_correlation_preserves_descending_and_stationary_source_order(depth):
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None
    dataset.active_index.values[:] = depth
    original = dataset.active_index.values.copy()
    observed = _intersect(session)
    assert observed.coverage("lithology") == pytest.approx(6 / 8)
    assert observed.coverage("cuttings") == pytest.approx(5 / 8)
    assert observed.depth_axis_id == dataset.active_index_id
    np.testing.assert_array_equal(dataset.active_index.values, original)


def test_signed_geology_selection_fails_closed_after_md_becomes_nonfinite():
    from test_interpretation_geology_evidence_signed_pdf import _actual_source
    from geoworkbench.services.interpretation_geology_evidence_export import (
        verified_session_geology_evidence,
    )

    session, report, selected = _actual_source()
    assert verified_session_geology_evidence(session, report, (selected,)) == (selected,)
    session.current_dataset.active_index.values[1] = np.nan
    with pytest.raises(ValueError, match="one-dimensional finite numeric MD axis"):
        verified_session_geology_evidence(session, report, (selected,))


def test_time_tvd_and_unknown_units_are_refused_without_depth_conversion() -> None:
    for typ, role, unit in (
        (IndexType.RELATIVE_TIME, IndexRole.TIME, "s"),
        (IndexType.TVD, IndexRole.DEPTH, "m"),
        (IndexType.TVDSS, IndexRole.DEPTH, "m"),
        (IndexType.MD, IndexRole.DEPTH, "ft"),
    ):
        session = _session()
        dataset = session.current_dataset
        assert dataset is not None
        index = DatasetIndex(
            "alternate", "ALTERNATE", typ, role, unit,
            np.array([1000.0, 1005.0, 1010.0, 1015.0]),
        )
        dataset.add_index(index, make_active=True)
        with pytest.raises(ValueError, match="explicit metre MD"):
            _intersect(session)


def test_invalid_or_outside_gas_intervals_never_produce_geology_claims() -> None:
    session = _session()
    for top, bottom in (
        (1002.0, 1002.0),
        (1010.0, 1002.0),
        (nan, 1010.0),
        (999.0, 1004.0),
        (1004.0, 1016.0),
    ):
        with pytest.raises(ValueError):
            _intersect(session, top, bottom)


@pytest.mark.parametrize("side", ("top", "bottom"))
@pytest.mark.parametrize("invalid_type", ("numeric_text", "boolean", "array", "object_scalar", "none"))
def test_requested_interval_rejects_non_numeric_md_without_changing_sources(side, invalid_type):
    session = _session()
    dataset, well = session.current_dataset, session.current_well
    assert dataset is not None and well is not None
    selected = {"top": 1002.0, "bottom": 1010.0}
    nominal = selected[side]
    value = {
        "numeric_text": str(nominal),
        "boolean": True,
        "array": np.array([nominal]),
        "object_scalar": np.array(nominal, dtype=object),
        "none": None,
    }[invalid_type]
    selected[side] = value
    before_well = repr(well)
    before_axis = dataset.active_index.values.copy()
    before_curve = dataset.curves["curve-c1"].values.copy()

    with pytest.raises(ValueError, match="finite numeric MD depths"):
        _intersect(session, **selected)

    assert repr(well) == before_well
    np.testing.assert_array_equal(dataset.active_index.values, before_axis)
    np.testing.assert_array_equal(dataset.curves["curve-c1"].values, before_curve)


@pytest.mark.parametrize(("top", "bottom"), (
    (np.int64(1002), np.float64(1010.0)),
    (np.float32(1002.0), np.int32(1010)),
    (np.array(1002.0), np.array(1010.0)),
))
def test_requested_interval_keeps_explicit_numeric_md_scalars(top, bottom):
    session = _session()
    result = _intersect(session, top, bottom)
    assert (result.gas_top, result.gas_bottom, result.depth_unit) == (1002.0, 1010.0, "m")
    assert result.coverage("lithology") == pytest.approx(6 / 8)
    assert result.coverage("cuttings") == pytest.approx(5 / 8)


def test_touching_boundaries_are_not_observations() -> None:
    session = _session()
    well = session.current_well
    assert well is not None
    well.lithology.clear()
    well.cuttings.clear()
    well.stratigraphy.append(StratigraphyInterval("contact", 1000.0, 1005.0, "C"))
    evidence = _intersect(session, 1005.0, 1010.0)
    assert evidence.intersections == ()
    assert evidence.coverage("stratigraphy") == 0.0
    assert evidence.missing_kinds == (
        "lithology", "cuttings", "lba", "calcimetry", "stratigraphy",
    )


@pytest.mark.parametrize("source_kind", ("lithology", "cuttings", "stratigraphy"))
@pytest.mark.parametrize("bad_bound", (float("nan"), float("inf"), float("-inf"), "1004.0", True))
def test_corrupt_source_geology_md_bounds_never_become_missing_evidence(source_kind, bad_bound):
    session = _session()
    well = session.current_well
    dataset = session.current_dataset
    assert well is not None and dataset is not None
    if source_kind == "stratigraphy":
        well.stratigraphy.append(StratigraphyInterval(
            "invalid-stratum", 1004.0, 1009.0, "C1",
        ))
    record = {
        "lithology": well.lithology,
        "cuttings": well.cuttings,
        "stratigraphy": well.stratigraphy,
    }[source_kind][0]
    record.top_depth = bad_bound
    before_record = repr(well)
    before_depth = dataset.depth.copy()
    before_curve = dataset.curves["curve-c1"].values.copy()

    with pytest.raises(ValueError, match="finite numeric MD bounds"):
        _intersect(session)

    assert repr(well) == before_record
    np.testing.assert_array_equal(dataset.depth, before_depth)
    np.testing.assert_array_equal(dataset.curves["curve-c1"].values, before_curve)


def test_valid_outside_source_records_still_do_not_inflate_coverage():
    session = _session()
    evidence = _intersect(session)
    assert evidence.coverage("lithology") == pytest.approx(6 / 8)
    assert evidence.coverage("cuttings") == pytest.approx(5 / 8)
    assert all(item.source_id not in {"lith-out", "sample-out"} for item in evidence.intersections)


def test_finite_md_bounds_with_overflowing_span_are_rejected_without_source_changes():
    session = _session()
    dataset = session.current_dataset
    dataset.active_index.values = np.array([-1e308, 1e308])
    before = repr(session.current_well)
    depths = dataset.depth.copy()
    with pytest.raises(ValueError, match="finite MD"):
        _intersect(session, -1e308, 1e308)
    assert repr(session.current_well) == before
    np.testing.assert_array_equal(dataset.depth, depths)


def test_evidence_gap_and_attribute_coverage_reject_overflowing_span():
    evidence = replace(_intersect(_session()), gas_top=-1e308, gas_bottom=1e308)
    with pytest.raises(ValueError, match="finite MD"):
        evidence.uncovered_intervals("lithology")
    with pytest.raises(ValueError, match="finite MD"):
        evidence.attribute_coverage("lithology", "lithotype_id")


def test_large_representable_md_span_keeps_measured_coverage():
    session = _session()
    session.current_dataset.active_index.values = np.array([-1e307, 1e307])
    session.current_well.lithology[0].top_depth = -1e307
    session.current_well.lithology[0].bottom_depth = 0.0
    evidence = _intersect(session, -1e307, 1e307)
    assert evidence.coverage("lithology") == pytest.approx(0.5)


@pytest.mark.parametrize("code", (None, True, 123, np.array(["C1"])))
def test_non_text_stratigraphy_code_cannot_become_measured_evidence(code):
    session = _session()
    well = session.current_well
    well.stratigraphy.append(StratigraphyInterval("invalid-code", 1004.0, 1009.0, code))
    before = repr(well)
    with pytest.raises(ValueError, match="text stratigraphy code"):
        _intersect(session)
    assert repr(well) == before


@pytest.mark.parametrize("code", ("", "   ", " C1 "))
def test_text_stratigraphy_codes_keep_blank_and_trimmed_behavior(code):
    session = _session()
    session.current_well.stratigraphy.append(
        StratigraphyInterval("stratum", 1004.0, 1009.0, code),
    )
    evidence = _intersect(session)
    observed = [item for item in evidence.intersections if item.kind == "stratigraphy"]
    if code.strip():
        assert observed[0].attributes == (("code", "C1"),)
        assert evidence.coverage("stratigraphy") == pytest.approx(5 / 8)
    else:
        assert observed == []
        assert evidence.coverage("stratigraphy") == 0.0


@pytest.mark.parametrize("sample_index", (0, 1))
@pytest.mark.parametrize("bad_fraction", (
    float("nan"), float("inf"), float("-inf"), -1.0, 101.0,
    "70.0", True, None, np.array([70.0]), np.array(70.0, dtype=object),
))
def test_corrupt_cuttings_percentage_never_becomes_incomplete_measured_evidence(
    sample_index, bad_fraction,
):
    session = _session()
    well, dataset = session.current_well, session.current_dataset
    assert well is not None and dataset is not None
    # Even samples outside the request must not be silently discarded.
    component = well.cuttings[sample_index].components[0]
    component.percentage = bad_fraction
    before_well = repr(well)
    before_md = dataset.active_index.values.copy()
    before_curve = dataset.curves["curve-c1"].values.copy()

    with pytest.raises(ValueError, match="finite numeric cuttings percentages"):
        _intersect(session)

    assert repr(well) == before_well
    np.testing.assert_array_equal(dataset.active_index.values, before_md)
    np.testing.assert_array_equal(dataset.curves["curve-c1"].values, before_curve)


@pytest.mark.parametrize(("first", "second"), (
    (0.0, 100.0),
    (np.int64(70), np.float32(30.0)),
    (np.array(70.0), np.array(30.0)),
))
def test_valid_cuttings_component_percentages_keep_measured_source_evidence(
    first, second,
):
    session = _session()
    well = session.current_well
    assert well is not None
    well.cuttings[0].components[0].percentage = first
    well.cuttings[0].components[1].percentage = second
    before = repr(well)
    evidence = _intersect(session)
    samples = [item for item in evidence.intersections if item.kind == "cuttings"]
    assert len(samples) == 1
    assert samples[0].source_id == "sample-in"
    assert ("lithotype:sandstone", float(first)) in samples[0].attributes
    assert ("lithotype:clay", float(second)) in samples[0].attributes
    assert evidence.coverage("cuttings") == pytest.approx(5 / 8)
    assert repr(well) == before
