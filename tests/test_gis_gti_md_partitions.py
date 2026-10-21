from dataclasses import FrozenInstanceError, replace

import pytest

from geoworkbench.services.gis_gti_lithology_screening import (
    EvidenceOrigin, FluidAssessment, IntervalObservation, ObservationKind,
    ObservationQuality, ReservoirAssessment, RockFamily, review_gis_gti_intervals,
)


def _obs(kind, origin, top, bottom, source="source", quality=ObservationQuality.VALIDATED):
    return IntervalObservation(kind, origin, source, "md-1", top, bottom, quality,
                               "explicit-calibration" if origin is EvidenceOrigin.GIS else "")


def _review(observations=(), **changes):
    args = dict(top_md_m=100.0, bottom_md_m=110.0, depth_axis_id="md-1",
                rock_family=RockFamily.CLASTIC, observations=observations)
    args.update(changes)
    return review_gis_gti_intervals(**args)


def _bounds(result):
    return [(item.top_md_m, item.bottom_md_m) for item in result]


def test_disjoint_gis_and_gas_do_not_form_a_false_combined_candidate():
    observations = (
        _obs(ObservationKind.EFFECTIVE_POROSITY, EvidenceOrigin.GIS, 100, 104, "phi"),
        _obs(ObservationKind.CALIBRATED_LOW_SW, EvidenceOrigin.GIS, 100, 104, "sw"),
        _obs(ObservationKind.GAS_SHOW, EvidenceOrigin.MUD_GAS, 106, 110, "gas"),
    )
    result = _review(observations)
    assert _bounds(result) == [(100, 104), (104, 106), (106, 110)]
    assert all(item.fluid is FluidAssessment.UNDETERMINED for item in result)
    assert all(not item.shortlist_for_geologist for item in result)
    assert result[0].reservoir is ReservoirAssessment.CANDIDATE
    assert result[1].accepted_evidence_ids == ()
    assert "no_validated_evidence" in result[1].reason_codes
    assert result[2].accepted_evidence_ids == ("gas",)
    assert observations[0].bottom_md_m == 104
    with pytest.raises(FrozenInstanceError):
        result[0].top_md_m = 0


def test_hydrocarbon_candidate_exists_only_on_actual_shared_md():
    result = _review((
        _obs(ObservationKind.EFFECTIVE_POROSITY, EvidenceOrigin.GIS, 100, 110, "phi"),
        _obs(ObservationKind.CALIBRATED_LOW_SW, EvidenceOrigin.GIS, 102, 108, "sw"),
        _obs(ObservationKind.GAS_SHOW, EvidenceOrigin.MUD_GAS, 104, 106, "gas"),
    ))
    assert _bounds(result) == [(100, 102), (102, 104), (104, 106), (106, 108), (108, 110)]
    assert [item.shortlist_for_geologist for item in result] == [False, False, True, False, False]
    assert result[2].fluid is FluidAssessment.HC_CANDIDATE
    assert result[2].accepted_evidence_ids == ("phi", "sw", "gas")


def test_separate_tests_do_not_conflict_and_touching_boundaries_are_not_shared():
    result = _review((
        _obs(ObservationKind.TEST_OIL, EvidenceOrigin.FORMATION_TEST, 100, 105, "oil"),
        _obs(ObservationKind.TEST_WATER, EvidenceOrigin.FORMATION_TEST, 105, 110, "water"),
    ))
    assert _bounds(result) == [(100, 105), (105, 110)]
    assert [item.fluid for item in result] == [FluidAssessment.TEST_OIL, FluidAssessment.TEST_WATER]
    assert result[0].shortlist_for_geologist and not result[1].shortlist_for_geologist


def test_overlapping_tests_keep_conflict_only_where_both_cover():
    result = _review((
        _obs(ObservationKind.TEST_GAS, EvidenceOrigin.FORMATION_TEST, 99, 106, "gas"),
        _obs(ObservationKind.TEST_WATER, EvidenceOrigin.FORMATION_TEST, 104, 111, "water"),
    ))
    assert _bounds(result) == [(100, 104), (104, 106), (106, 110)]
    assert [item.fluid for item in result] == [
        FluidAssessment.TEST_GAS, FluidAssessment.TEST_CONFLICT, FluidAssessment.TEST_WATER,
    ]
    assert "multiple_test_fluids_require_interval_review" in result[1].reason_codes
    assert not result[1].shortlist_for_geologist


def test_suspect_evidence_has_local_qc_without_promoting_a_candidate():
    result = _review((
        _obs(ObservationKind.GAS_SHOW, EvidenceOrigin.MUD_GAS, 102, 108, "gas",
             ObservationQuality.SUSPECT),
    ))
    assert _bounds(result) == [(100, 102), (102, 108), (108, 110)]
    assert result[1].disregarded_evidence_ids == ("gas",)
    assert result[0].disregarded_evidence_ids == result[2].disregarded_evidence_ids == ()
    assert all(item.accepted_evidence_ids == () for item in result)
    assert all(not item.shortlist_for_geologist for item in result)


@pytest.mark.parametrize("observations", [(), (
    _obs(ObservationKind.GAS_SHOW, EvidenceOrigin.MUD_GAS, 90, 100),
    _obs(ObservationKind.GAS_SHOW, EvidenceOrigin.MUD_GAS, 110, 120),
)])
def test_empty_or_merely_touching_window_remains_one_unknown_cell(observations):
    result = _review(observations)
    assert _bounds(result) == [(100, 110)]
    assert result[0].reservoir is ReservoirAssessment.UNKNOWN
    assert result[0].accepted_evidence_ids == ()


def test_input_order_and_repeated_boundaries_do_not_create_zero_width_cells():
    early = _obs(ObservationKind.GAS_SHOW, EvidenceOrigin.MUD_GAS, 100, 110, "early")
    late = _obs(ObservationKind.LBA_SHOW, EvidenceOrigin.GEOLOGY, 102, 108, "late")
    result = _review((late, early, replace(late, source_id="other")))
    assert _bounds(result) == [(100, 102), (102, 108), (108, 110)]
    assert result[1].accepted_evidence_ids == ("late", "early", "other")


@pytest.mark.parametrize("change", [
    {"depth_axis_id": "other-axis"}, {"source_id": ""},
    {"top_md_m": float("nan")}, {"top_md_m": 125}, {"quality": "validated"},
])
def test_invalid_out_of_window_observation_is_not_silently_ignored(change):
    observation = _obs(ObservationKind.GAS_SHOW, EvidenceOrigin.MUD_GAS, 120, 125)
    with pytest.raises((ValueError, TypeError)):
        _review((replace(observation, **change),))


@pytest.mark.parametrize("changes", [
    {"top_md_m": True}, {"bottom_md_m": float("inf")}, {"bottom_md_m": 100},
    {"depth_axis_id": ""}, {"rock_family": "clastic"}, {"observations": []},
])
def test_partition_api_preserves_existing_input_guards(changes):
    with pytest.raises((ValueError, TypeError)):
        _review(**changes)


def test_sparse_evidence_keeps_all_gaps_and_conserves_requested_length():
    observations = tuple(
        _obs(ObservationKind.GAS_SHOW, EvidenceOrigin.MUD_GAS, i, i + 0.25, str(i))
        for i in range(100, 110)
    )
    result = _review(observations)
    assert len(result) == 20
    assert sum(item.bottom_md_m-item.top_md_m for item in result) == pytest.approx(10)
    assert all(first.bottom_md_m == second.top_md_m for first, second in zip(result, result[1:]))
    assert sum(bool(item.accepted_evidence_ids) for item in result) == 10


def test_unrepresentable_window_or_observation_width_is_rejected():
    top = 2**53
    with pytest.raises(ValueError):
        _review(top_md_m=top, bottom_md_m=top+1)
    observation = _obs(ObservationKind.GAS_SHOW, EvidenceOrigin.MUD_GAS, top, top+1)
    with pytest.raises(ValueError):
        _review((observation,))
