from __future__ import annotations

import numpy as np

from geoworkbench.calculations.gas_conditioning import (
    GasConditioningPolicy,
    GasConditioningQcInterval,
    condition_gas_components,
)


def test_qc_summary_reports_component_and_affected_row_counts() -> None:
    depth = np.arange(0.0, 11.0)
    c1 = np.full(depth.shape, np.nan)
    c2 = np.full(depth.shape, np.nan)
    c1[[0, 3, 10]] = (10.0, 13.0, 20.0)
    c2[[0, 2, 10]] = (5.0, 7.0, 9.0)

    result = condition_gas_components(
        depth,
        {"C2": c2, "C1": c1},
        policy=GasConditioningPolicy(max_gap_steps=2.0, cadence_factor=2.0),
    )

    summary = result.qc_summary
    assert [component.mnemonic for component in summary.components] == ["C1", "C2"]
    assert summary.affected_depth_row_count == 2
    assert summary.interpolated_component_sample_count == 3
    assert summary.nominal_depth_step == 1.0

    c1_qc = summary.component("c1")
    assert c1_qc.interpolated_sample_count == 2
    assert c1_qc.interpolated_intervals == (
        GasConditioningQcInterval(minimum_depth=1.0, maximum_depth=2.0, sample_count=2),
    )
    assert result.interpolated_count("C1") == c1_qc.interpolated_sample_count

    c2_qc = summary.component(" C2 ")
    assert c2_qc.interpolated_sample_count == 1
    assert c2_qc.interpolated_intervals == (
        GasConditioningQcInterval(minimum_depth=1.0, maximum_depth=1.0, sample_count=1),
    )


def test_qc_intervals_normalize_depth_bounds_for_descending_axis() -> None:
    depth = np.array([5.0, 4.0, 3.0, 2.0, 1.0, 0.0])
    values = np.array([20.0, np.nan, np.nan, 14.0, np.nan, 10.0])

    result = condition_gas_components(
        depth,
        {"C1": values},
        policy=GasConditioningPolicy(max_gap_steps=2.0, cadence_factor=2.0),
    )

    qc = result.qc_summary.component("C1")
    assert qc.interpolated_sample_count == 3
    assert qc.interpolated_intervals == (
        GasConditioningQcInterval(minimum_depth=3.0, maximum_depth=4.0, sample_count=2),
        GasConditioningQcInterval(minimum_depth=1.0, maximum_depth=1.0, sample_count=1),
    )


def test_qc_summary_preserves_empty_provenance_when_nothing_is_restored() -> None:
    depth = np.arange(0.0, 5.0)
    values = np.arange(10.0, 15.0)

    result = condition_gas_components(depth, {"C1": values})

    summary = result.qc_summary
    assert summary.affected_depth_row_count == 0
    assert summary.interpolated_component_sample_count == 0
    component = summary.component("C1")
    assert component.interpolated_sample_count == 0
    assert component.interpolated_intervals == ()
