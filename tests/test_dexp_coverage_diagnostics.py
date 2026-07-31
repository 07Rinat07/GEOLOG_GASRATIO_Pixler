from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
)
from geoworkbench.project.interpretation_calculation_diagnostics import (
    diagnose_dexp_coverage,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.drilling_mode import DrillingModeCode


def _add_curve(dataset: Dataset, mnemonic: str, values: np.ndarray, unit: str) -> None:
    dataset.curves[mnemonic] = CurveData(
        CurveMetadata(
            curve_id=mnemonic,
            original_mnemonic=mnemonic,
            canonical_mnemonic=mnemonic,
            unit=unit,
            description=mnemonic,
            source_dataset_id=dataset.dataset_id,
        ),
        np.asarray(values, dtype=np.float64),
    )


def _controller_with_dexp_inputs(
    *,
    include_bit_rpm: bool = False,
) -> InterpretationCalculationController:
    depth = np.arange(1_000.0, 1_012.0)
    dataset = Dataset(
        "dexp-diagnostic",
        "DEXP diagnostic",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    rop = np.full(depth.shape, 60.0)
    rop[2:4] = 0.0
    rop[8] = np.nan
    rpm = np.full(depth.shape, 100.0)
    rpm[5] = 0.0
    _add_curve(dataset, "ROP", rop, "ft/h")
    _add_curve(dataset, "RPM", rpm, "rpm")
    _add_curve(dataset, "WOB", np.full(depth.shape, 50_000.0), "lbf")
    _add_curve(dataset, "BIT", np.full(depth.shape, 10.0), "in")
    _add_curve(dataset, "FLOW", np.full(depth.shape, 500.0), "gpm")
    if include_bit_rpm:
        bit_rpm = np.full(depth.shape, np.nan)
        bit_rpm[5] = 150.0
        _add_curve(dataset, "MOTOR_RPM", bit_rpm, "rpm")
    session = ProjectSession()
    session.add_dataset(dataset, "Well DEXP")
    return InterpretationCalculationController(session)


def _rotary_controller_with_formula_gap() -> InterpretationCalculationController:
    depth = np.arange(1_000.0, 1_008.0)
    dataset = Dataset(
        "dexp-repair",
        "DEXP repair",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    wob = np.full(depth.shape, 50_000.0)
    wob[3] = 1_000_000.0 * 10.0 / 12.0
    _add_curve(dataset, "ROP", np.full(depth.shape, 60.0), "ft/h")
    _add_curve(dataset, "RPM", np.full(depth.shape, 100.0), "rpm")
    _add_curve(dataset, "WOB", wob, "lbf")
    _add_curve(dataset, "BIT", np.full(depth.shape, 10.0), "in")
    _add_curve(dataset, "FLOW", np.full(depth.shape, 500.0), "gpm")
    session = ProjectSession()
    session.add_dataset(dataset, "Well repair")
    return InterpretationCalculationController(session)


def test_dexp_calculation_repairs_short_gap_only_inside_rotary_mode() -> None:
    controller = _rotary_controller_with_formula_gap()
    controller.calculate_standard_curves()

    diagnostic = diagnose_dexp_coverage(controller)
    dataset = controller.session.current_dataset
    assert dataset is not None
    curve = dataset.curve_by_mnemonic("DEXP")
    assert curve is not None

    assert diagnostic.curve_source == "calculation"
    assert diagnostic.coverage_percent == 100.0
    assert diagnostic.rotary_points == 8
    assert diagnostic.slide_points == 0
    assert "gap_repair=linear-short-internal-same-mode" in curve.metadata.provenance
    assert np.all(np.isfinite(curve.values))


def test_dexp_calculation_preserves_slide_gap_without_bit_rpm() -> None:
    controller = _controller_with_dexp_inputs()
    result = controller.calculate_standard_curves()

    diagnostic = diagnose_dexp_coverage(controller)
    dataset = controller.session.current_dataset
    assert dataset is not None
    dexp = dataset.curve_by_mnemonic("DEXP")
    mode = dataset.curve_by_mnemonic("DRILL_MODE")
    effective_rpm = dataset.curve_by_mnemonic("BIT_RPM_EFFECTIVE")
    assert dexp is not None
    assert mode is not None
    assert effective_rpm is not None

    assert diagnostic.total_points == 12
    assert diagnostic.valid_points == 8
    assert diagnostic.missing_points == 4
    assert diagnostic.slide_points == 1
    assert diagnostic.slide_points_without_bit_rpm == 1
    assert diagnostic.bit_rpm_mnemonic is None
    assert np.isnan(dexp.values[5])
    assert mode.values[5] == DrillingModeCode.SLIDE
    assert np.isnan(effective_rpm.values[5])
    assert any(issue.code == "dexp-slide-bit-rpm-missing" for issue in result.issues)
    assert "rpm=mode-aware" in dexp.metadata.provenance


def test_dexp_calculation_uses_real_bit_rpm_during_slide() -> None:
    controller = _controller_with_dexp_inputs(include_bit_rpm=True)
    controller.calculate_standard_curves()

    diagnostic = diagnose_dexp_coverage(controller)
    dataset = controller.session.current_dataset
    assert dataset is not None
    dexp = dataset.curve_by_mnemonic("DEXP")
    effective_rpm = dataset.curve_by_mnemonic("BIT_RPM_EFFECTIVE")
    assert dexp is not None
    assert effective_rpm is not None

    expected = np.log10(60.0 / (60.0 * 150.0)) / np.log10(
        12.0 * 50_000.0 / (1_000_000.0 * 10.0)
    )
    assert np.isclose(dexp.values[5], expected)
    assert effective_rpm.values[5] == 150.0
    assert diagnostic.valid_points == 9
    assert diagnostic.slide_points == 1
    assert diagnostic.slide_points_with_bit_rpm == 1
    assert diagnostic.slide_points_without_bit_rpm == 0
    assert diagnostic.bit_rpm_mnemonic == "MOTOR_RPM"


def test_dexp_diagnostic_reports_modes_before_curve_creation() -> None:
    controller = _controller_with_dexp_inputs()

    diagnostic = diagnose_dexp_coverage(controller)

    assert diagnostic.curve_mnemonic is None
    assert diagnostic.curve_source == "potential"
    assert diagnostic.valid_points == 8
    assert diagnostic.missing_points == 4
    counts = dict(diagnostic.reason_counts)
    assert counts["rop_nonpositive"] == 2
    assert counts["not_drilling"] == 2
    assert counts["rop_missing"] == 1
    assert counts["drilling_mode_unknown"] == 1
    assert counts["slide_bit_rpm_missing"] == 1
    assert "rpm_nonpositive" not in counts
    assert [(gap.top, gap.bottom, gap.point_count) for gap in diagnostic.gap_intervals] == [
        (1_002.0, 1_003.0, 2),
        (1_005.0, 1_005.0, 1),
        (1_008.0, 1_008.0, 1),
    ]
