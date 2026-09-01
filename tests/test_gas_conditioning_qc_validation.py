from __future__ import annotations

import pytest

from geoworkbench.domain.gas_conditioning_qc import (
    GasComponentConditioningQc,
    GasConditioningQcInterval,
    GasConditioningQcSummary,
)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_qc_interval_rejects_non_finite_depth_bounds(value: float) -> None:
    with pytest.raises(ValueError, match="конечными"):
        GasConditioningQcInterval(value, 1001.0, 1)

    with pytest.raises(ValueError, match="конечными"):
        GasConditioningQcInterval(1000.0, value, 1)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_qc_summary_rejects_non_finite_nominal_depth_step(value: float) -> None:
    with pytest.raises(ValueError, match="конечным положительным"):
        GasConditioningQcSummary(value, 0, 0, ())


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_component_qc_rejects_non_finite_max_gap(value: float) -> None:
    with pytest.raises(ValueError, match="конечным положительным"):
        GasComponentConditioningQc("C1", 0, (), value)


def test_qc_contract_rejects_boolean_and_non_integer_counters() -> None:
    with pytest.raises(ValueError, match="sample_count"):
        GasConditioningQcInterval(1000.0, 1000.0, True)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="affected_depth_row_count"):
        GasConditioningQcSummary(0.5, 1.5, 0, ())  # type: ignore[arg-type]


def test_component_qc_requires_typed_intervals() -> None:
    with pytest.raises(ValueError, match="QC-интервалы"):
        GasComponentConditioningQc("C1", 1, (object(),), 1.0)  # type: ignore[arg-type]
