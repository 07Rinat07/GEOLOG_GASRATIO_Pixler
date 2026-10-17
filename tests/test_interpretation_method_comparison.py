"""Evidence-bounded comparisons never reinterpret OPUS votes or fabricate phase QC."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from geoworkbench.services.fluid_phase_contract import FluidPhaseContract
from geoworkbench.services.hydrocarbon_interpretation_legacy import (
    HydrocarbonCandidateInterval,
    HydrocarbonInterpretationReport,
    OpusGasomerIndicatorReport,
    OpusGasomerIntervalReport,
    OpusGasomerReportSection,
)
from geoworkbench.services.interpretation_method_comparison import (
    MethodComparisonStatus,
    compare_standard_opus_reports,
)


def _candidate(
    top: float = 100.0, bottom: float = 104.0,
    *, phase: str = "probable_gas", with_pixler: bool = True,
) -> HydrocarbonCandidateInterval:
    return HydrocarbonCandidateInterval(
        top, bottom, 4, "high", "TG", 6.5, 0.2,
        phase, 15.0, 6.0, 3.2, 9.0, 0.7,
        SimpleNamespace(c1_c2=17.0) if with_pixler else None,
        (), "insufficient", (), (),
    )


def _interval(
    top: float = 100.0, bottom: float = 104.0,
    *, code: int = 3, valid_rows: int = 8,
    votes: tuple[int, ...] | None = None,
) -> OpusGasomerIntervalReport:
    actual_votes = (code,) * 5 if votes is None else votes
    indicators = tuple(
        OpusGasomerIndicatorReport(
            f"OPUS_GM_{number}", "formula", 1.0, vote, f"Class {vote}",
            0.625, valid_rows, 10, ((vote, valid_rows),),
            (("available", valid_rows),),
        )
        for number, vote in enumerate(actual_votes, start=1)
    )
    return OpusGasomerIntervalReport(
        top, bottom, code, f"Class {code}", 0.625, valid_rows, 10,
        0.02, 0.2, 0.18, 6.0, 9.0, indicators, (),
    )


def _section(*intervals: OpusGasomerIntervalReport) -> OpusGasomerReportSection:
    return OpusGasomerReportSection(
        "opus-gasomer", "1", "workbook", "synchronous-rows", "local",
        "%vol", 0.001, (), (), (), (), "sha256-placeholder", (), (),
        intervals, (),
    )


def _reports(
    standard_candidates: tuple[HydrocarbonCandidateInterval, ...] = (_candidate(),),
    opus_intervals: tuple[OpusGasomerIntervalReport, ...] = (_interval(),),
) -> tuple[HydrocarbonInterpretationReport, HydrocarbonInterpretationReport]:
    standard = HydrocarbonInterpretationReport(
        "Project", "Well", "dataset-1", "Log", "2026-10-17", "m",
        4.0, "TG", 0.02, 0.005, (), standard_candidates, (), (),
        depth_axis_id="dataset-1:primary-index",
    )
    opus = replace(
        standard, report_profile="opus", candidates=(),
        opus_gasomer=_section(*opus_intervals),
    )
    return standard, opus


@pytest.mark.parametrize(
    ("standard_code", "opus_code", "expected_status", "expected_reason", "expected_phase"),
    [
        ("probable_gas", 3, MethodComparisonStatus.AGREEMENT, "bounded_phase_agreement", FluidPhaseContract.GAS),
        ("probable_gas", 2, MethodComparisonStatus.DISAGREEMENT, "bounded_phase_disagreement", FluidPhaseContract.LIQUID),
        ("heavy_or_residual_oil", 1, MethodComparisonStatus.AGREEMENT, "bounded_phase_agreement", FluidPhaseContract.LIQUID),
        ("heavy_or_residual_oil", 3, MethodComparisonStatus.DISAGREEMENT, "bounded_phase_disagreement", FluidPhaseContract.GAS),
        ("probable_gas", 4, MethodComparisonStatus.INSUFFICIENT, "opus_class_four_unverified", FluidPhaseContract.INDETERMINATE),
        ("probable_gas", 7, MethodComparisonStatus.INSUFFICIENT, "opus_no_valid_consensus", FluidPhaseContract.INDETERMINATE),
        ("probable_gas", 5, MethodComparisonStatus.INSUFFICIENT, "fluid_phase_ambiguous", FluidPhaseContract.LIQUID_OR_CONDENSATE),
        ("opus_gas_condensate_or_gassy_oil", 2, MethodComparisonStatus.INSUFFICIENT, "fluid_phase_ambiguous", FluidPhaseContract.LIQUID),
    ],
)
def test_bounded_status_and_reason_follow_both_independent_profiles(
    standard_code: str, opus_code: int, expected_status: MethodComparisonStatus,
    expected_reason: str, expected_phase: FluidPhaseContract,
) -> None:
    standard, opus = _reports((_candidate(phase=standard_code),), (_interval(code=opus_code),))
    before_standard, before_opus = standard, opus
    comparisons = compare_standard_opus_reports(standard, opus)

    assert len(comparisons) == 1
    item = comparisons[0]
    assert item.status is expected_status
    assert item.reason_code == expected_reason
    assert item.standard_bounds == (100.0, 104.0)
    assert item.opus_bounds == (100.0, 104.0)
    assert item.overlap_depth == 4.0
    assert item.standard_overlap_fraction == item.opus_overlap_fraction == 1.0
    assert item.standard_wetness_robust_z == 3.2
    assert item.standard_pixler_c1_c2 == 17.0
    assert item.opus_class_code == opus_code
    assert item.opus_phase is expected_phase
    assert item.opus_support_fraction == 0.625
    assert item.opus_valid_rows == 8
    assert standard == before_standard and opus == before_opus


@pytest.mark.parametrize(
    ("standard", "opus", "reason"),
    [
        ((_candidate(100.0, 104.0),), (), "no_opus_depth_overlap"),
        ((), (_interval(100.0, 104.0),), "no_standard_depth_overlap"),
        ((_candidate(100.0, 104.0),), (_interval(103.0, 110.0),), "partial_depth_overlap"),
        ((_candidate(100.0, 104.0),), (_interval(100.0, 102.0), _interval(102.0, 104.0)), "multiple_opus_depth_overlaps"),
        ((_candidate(with_pixler=False),), (_interval(),), "standard_context_unavailable"),
    ],
)
def test_insufficient_overlap_and_missing_inputs_preserve_specific_reason(
    standard: tuple[HydrocarbonCandidateInterval, ...],
    opus: tuple[OpusGasomerIntervalReport, ...],
    reason: str,
) -> None:
    reports = _reports(standard, opus)
    comparisons = compare_standard_opus_reports(*reports)
    assert len(comparisons) == 1
    assert comparisons[0].status is MethodComparisonStatus.INSUFFICIENT
    assert comparisons[0].reason_code == reason


@pytest.mark.parametrize("change", [
    {"dataset_id": "different-dataset"},
    {"depth_axis_id": "dataset-1:lag-corrected"},
    {"depth_axis_id": None},
    {"depth_unit": "ft"},
])
def test_never_compare_different_depth_axes_or_datasets(change: dict[str, str | None]) -> None:
    standard, opus = _reports()
    with pytest.raises(ValueError, match="Нельзя сравнивать"):
        compare_standard_opus_reports(standard, replace(opus, **change))


def test_missing_opus_valid_rows_precludes_agreement() -> None:
    standard, opus = _reports(opus_intervals=(_interval(code=2, valid_rows=0),))
    item, = compare_standard_opus_reports(standard, opus)
    assert item.status is MethodComparisonStatus.INSUFFICIENT
    assert item.reason_code == "opus_no_valid_consensus"


def test_conflicting_opus_five_vote_families_cannot_claim_agreement() -> None:
    standard, opus = _reports(
        (_candidate(phase="heavy_or_residual_oil"),),
        (_interval(code=2, votes=(1, 2, 2, 3, 3)),),
    )
    result, = compare_standard_opus_reports(standard, opus)
    assert result.status is MethodComparisonStatus.INSUFFICIENT
    assert result.reason_code == "opus_mixed_indicator_families"
    assert result.opus_class_code == 2


def test_missing_five_formula_evidence_cannot_claim_agreement() -> None:
    standard, opus = _reports()
    section = opus.opus_gasomer
    assert section is not None
    opus = replace(
        opus, opus_gasomer=replace(section, intervals=(
            replace(section.intervals[0], indicators=()),),
        ),
    )
    result, = compare_standard_opus_reports(standard, opus)
    assert result.status is MethodComparisonStatus.INSUFFICIENT
    assert result.reason_code == "opus_indicator_evidence_missing"


def test_many_to_one_depth_overlap_is_not_method_agreement() -> None:
    standard, opus = _reports(
        (_candidate(100.0, 102.0), _candidate(102.0, 104.0)),
        (_interval(100.0, 104.0),),
    )
    result = compare_standard_opus_reports(standard, opus)
    assert len(result) == 2
    assert all(item.status is MethodComparisonStatus.INSUFFICIENT for item in result)
    assert all(item.reason_code == "multiple_standard_depth_overlaps" for item in result)
