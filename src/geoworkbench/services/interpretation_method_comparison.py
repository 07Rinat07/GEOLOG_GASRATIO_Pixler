"""Conservative, source-backed comparison of standard mud-gas and OPUS reports.

This is a structured QC companion; it never replaces either interpretation,
modifies OPUS classes/palettes, or asserts geological productivity/water.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from math import isfinite

from geoworkbench.services.fluid_phase_contract import (
    FluidPhaseContract,
    fluid_phase_from_hypothesis,
)
from geoworkbench.services.hydrocarbon_interpretation_legacy import (
    HydrocarbonCandidateInterval,
    HydrocarbonInterpretationReport,
    OpusGasomerIntervalReport,
)
from geoworkbench.services.opus_interpretation import (
    _gasomer_ambiguous_hypothesis,
)


class MethodComparisonStatus(StrEnum):
    AGREEMENT = "agreement"
    DISAGREEMENT = "disagreement"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True, slots=True)
class MethodComparisonInterval:
    """Auditable method comparison; support is not a fluid probability."""

    standard_bounds: tuple[float, float] | None
    opus_bounds: tuple[float, float] | None
    status: MethodComparisonStatus
    reason_code: str
    overlap_depth: float
    standard_overlap_fraction: float | None
    opus_overlap_fraction: float | None
    standard_phase: FluidPhaseContract | None
    opus_phase: FluidPhaseContract | None
    standard_wetness_robust_z: float | None
    standard_pixler_c1_c2: float | None
    opus_class_code: int | None
    opus_support_fraction: float | None
    opus_valid_rows: int | None


_OPUS_CLASS_PHASE: dict[int, FluidPhaseContract] = {
    1: FluidPhaseContract.LIQUID,  # residual/oxidized oil screening
    2: FluidPhaseContract.LIQUID,  # oil screening
    3: FluidPhaseContract.GAS,
    4: FluidPhaseContract.INDETERMINATE,  # water association is NOT proven
    5: FluidPhaseContract.LIQUID_OR_CONDENSATE,
    6: FluidPhaseContract.LIQUID,
    7: FluidPhaseContract.INDETERMINATE,
}


def _strict_phase(phase: FluidPhaseContract) -> str | None:
    if phase in (FluidPhaseContract.LIQUID, FluidPhaseContract.LIGHT_OIL):
        return "liquid"
    if phase is FluidPhaseContract.GAS:
        return "gas"
    return None


def _depth_overlap(first: tuple[float, float], second: tuple[float, float]) -> float:
    return max(0.0, min(first[1], second[1]) - max(first[0], second[0]))


def compare_standard_opus_reports(
    standard: HydrocarbonInterpretationReport,
    opus: HydrocarbonInterpretationReport,
) -> tuple[MethodComparisonInterval, ...]:
    """Compare one dataset and one actual depth *axis*, never just shared MD units.

    Strict agreement/disagreement is emitted only for sufficiently overlapping
    intervals with a determined standard Haworth/Pixler phase AND a determined
    OPUS Gasomer liquid/gas class. All missing, mixed or disputed evidence stays
    INSUFFICIENT, with a stable reason code and measured numeric context.
    """

    if standard.report_profile != "standard" or opus.report_profile != "opus":
        raise ValueError("Нужны отдельные отчёты standard и opus")
    if standard.dataset_id != opus.dataset_id:
        raise ValueError("Нельзя сравнивать отчёты разных наборов данных")
    if (
        not standard.depth_axis_id
        or not opus.depth_axis_id
        or standard.depth_axis_id != opus.depth_axis_id
        or standard.depth_unit != opus.depth_unit
    ):
        raise ValueError("Нельзя сравнивать отчёты без совпадающей оси глубины")
    section = opus.opus_gasomer
    intervals = section.intervals if section is not None else ()
    result: list[MethodComparisonInterval] = []
    for candidate in standard.candidates:
        standard_bounds = (candidate.top_depth, candidate.bottom_depth)
        matched = [
            interval
            for interval in intervals
            if _depth_overlap(
                standard_bounds, (interval.top_depth, interval.bottom_depth)
            ) > 0.0
        ]
        if len(matched) == 1:
            compared = _compare_interval(candidate, matched[0])
            # One OPUS show covering multiple standard peaks does not imply
            # independent one-to-one agreement for either standard interval.
            opus_bounds = (matched[0].top_depth, matched[0].bottom_depth)
            competing = sum(
                _depth_overlap((other.top_depth, other.bottom_depth), opus_bounds) > 0.0
                for other in standard.candidates
            )
            if competing > 1:
                compared = replace(
                    compared,
                    status=MethodComparisonStatus.INSUFFICIENT,
                    reason_code="multiple_standard_depth_overlaps",
                )
            result.append(compared)
        else:
            phase = fluid_phase_from_hypothesis(candidate.fluid_hypothesis)
            result.append(MethodComparisonInterval(
                standard_bounds=standard_bounds,
                opus_bounds=None,
                status=MethodComparisonStatus.INSUFFICIENT,
                reason_code=(
                    "no_opus_depth_overlap" if not matched
                    else "multiple_opus_depth_overlaps"
                ),
                overlap_depth=0.0,
                standard_overlap_fraction=None,
                opus_overlap_fraction=None,
                standard_phase=phase,
                opus_phase=None,
                standard_wetness_robust_z=candidate.wetness_robust_z,
                standard_pixler_c1_c2=(
                    candidate.pixler_assessment.c1_c2
                    if candidate.pixler_assessment is not None else None
                ),
                opus_class_code=None,
                opus_support_fraction=None,
                opus_valid_rows=None,
            ))
    for interval in intervals:
        bounds = (interval.top_depth, interval.bottom_depth)
        if any(
            _depth_overlap((candidate.top_depth, candidate.bottom_depth), bounds) > 0.0
            for candidate in standard.candidates
        ):
            continue
        result.append(MethodComparisonInterval(
            standard_bounds=None,
            opus_bounds=bounds,
            status=MethodComparisonStatus.INSUFFICIENT,
            reason_code="no_standard_depth_overlap",
            overlap_depth=0.0,
            standard_overlap_fraction=None,
            opus_overlap_fraction=None,
            standard_phase=None,
            opus_phase=_OPUS_CLASS_PHASE.get(interval.class_code),
            standard_wetness_robust_z=None,
            standard_pixler_c1_c2=None,
            opus_class_code=interval.class_code,
            opus_support_fraction=interval.support_fraction,
            opus_valid_rows=interval.valid_rows,
        ))
    return tuple(result)


def _compare_interval(
    standard: HydrocarbonCandidateInterval,
    opus: OpusGasomerIntervalReport,
) -> MethodComparisonInterval:
    first = (standard.top_depth, standard.bottom_depth)
    second = (opus.top_depth, opus.bottom_depth)
    overlap = _depth_overlap(first, second)
    first_span = first[1] - first[0]
    second_span = second[1] - second[0]
    first_fraction = overlap / first_span if first_span > 0 else 0.0
    second_fraction = overlap / second_span if second_span > 0 else 0.0
    standard_phase = fluid_phase_from_hypothesis(standard.fluid_hypothesis)
    opus_phase = _OPUS_CLASS_PHASE.get(opus.class_code, FluidPhaseContract.INDETERMINATE)
    standard_group = _strict_phase(standard_phase)
    opus_group = _strict_phase(opus_phase)

    if first_fraction < 0.5 or second_fraction < 0.5:
        status, reason = MethodComparisonStatus.INSUFFICIENT, "partial_depth_overlap"
    elif opus.valid_rows <= 0 or opus.class_code == 7:
        status, reason = MethodComparisonStatus.INSUFFICIENT, "opus_no_valid_consensus"
    elif len(opus.indicators) != 5:
        status, reason = MethodComparisonStatus.INSUFFICIENT, "opus_indicator_evidence_missing"
    elif _gasomer_ambiguous_hypothesis(opus) is not None:
        status, reason = MethodComparisonStatus.INSUFFICIENT, "opus_mixed_indicator_families"
    elif opus.class_code == 4:
        status, reason = MethodComparisonStatus.INSUFFICIENT, "opus_class_four_unverified"
    elif not isfinite(opus.support_fraction) or opus.support_fraction <= 0.0:
        status, reason = MethodComparisonStatus.INSUFFICIENT, "opus_support_unavailable"
    elif standard.pixler_assessment is None or (
        standard.wetness_robust_z is None
        or not isfinite(standard.wetness_robust_z)
    ):
        status, reason = MethodComparisonStatus.INSUFFICIENT, "standard_context_unavailable"
    elif standard_group is None or opus_group is None:
        status, reason = MethodComparisonStatus.INSUFFICIENT, "fluid_phase_ambiguous"
    elif standard_group == opus_group:
        status, reason = MethodComparisonStatus.AGREEMENT, "bounded_phase_agreement"
    else:
        status, reason = MethodComparisonStatus.DISAGREEMENT, "bounded_phase_disagreement"

    return MethodComparisonInterval(
        standard_bounds=first,
        opus_bounds=second,
        status=status,
        reason_code=reason,
        overlap_depth=overlap,
        standard_overlap_fraction=first_fraction,
        opus_overlap_fraction=second_fraction,
        standard_phase=standard_phase,
        opus_phase=opus_phase,
        standard_wetness_robust_z=standard.wetness_robust_z,
        standard_pixler_c1_c2=(
            standard.pixler_assessment.c1_c2
            if standard.pixler_assessment is not None else None
        ),
        opus_class_code=opus.class_code,
        opus_support_fraction=opus.support_fraction,
        opus_valid_rows=opus.valid_rows,
    )


__all__ = [
    "MethodComparisonInterval",
    "MethodComparisonStatus",
    "compare_standard_opus_reports",
]
