from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.calculations.gas_conditioning import (
    GasConditioningPolicy,
    condition_gas_components,
    interpolate_bounded_gaps,
)
from geoworkbench.calculations.gas_ratio import calculate_conditioned_ratios


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_gap_steps": 0.0}, "max_gap_steps"),
        ({"cadence_factor": float("nan")}, "cadence_factor"),
        ({"minimum_finite_samples": 1}, "minimum_finite_samples"),
        ({"absolute_max_gap": -1.0}, "absolute_max_gap"),
    ],
)
def test_conditioning_policy_rejects_unsafe_values(
    kwargs: dict[str, float | int], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        GasConditioningPolicy(**kwargs)


def test_short_bounded_gap_is_interpolated_but_long_outage_remains() -> None:
    depth = np.arange(0.0, 21.0)
    values = np.full(depth.shape, np.nan)
    values[[0, 3, 20]] = (10.0, 13.0, 30.0)

    result = condition_gas_components(
        depth,
        {"C1": values},
        policy=GasConditioningPolicy(max_gap_steps=2.0, cadence_factor=2.0),
    )

    np.testing.assert_allclose(result.components["C1"][:4], [10.0, 11.0, 12.0, 13.0])
    assert np.all(result.interpolated_masks["C1"][1:3])
    assert np.isnan(result.components["C1"][10])
    assert not result.interpolated_masks["C1"][10]
    assert result.interpolated_count("c1") == 2


def test_descending_depth_is_conditioned_without_reordering_output() -> None:
    depth = np.array([4.0, 3.0, 2.0, 1.0, 0.0])
    values = np.array([20.0, np.nan, 0.0, np.nan, 10.0])

    result = condition_gas_components(depth, {"C1": values})

    np.testing.assert_array_equal(result.depth, depth)
    np.testing.assert_allclose(result.components["C1"], [20.0, 10.0, 0.0, 5.0, 10.0])
    np.testing.assert_array_equal(
        result.interpolated_masks["C1"],
        [False, True, False, True, False],
    )


def test_explicit_zero_is_preserved_as_a_measured_boundary() -> None:
    depth = np.arange(0.0, 5.0)
    values = np.array([10.0, np.nan, 0.0, np.nan, 20.0])

    interpolated, mask = interpolate_bounded_gaps(depth, values, max_gap=3.0)

    assert interpolated[2] == 0.0
    assert not mask[2]
    assert interpolated[1] == 5.0
    assert interpolated[3] == 10.0


def test_conditioning_does_not_mutate_inputs_and_normalizes_mnemonics() -> None:
    depth = np.arange(0.0, 4.0)
    values = np.array([1.0, np.nan, 3.0, 4.0])
    original_depth = depth.copy()
    original_values = values.copy()

    result = condition_gas_components(depth, {" c1 ": values})

    np.testing.assert_array_equal(depth, original_depth)
    np.testing.assert_array_equal(values, original_values)
    assert set(result.components) == {"C1"}
    assert result.depth is not depth
    assert result.components["C1"] is not values


def test_conditioning_rejects_non_monotonic_depth_and_shape_mismatch() -> None:
    with pytest.raises(ValueError, match="строго монотонной"):
        condition_gas_components(
            np.array([0.0, 2.0, 1.0]),
            {"C1": np.array([1.0, 2.0, 3.0])},
        )

    with pytest.raises(ValueError, match="ожидалась 3"):
        condition_gas_components(
            np.array([0.0, 1.0, 2.0]),
            {"C1": np.array([1.0, 2.0])},
        )


def test_conditioning_rejects_case_insensitive_duplicate_mnemonics() -> None:
    depth = np.arange(0.0, 3.0)

    with pytest.raises(ValueError, match="Дублирующаяся мнемоника"):
        condition_gas_components(
            depth,
            {
                "C1": np.array([1.0, 2.0, 3.0]),
                "c1": np.array([1.0, 2.0, 3.0]),
            },
        )


def test_absolute_gap_cap_prevents_over_interpolation() -> None:
    depth = np.arange(0.0, 11.0)
    values = np.full(depth.shape, np.nan)
    values[[0, 5, 10]] = (10.0, 15.0, 20.0)

    result = condition_gas_components(
        depth,
        {"C1": values},
        policy=GasConditioningPolicy(
            max_gap_steps=10.0,
            cadence_factor=10.0,
            absolute_max_gap=2.0,
        ),
    )

    assert np.isnan(result.components["C1"][1])
    assert np.isnan(result.components["C1"][6])
    assert result.interpolated_count("C1") == 0
    assert result.max_gap_by_component["C1"] == 2.0


def test_conditioned_ratios_are_derived_after_source_component_alignment() -> None:
    depth = np.arange(0.0, 21.0)

    def sparse(first: float, second: float, last: float) -> np.ndarray:
        values = np.full(depth.shape, np.nan)
        values[[0, 3, 20]] = (first, second, last)
        return values

    result = calculate_conditioned_ratios(
        depth,
        {
            "C1": sparse(80.0, 70.0, 60.0),
            "C2": sparse(10.0, 10.0, 10.0),
            "C3": sparse(5.0, 5.0, 5.0),
            "IC4": sparse(1.0, 1.0, 1.0),
            "NC4": sparse(2.0, 2.0, 2.0),
            "IC5": sparse(1.0, 1.0, 1.0),
            "NC5": sparse(1.0, 1.0, 1.0),
        },
        policy=GasConditioningPolicy(max_gap_steps=2.0, cadence_factor=2.0),
    )

    assert np.isfinite(result.curves["TG_CALC"].values[1])
    assert np.isfinite(result.curves["PIXLER_C1_C2"].values[2])
    assert np.isnan(result.curves["TG_CALC"].values[10])
    assert np.isnan(result.curves["PIXLER_C1_C2"].values[10])

    relative_sum = sum(
        result.curves[f"{component}_REL"].values
        for component in ("C1", "C2", "C3", "IC4", "NC4", "IC5", "NC5")
    )
    np.testing.assert_allclose(relative_sum[1:3], [100.0, 100.0])
    assert np.isnan(relative_sum[10])
    assert result.conditioned_components.interpolated_count("C1") == 2


def test_infinite_source_values_are_treated_as_missing_without_mutation() -> None:
    depth = np.arange(0.0, 4.0)
    values = np.array([1.0, np.inf, 3.0, 4.0])

    result = condition_gas_components(depth, {"C1": values})

    assert np.isinf(values[1])
    assert result.components["C1"][1] == 2.0
    assert result.interpolated_masks["C1"][1]
