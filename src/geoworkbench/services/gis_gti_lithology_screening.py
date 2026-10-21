"""Explainable interval screening of verified GIS, mud-gas and geology evidence.

INTERP-FUSION-01 data-only boundary. Inputs are *validated interpretations*,
not raw LAS curves. No hidden lithology cutoffs, Archie coefficients,
resampling, fluid percentages, reservoir probabilities or pay designation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite


class RockFamily(StrEnum):
    CLASTIC = "clastic"
    CARBONATE = "carbonate"
    ARGILLACEOUS = "argillaceous"
    HALITE = "halite"
    SULFATE = "sulfate"
    VOLCANIC = "volcanic"
    COAL_OR_ORGANIC = "coal_or_organic"
    UNKNOWN_OR_MIXED = "unknown_or_mixed"


class EvidenceOrigin(StrEnum):
    GIS = "gis"
    MUD_GAS = "mud_gas"
    GEOLOGY = "geology"
    FORMATION_TEST = "formation_test"


class ObservationKind(StrEnum):
    EFFECTIVE_POROSITY = "effective_porosity"
    FRACTURES = "fractures"
    NMR_MOBILITY = "nmr_mobility"
    TIGHT_MATRIX = "tight_matrix"
    CALIBRATED_LOW_SW = "calibrated_low_sw"
    CALIBRATED_HIGH_SW = "calibrated_high_sw"
    GAS_EFFECT = "gas_effect"
    GAS_SHOW = "gas_show"
    LBA_SHOW = "lba_show"
    TEST_GAS = "test_gas"
    TEST_OIL = "test_oil"
    TEST_WATER = "test_water"


class ObservationQuality(StrEnum):
    VALIDATED = "validated"
    SUSPECT = "suspect"
    REJECTED = "rejected"


class ReservoirAssessment(StrEnum):
    DYNAMIC_SUPPORT = "dynamic_support"
    LOG_SUPPORTED = "log_supported"
    CANDIDATE = "candidate"
    TIGHT_INDICATION = "tight_indication"
    ATYPICAL_UNVERIFIED = "atypical_unverified"
    UNKNOWN = "unknown"


class FluidAssessment(StrEnum):
    TEST_GAS = "gas_confirmed_by_test"
    TEST_OIL = "oil_confirmed_by_test"
    TEST_WATER = "water_confirmed_by_test"
    TEST_CONFLICT = "different_test_fluids_review"
    GAS_CANDIDATE = "gas_candidate_from_gis_and_gti"
    HC_CANDIDATE = "hydrocarbon_candidate_from_gis_and_gti"
    WATER_CANDIDATE = "water_candidate_from_gis"
    UNDETERMINED = "undetermined"


_GIS_KINDS = frozenset({
    ObservationKind.EFFECTIVE_POROSITY, ObservationKind.FRACTURES,
    ObservationKind.NMR_MOBILITY, ObservationKind.TIGHT_MATRIX,
    ObservationKind.CALIBRATED_LOW_SW, ObservationKind.CALIBRATED_HIGH_SW,
    ObservationKind.GAS_EFFECT,
})
_ORIGIN_BY_KIND = {
    **{kind: EvidenceOrigin.GIS for kind in _GIS_KINDS},
    ObservationKind.GAS_SHOW: EvidenceOrigin.MUD_GAS,
    ObservationKind.LBA_SHOW: EvidenceOrigin.GEOLOGY,
    ObservationKind.TEST_GAS: EvidenceOrigin.FORMATION_TEST,
    ObservationKind.TEST_OIL: EvidenceOrigin.FORMATION_TEST,
    ObservationKind.TEST_WATER: EvidenceOrigin.FORMATION_TEST,
}
_TEST_KINDS = frozenset({
    ObservationKind.TEST_GAS, ObservationKind.TEST_OIL,
    ObservationKind.TEST_WATER,
})
_ATYPICAL_MATRIX = frozenset({
    RockFamily.ARGILLACEOUS, RockFamily.HALITE, RockFamily.SULFATE,
    RockFamily.VOLCANIC, RockFamily.COAL_OR_ORGANIC,
})


@dataclass(frozen=True, slots=True)
class IntervalObservation:
    kind: ObservationKind
    origin: EvidenceOrigin
    source_id: str
    depth_axis_id: str
    top_md_m: float
    bottom_md_m: float
    quality: ObservationQuality
    method_or_calibration_id: str = ""


@dataclass(frozen=True, slots=True)
class GisGtiIntervalReview:
    """Per-interval review; not a quantitative saturation or production claim."""

    top_md_m: float
    bottom_md_m: float
    depth_axis_id: str
    rock_family: RockFamily
    reservoir: ReservoirAssessment
    fluid: FluidAssessment
    shortlist_for_geologist: bool
    accepted_evidence_ids: tuple[str, ...]
    disregarded_evidence_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    method_id: str = "interp-fusion-lithology-qc-1"


def review_gis_gti_interval(
    *,
    top_md_m: float,
    bottom_md_m: float,
    depth_axis_id: str,
    rock_family: RockFamily,
    observations: tuple[IntervalObservation, ...],
) -> GisGtiIntervalReview:
    """Review overlapping validated intervals on the exact same verified MD axis.

    A prior GIS semantic resolver must approve each curve's UOM, tool, source,
    caliper QC, lag and petrophysical model. One source ID may supply multiple
    measurements; this function does not double-count or assign probabilities.
    """
    _validate_bounds(top_md_m, bottom_md_m)
    if not isinstance(depth_axis_id, str) or not depth_axis_id.strip():
        raise ValueError("A verified nonempty MD depth-axis ID is required")
    if not isinstance(rock_family, RockFamily):
        raise TypeError("rock_family must be RockFamily")
    if not isinstance(observations, tuple):
        raise TypeError("observations must be an immutable tuple")

    accepted: list[IntervalObservation] = []
    discarded_ids: list[str] = []
    reasons: list[str] = []
    for observed in observations:
        if not isinstance(observed, IntervalObservation):
            raise TypeError("All observations must be IntervalObservation")
        _validate_observation(observed, depth_axis_id)
        if observed.bottom_md_m <= top_md_m or observed.top_md_m >= bottom_md_m:
            continue
        if observed.quality is not ObservationQuality.VALIDATED:
            discarded_ids.append(observed.source_id)
            reasons.append("suspect_or_rejected_source_not_used")
            continue
        accepted.append(observed)

    kinds = {item.kind for item in accepted}
    tests = kinds & _TEST_KINDS
    if len(tests) > 1:
        fluid = FluidAssessment.TEST_CONFLICT
        reasons.append("multiple_test_fluids_require_interval_review")
    elif ObservationKind.TEST_GAS in tests:
        fluid = FluidAssessment.TEST_GAS
    elif ObservationKind.TEST_OIL in tests:
        fluid = FluidAssessment.TEST_OIL
    elif ObservationKind.TEST_WATER in tests:
        fluid = FluidAssessment.TEST_WATER
    elif (
        ObservationKind.GAS_EFFECT in kinds
        and ObservationKind.GAS_SHOW in kinds
        and ObservationKind.EFFECTIVE_POROSITY in kinds
    ):
        fluid = FluidAssessment.GAS_CANDIDATE
        reasons.append("gas_effect_not_direct_phase_test")
    elif (
        ObservationKind.CALIBRATED_LOW_SW in kinds
        and ObservationKind.EFFECTIVE_POROSITY in kinds
        and (
            ObservationKind.GAS_SHOW in kinds
            or ObservationKind.LBA_SHOW in kinds
        )
    ):
        fluid = FluidAssessment.HC_CANDIDATE
        reasons.append("low_sw_not_oil_versus_gas_discriminator")
    elif (
        ObservationKind.CALIBRATED_HIGH_SW in kinds
        and ObservationKind.EFFECTIVE_POROSITY in kinds
    ):
        fluid = FluidAssessment.WATER_CANDIDATE
        reasons.append("high_sw_not_formation_test")
    else:
        fluid = FluidAssessment.UNDETERMINED

    if tests & {ObservationKind.TEST_GAS, ObservationKind.TEST_OIL}:
        reservoir = ReservoirAssessment.DYNAMIC_SUPPORT
    elif (
        ObservationKind.EFFECTIVE_POROSITY in kinds
        and ObservationKind.NMR_MOBILITY in kinds
    ):
        reservoir = ReservoirAssessment.LOG_SUPPORTED
    elif (
        ObservationKind.EFFECTIVE_POROSITY in kinds
        or ObservationKind.FRACTURES in kinds
    ):
        reservoir = ReservoirAssessment.CANDIDATE
    elif ObservationKind.TIGHT_MATRIX in kinds:
        reservoir = ReservoirAssessment.TIGHT_INDICATION
    elif rock_family in _ATYPICAL_MATRIX:
        reservoir = ReservoirAssessment.ATYPICAL_UNVERIFIED
    else:
        reservoir = ReservoirAssessment.UNKNOWN

    if rock_family in _ATYPICAL_MATRIX:
        reasons.append("atypical_rock_requires_secondary_storage_or_test")
    if (
        ObservationKind.TIGHT_MATRIX in kinds
        and (
            ObservationKind.EFFECTIVE_POROSITY in kinds
            or ObservationKind.FRACTURES in kinds
            or ObservationKind.NMR_MOBILITY in kinds
        )
    ):
        reasons.append("tight_vs_storage_evidence_conflict")
    if (
        ObservationKind.CALIBRATED_LOW_SW in kinds
        and ObservationKind.CALIBRATED_HIGH_SW in kinds
    ):
        reasons.append("competing_water_saturation_interpretations")
    if (
        ObservationKind.TEST_WATER in tests
        and (
            ObservationKind.GAS_SHOW in kinds
            or ObservationKind.LBA_SHOW in kinds
            or ObservationKind.CALIBRATED_LOW_SW in kinds
        )
    ):
        reasons.append("water_test_vs_hydrocarbon_indicators")
    if (
        (ObservationKind.GAS_SHOW in kinds or ObservationKind.LBA_SHOW in kinds)
        and reservoir in {
            ReservoirAssessment.TIGHT_INDICATION,
            ReservoirAssessment.ATYPICAL_UNVERIFIED,
        }
    ):
        reasons.append("hydrocarbon_show_without_verified_reservoir")
    if not kinds:
        reasons.append("no_validated_evidence")

    shortlist = (
        fluid in {
            FluidAssessment.TEST_GAS,
            FluidAssessment.TEST_OIL,
            FluidAssessment.GAS_CANDIDATE,
            FluidAssessment.HC_CANDIDATE,
        }
        and reservoir in {
            ReservoirAssessment.DYNAMIC_SUPPORT,
            ReservoirAssessment.LOG_SUPPORTED,
            ReservoirAssessment.CANDIDATE,
        }
        and "competing_water_saturation_interpretations" not in reasons
        and "tight_vs_storage_evidence_conflict" not in reasons
    )
    if shortlist:
        reasons.append("prospect_review_not_commercial_pay")
    # An independent dynamic water test cannot be negated by a gas show.
    if ObservationKind.TEST_WATER in tests and len(tests) == 1:
        shortlist = False

    return GisGtiIntervalReview(
        float(top_md_m), float(bottom_md_m), depth_axis_id, rock_family,
        reservoir, fluid, shortlist,
        tuple(dict.fromkeys(item.source_id for item in accepted)),
        tuple(dict.fromkeys(discarded_ids)),
        tuple(dict.fromkeys(reasons)),
    )


def _validate_bounds(top: float, bottom: float) -> None:
    for value in (top, bottom):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("MD bounds must be finite numbers in metres")
        if not isfinite(value):
            raise ValueError("MD bounds must be finite numbers in metres")
    if top < 0 or bottom <= top:
        raise ValueError("MD bounds require 0 <= top < bottom")


def _validate_observation(item: IntervalObservation, expected_axis: str) -> None:
    if not isinstance(item.kind, ObservationKind):
        raise TypeError("Observation kind must be explicit")
    if item.origin is not _ORIGIN_BY_KIND[item.kind]:
        raise ValueError("Observation origin is inconsistent with kind")
    if not isinstance(item.quality, ObservationQuality):
        raise TypeError("Observation quality must be explicit")
    if not isinstance(item.source_id, str) or not item.source_id.strip():
        raise ValueError("Every observation requires a source ID")
    if item.depth_axis_id != expected_axis:
        raise ValueError("Cannot correlate observations from different MD axes")
    _validate_bounds(item.top_md_m, item.bottom_md_m)
    if item.origin is EvidenceOrigin.GIS and (
        not isinstance(item.method_or_calibration_id, str)
        or not item.method_or_calibration_id.strip()
    ):
        raise ValueError("GIS interpretation requires a method/calibration ID")


__all__ = [
    "EvidenceOrigin", "FluidAssessment", "GisGtiIntervalReview",
    "IntervalObservation", "ObservationKind", "ObservationQuality",
    "ReservoirAssessment", "RockFamily", "review_gis_gti_interval",
]
