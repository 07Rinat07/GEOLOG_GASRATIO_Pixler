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


def _controller_with_dexp_inputs() -> InterpretationCalculationController:
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
    session = ProjectSession()
    session.add_dataset(dataset, "Well DEXP")
    return InterpretationCalculationController(session)


def test_dexp_diagnostic_counts_invalid_inputs_and_contiguous_gaps() -> None:
    controller = _controller_with_dexp_inputs()
    controller.calculate_standard_curves()

    diagnostic = diagnose_dexp_coverage(controller)

    assert diagnostic.curve_source == "calculation"
    assert diagnostic.total_points == 12
    assert diagnostic.valid_points == 8
    assert diagnostic.missing_points == 4
    assert diagnostic.coverage_percent == 100.0 * 8.0 / 12.0
    counts = dict(diagnostic.reason_counts)
    assert counts["rop_nonpositive"] == 2
    assert counts["rop_missing"] == 1
    assert counts["rpm_nonpositive"] == 1
    assert [(gap.top, gap.bottom, gap.point_count) for gap in diagnostic.gap_intervals] == [
        (1_002.0, 1_003.0, 2),
        (1_005.0, 1_005.0, 1),
        (1_008.0, 1_008.0, 1),
    ]


def test_dexp_diagnostic_reports_potential_coverage_before_curve_creation() -> None:
    controller = _controller_with_dexp_inputs()

    diagnostic = diagnose_dexp_coverage(controller)

    assert diagnostic.curve_mnemonic is None
    assert diagnostic.curve_source == "potential"
    assert diagnostic.valid_points == 8
    assert diagnostic.missing_points == 4
