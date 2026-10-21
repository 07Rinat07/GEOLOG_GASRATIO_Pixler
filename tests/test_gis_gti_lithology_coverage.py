from dataclasses import FrozenInstanceError, replace

import pytest

from geoworkbench.services.gis_gti_lithology_screening import (
    EvidenceOrigin, FluidAssessment, IntervalObservation, LithologyObservation,
    ObservationKind, ObservationQuality, ReservoirAssessment, RockFamily,
    review_gis_gti_lithology_intervals,
)


def _rock(top, bottom, family=RockFamily.CLASTIC, source="rock",
          quality=ObservationQuality.VALIDATED):
    return LithologyObservation(source, "md-1", top, bottom, family, quality)


def _gas(top=100, bottom=110):
    return IntervalObservation(ObservationKind.GAS_SHOW, EvidenceOrigin.MUD_GAS,
                               "gas", "md-1", top, bottom, ObservationQuality.VALIDATED)


def _review(lithology=(), observations=(), **changes):
    args = dict(top_md_m=100.0, bottom_md_m=110.0, depth_axis_id="md-1",
                lithology=lithology, observations=observations)
    args.update(changes)
    return review_gis_gti_lithology_intervals(**args)


def _bounds(cells):
    return [(cell.review.top_md_m, cell.review.bottom_md_m) for cell in cells]


def test_changing_rocks_and_evidence_share_exact_cells_without_a_default_family():
    rocks = (_rock(99, 104, source="sand"), _rock(106, 111, RockFamily.HALITE, "salt"))
    gas = _gas(102, 108)
    cells = _review(rocks, (gas,))
    assert _bounds(cells) == [(100, 102), (102, 104), (104, 106), (106, 108), (108, 110)]
    assert [cell.review.rock_family for cell in cells] == [
        RockFamily.CLASTIC, RockFamily.CLASTIC, RockFamily.UNKNOWN_OR_MIXED,
        RockFamily.HALITE, RockFamily.HALITE,
    ]
    assert cells[2].lithology_source_ids == ()
    assert cells[2].lithology_issues == ("no_validated_lithology",)
    assert cells[3].review.reservoir is ReservoirAssessment.ATYPICAL_UNVERIFIED
    assert cells[1].review.accepted_evidence_ids == ("gas",)
    assert all(not cell.review.shortlist_for_geologist for cell in cells)
    assert rocks[0].top_md_m == 99 and gas.top_md_m == 102
    with pytest.raises(FrozenInstanceError):
        cells[0].lithology_source_ids = ()


def test_conflicting_lithology_is_local_and_neither_record_wins():
    cells = _review((_rock(100, 106, source="a"), _rock(104, 110, RockFamily.HALITE, "b")))
    assert _bounds(cells) == [(100, 104), (104, 106), (106, 110)]
    assert cells[1].review.rock_family is RockFamily.UNKNOWN_OR_MIXED
    assert cells[1].lithology_source_ids == ("a", "b")
    assert cells[1].lithology_issues == ("conflicting_lithology_requires_review",)
    assert cells[0].lithology_issues == cells[2].lithology_issues == ()


def test_matching_overlaps_preserve_source_order_without_conflict_or_zero_width():
    cells = _review((_rock(104, 110, source="later"), _rock(100, 106, source="earlier")))
    assert _bounds(cells) == [(100, 104), (104, 106), (106, 110)]
    assert cells[1].lithology_source_ids == ("later", "earlier")
    assert all(cell.review.rock_family is RockFamily.CLASTIC for cell in cells)
    assert all(cell.lithology_issues == () for cell in cells)


def test_touching_different_rocks_do_not_conflict():
    cells = _review((_rock(100, 105, source="a"), _rock(105, 110, RockFamily.HALITE, "b")))
    assert _bounds(cells) == [(100, 105), (105, 110)]
    assert [cell.lithology_source_ids for cell in cells] == [("a",), ("b",)]
    assert all(cell.lithology_issues == () for cell in cells)


@pytest.mark.parametrize("quality", [ObservationQuality.SUSPECT, ObservationQuality.REJECTED])
def test_untrusted_lithology_is_local_and_never_overrides_validated_rock(quality):
    cells = _review((
        _rock(100, 110, source="good"),
        _rock(102, 108, RockFamily.HALITE, "uncertain", quality),
    ))
    assert _bounds(cells) == [(100, 102), (102, 108), (108, 110)]
    assert all(cell.review.rock_family is RockFamily.CLASTIC for cell in cells)
    assert cells[1].lithology_source_ids == ("good",)
    assert cells[1].disregarded_lithology_ids == ("uncertain",)
    assert cells[1].lithology_issues == ("suspect_or_rejected_lithology_not_used",)
    assert cells[0].disregarded_lithology_ids == cells[2].disregarded_lithology_ids == ()


def test_only_suspect_rock_leaves_unknown_and_retains_both_qc_reasons():
    cells = _review((_rock(100, 110, quality=ObservationQuality.SUSPECT),))
    assert cells[0].review.rock_family is RockFamily.UNKNOWN_OR_MIXED
    assert cells[0].lithology_source_ids == ()
    assert cells[0].disregarded_lithology_ids == ("rock",)
    assert cells[0].lithology_issues == (
        "no_validated_lithology", "suspect_or_rejected_lithology_not_used",
    )


def test_recorded_unknown_is_distinct_from_missing_lithology():
    known_record = _review((_rock(100, 110, RockFamily.UNKNOWN_OR_MIXED),))[0]
    missing = _review()[0]
    assert known_record.review.rock_family is missing.review.rock_family is RockFamily.UNKNOWN_OR_MIXED
    assert known_record.lithology_source_ids == ("rock",)
    assert known_record.lithology_issues == ()
    assert missing.lithology_issues == ("no_validated_lithology",)


@pytest.mark.parametrize("rocks", [(), (
    _rock(100, 110, source="a"), _rock(100, 110, RockFamily.HALITE, "b"),
)])
def test_independent_formation_test_authority_survives_lithology_uncertainty(rocks):
    test = IntervalObservation(ObservationKind.TEST_GAS, EvidenceOrigin.FORMATION_TEST,
                               "test", "md-1", 100, 110, ObservationQuality.VALIDATED)
    cell = _review(rocks, (test,))[0]
    assert cell.review.fluid is FluidAssessment.TEST_GAS
    assert cell.review.reservoir is ReservoirAssessment.DYNAMIC_SUPPORT
    assert cell.review.shortlist_for_geologist
    assert cell.lithology_issues


@pytest.mark.parametrize("change", [
    {"depth_axis_id": "other"}, {"source_id": ""}, {"rock_family": "clastic"},
    {"quality": "validated"}, {"top_md_m": True}, {"bottom_md_m": float("nan")},
    {"bottom_md_m": 120},
])
def test_invalid_off_window_lithology_is_rejected_before_partition(change):
    rock = replace(_rock(120, 125), **change)
    with pytest.raises((ValueError, TypeError)):
        _review((rock,))


@pytest.mark.parametrize("rocks", [[], (object(),)])
def test_lithology_container_and_item_types_are_explicit(rocks):
    with pytest.raises(TypeError):
        _review(rocks)


def test_foreign_off_window_evidence_cannot_hide_behind_valid_lithology():
    with pytest.raises(ValueError, match="different MD axes"):
        _review((_rock(100, 110),), (replace(_gas(120, 125), depth_axis_id="other"),))


def test_empty_inputs_keep_one_unknown_cell_and_full_requested_span():
    cells = _review()
    assert _bounds(cells) == [(100, 110)]
    assert cells[0].review.reason_codes == ("no_validated_evidence",)
    assert cells[0].lithology_issues == ("no_validated_lithology",)


def test_sparse_lithology_and_evidence_keep_every_gap_and_conserve_length():
    rocks = tuple(_rock(i, i + 0.25, source=str(i)) for i in range(100, 110))
    cells = _review(rocks, (_gas(101, 109),))
    assert sum(cell.review.bottom_md_m-cell.review.top_md_m for cell in cells) == pytest.approx(10)
    assert sum(bool(cell.lithology_source_ids) for cell in cells) == 10
    assert all(first.review.bottom_md_m == second.review.top_md_m
               for first, second in zip(cells, cells[1:]))
