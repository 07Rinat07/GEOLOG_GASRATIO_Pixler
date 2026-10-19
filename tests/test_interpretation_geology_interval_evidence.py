"""INTERP-GEO-01: depth coverage, traceable measurements, unknown != negative."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
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
