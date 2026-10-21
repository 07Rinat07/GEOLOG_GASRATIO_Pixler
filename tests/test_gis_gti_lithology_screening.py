"""INTERP-FUSION-01: verified observations, no automatic geological pay verdict."""

import pytest

from geoworkbench.services.gis_gti_lithology_screening import (
    EvidenceOrigin, FluidAssessment, IntervalObservation, ObservationKind,
    ObservationQuality, ReservoirAssessment, RockFamily,
    review_gis_gti_interval,
)

AXIS = "dataset-well1/md-m-verified"


def gis(kind: ObservationKind, *, quality: ObservationQuality = ObservationQuality.VALIDATED,
        axis: str = AXIS, top: float = 1000.0, bottom: float = 1010.0) -> IntervalObservation:
    return IntervalObservation(kind, EvidenceOrigin.GIS, f"gis:{kind.value}",
                               axis, top, bottom, quality, "petrophysicist-profile-v1")


def gas(top: float = 1000.0, bottom: float = 1010.0) -> IntervalObservation:
    return IntervalObservation(ObservationKind.GAS_SHOW, EvidenceOrigin.MUD_GAS,
                               "mudlog:C1-C5", AXIS, top, bottom, ObservationQuality.VALIDATED)


def lba() -> IntervalObservation:
    return IntervalObservation(ObservationKind.LBA_SHOW, EvidenceOrigin.GEOLOGY,
                               "cuttings:sample-01", AXIS, 1000.0, 1010.0,
                               ObservationQuality.VALIDATED)


def test_gis_porosity_sw_and_gti_gas_shortlist_unconfirmed_hc_not_oil() -> None:
    output = review_gis_gti_interval(
        top_md_m=1000, bottom_md_m=1010, depth_axis_id=AXIS,
        rock_family=RockFamily.CARBONATE,
        observations=(gis(ObservationKind.EFFECTIVE_POROSITY),
                      gis(ObservationKind.CALIBRATED_LOW_SW), gas()),
    )
    assert output.fluid is FluidAssessment.HC_CANDIDATE
    assert output.reservoir is ReservoirAssessment.CANDIDATE
    assert output.shortlist_for_geologist
    assert "prospect_review_not_commercial_pay" in output.reason_codes
    assert "low_sw_not_oil_versus_gas_discriminator" in output.reason_codes


def test_gis_gas_effect_plus_mud_gas_without_porosity_does_not_classify_gas() -> None:
    result = review_gis_gti_interval(
        top_md_m=1000, bottom_md_m=1010, depth_axis_id=AXIS,
        rock_family=RockFamily.ARGILLACEOUS,
        observations=(gis(ObservationKind.GAS_EFFECT), gas()),
    )
    assert result.fluid is FluidAssessment.UNDETERMINED
    assert result.reservoir is ReservoirAssessment.ATYPICAL_UNVERIFIED
    assert not result.shortlist_for_geologist
    assert "hydrocarbon_show_without_verified_reservoir" in result.reason_codes


def test_gis_porosity_plus_gas_effect_and_mud_gas_is_gas_candidate() -> None:
    result = review_gis_gti_interval(
        top_md_m=1000, bottom_md_m=1010, depth_axis_id=AXIS,
        rock_family=RockFamily.CLASTIC,
        observations=(gis(ObservationKind.GAS_EFFECT),
                      gis(ObservationKind.EFFECTIVE_POROSITY), gas()),
    )
    assert result.fluid is FluidAssessment.GAS_CANDIDATE
    assert result.shortlist_for_geologist


@pytest.mark.parametrize("rock", (
    RockFamily.ARGILLACEOUS, RockFamily.HALITE, RockFamily.SULFATE,
    RockFamily.VOLCANIC, RockFamily.COAL_OR_ORGANIC,
))
def test_atypical_lithology_does_not_diagnose_reservoir_from_gas_only(rock: RockFamily) -> None:
    result = review_gis_gti_interval(
        top_md_m=1000, bottom_md_m=1010, depth_axis_id=AXIS,
        rock_family=rock, observations=(gas(), lba()),
    )
    assert result.reservoir is ReservoirAssessment.ATYPICAL_UNVERIFIED
    assert result.fluid is FluidAssessment.UNDETERMINED
    assert not result.shortlist_for_geologist
    assert "atypical_rock_requires_secondary_storage_or_test" in result.reason_codes


def test_fractured_volcanic_rock_not_absolutely_excluded() -> None:
    result = review_gis_gti_interval(
        top_md_m=1000, bottom_md_m=1010, depth_axis_id=AXIS,
        rock_family=RockFamily.VOLCANIC,
        observations=(gis(ObservationKind.FRACTURES),
                      gis(ObservationKind.EFFECTIVE_POROSITY),
                      gis(ObservationKind.CALIBRATED_LOW_SW), gas()),
    )
    assert result.reservoir is ReservoirAssessment.CANDIDATE
    assert result.fluid is FluidAssessment.HC_CANDIDATE
    assert result.shortlist_for_geologist


def test_water_saturation_does_not_claim_oil_and_no_spurious_pay() -> None:
    result = review_gis_gti_interval(
        top_md_m=1000, bottom_md_m=1010, depth_axis_id=AXIS,
        rock_family=RockFamily.CARBONATE,
        observations=(gis(ObservationKind.EFFECTIVE_POROSITY),
                      gis(ObservationKind.CALIBRATED_HIGH_SW)),
    )
    assert result.fluid is FluidAssessment.WATER_CANDIDATE
    assert not result.shortlist_for_geologist


def test_water_test_overrides_mudgas_hypothesis_but_preserves_conflict() -> None:
    water = IntervalObservation(
        ObservationKind.TEST_WATER, EvidenceOrigin.FORMATION_TEST,
        "test:fluid-sample-01", AXIS, 1000, 1010, ObservationQuality.VALIDATED,
    )
    result = review_gis_gti_interval(
        top_md_m=1000, bottom_md_m=1010, depth_axis_id=AXIS,
        rock_family=RockFamily.CARBONATE,
        observations=(gis(ObservationKind.EFFECTIVE_POROSITY),
                      gis(ObservationKind.CALIBRATED_LOW_SW), gas(), water),
    )
    assert result.fluid is FluidAssessment.TEST_WATER
    assert not result.shortlist_for_geologist
    assert "water_test_vs_hydrocarbon_indicators" in result.reason_codes


@pytest.mark.parametrize(("kind", "expected"), (
    (ObservationKind.TEST_GAS, FluidAssessment.TEST_GAS),
    (ObservationKind.TEST_OIL, FluidAssessment.TEST_OIL),
    (ObservationKind.TEST_WATER, FluidAssessment.TEST_WATER),
))
def test_actual_test_result_is_identified_distinctly_from_gis(
    kind: ObservationKind, expected: FluidAssessment,
) -> None:
    test = IntervalObservation(
        kind, EvidenceOrigin.FORMATION_TEST, "test:recovered-fluid",
        AXIS, 1000, 1010, ObservationQuality.VALIDATED,
    )
    output = review_gis_gti_interval(
        top_md_m=1000, bottom_md_m=1010, depth_axis_id=AXIS,
        rock_family=RockFamily.HALITE, observations=(test,),
    )
    assert output.fluid is expected
    assert ("atypical_rock_requires_secondary_storage_or_test" in output.reason_codes)
    if kind is ObservationKind.TEST_WATER:
        assert not output.shortlist_for_geologist
    else:
        assert output.reservoir is ReservoirAssessment.DYNAMIC_SUPPORT
        assert output.shortlist_for_geologist


def test_different_tested_fluids_require_geological_review() -> None:
    tests = tuple(
        IntervalObservation(kind, EvidenceOrigin.FORMATION_TEST, f"test:{kind.value}",
                            AXIS, 1000, 1010, ObservationQuality.VALIDATED)
        for kind in (ObservationKind.TEST_WATER, ObservationKind.TEST_GAS)
    )
    output = review_gis_gti_interval(
        top_md_m=1000, bottom_md_m=1010, depth_axis_id=AXIS,
        rock_family=RockFamily.CARBONATE, observations=tests,
    )
    assert output.fluid is FluidAssessment.TEST_CONFLICT
    assert not output.shortlist_for_geologist


def test_conflicting_calibrated_sw_never_shortlists() -> None:
    output = review_gis_gti_interval(
        top_md_m=1000, bottom_md_m=1010, depth_axis_id=AXIS,
        rock_family=RockFamily.CARBONATE,
        observations=(gis(ObservationKind.EFFECTIVE_POROSITY), gas(),
                      gis(ObservationKind.CALIBRATED_HIGH_SW),
                      gis(ObservationKind.CALIBRATED_LOW_SW)),
    )
    assert "competing_water_saturation_interpretations" in output.reason_codes
    assert not output.shortlist_for_geologist


def test_suspect_gis_is_not_treated_as_validated() -> None:
    output = review_gis_gti_interval(
        top_md_m=1000, bottom_md_m=1010, depth_axis_id=AXIS,
        rock_family=RockFamily.CARBONATE,
        observations=(gis(ObservationKind.EFFECTIVE_POROSITY,
                          quality=ObservationQuality.SUSPECT),
                      gis(ObservationKind.CALIBRATED_LOW_SW), gas()),
    )
    assert output.fluid is FluidAssessment.UNDETERMINED
    assert not output.shortlist_for_geologist
    assert "gis:effective_porosity" in output.disregarded_evidence_ids


def test_other_depth_axes_or_missing_calibration_fail_explicitly() -> None:
    with pytest.raises(ValueError, match="different MD axes"):
        review_gis_gti_interval(
            top_md_m=1000, bottom_md_m=1010, depth_axis_id=AXIS,
            rock_family=RockFamily.CARBONATE,
            observations=(gis(ObservationKind.EFFECTIVE_POROSITY, axis="TVD"),),
        )
    uncalibrated = IntervalObservation(
        ObservationKind.CALIBRATED_LOW_SW, EvidenceOrigin.GIS,
        "gis:uncalibrated", AXIS, 1000, 1010, ObservationQuality.VALIDATED,
    )
    with pytest.raises(ValueError, match="calibration ID"):
        review_gis_gti_interval(
            top_md_m=1000, bottom_md_m=1010, depth_axis_id=AXIS,
            rock_family=RockFamily.CARBONATE,
            observations=(uncalibrated,),
        )


def test_wrong_source_for_gis_observation_is_rejected() -> None:
    wrong = IntervalObservation(
        ObservationKind.CALIBRATED_HIGH_SW, EvidenceOrigin.MUD_GAS,
        "mudgas:unknown", AXIS, 1000, 1010, ObservationQuality.VALIDATED,
        "archie-calibrated",
    )
    with pytest.raises(ValueError, match="inconsistent"):
        review_gis_gti_interval(
            top_md_m=1000, bottom_md_m=1010, depth_axis_id=AXIS,
            rock_family=RockFamily.CARBONATE, observations=(wrong,),
        )


def test_touching_interval_is_not_overlap_and_missing_is_not_negative() -> None:
    output = review_gis_gti_interval(
        top_md_m=1010, bottom_md_m=1020, depth_axis_id=AXIS,
        rock_family=RockFamily.UNKNOWN_OR_MIXED, observations=(gas(),),
    )
    assert output.accepted_evidence_ids == ()
    assert output.fluid is FluidAssessment.UNDETERMINED
    assert "no_validated_evidence" in output.reason_codes


def test_tight_and_fracture_support_are_conflicting_not_banned() -> None:
    output = review_gis_gti_interval(
        top_md_m=1000, bottom_md_m=1010, depth_axis_id=AXIS,
        rock_family=RockFamily.ARGILLACEOUS,
        observations=(gis(ObservationKind.TIGHT_MATRIX), gis(ObservationKind.FRACTURES),
                      gis(ObservationKind.EFFECTIVE_POROSITY),
                      gis(ObservationKind.CALIBRATED_LOW_SW), gas()),
    )
    assert "tight_vs_storage_evidence_conflict" in output.reason_codes
    assert not output.shortlist_for_geologist
