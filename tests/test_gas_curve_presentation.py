from __future__ import annotations

import numpy as np

from geoworkbench.services.gas_curve_presentation import (
    gas_scatter_sample_indices,
)


def test_dense_gas_scatter_enforces_vertical_display_gap() -> None:
    depth = np.linspace(0.0, 100.0, 2_001, dtype=np.float64)
    values = np.full(depth.shape, 2.5, dtype=np.float64)

    selected = gas_scatter_sample_indices(
        depth,
        values,
        top=0.0,
        bottom=100.0,
        vertical_span=300.0,
        minimum_gap=3.0,
    )

    assert 90 <= selected.size <= 101
    projected = depth[selected] / 100.0 * 300.0
    assert np.all(np.diff(projected) >= 3.0 - 1e-9)


def test_sparse_gas_scatter_keeps_separated_factual_observations() -> None:
    depth = np.arange(0.0, 101.0, 1.0, dtype=np.float64)
    values = np.full(depth.shape, np.nan, dtype=np.float64)
    values[[10, 50, 90]] = [1.2, 2.4, 3.6]

    selected = gas_scatter_sample_indices(
        depth,
        values,
        top=0.0,
        bottom=100.0,
        vertical_span=300.0,
        minimum_gap=3.0,
    )

    np.testing.assert_array_equal(selected, np.asarray([10, 50, 90]))


def test_gas_scatter_sampling_is_presentation_only_and_does_not_mutate_values() -> None:
    depth = np.linspace(0.0, 10.0, 101, dtype=np.float64)
    values = np.linspace(1.0, 5.0, 101, dtype=np.float64)
    original_depth = depth.copy()
    original_values = values.copy()

    selected = gas_scatter_sample_indices(
        depth,
        values,
        top=0.0,
        bottom=10.0,
        vertical_span=100.0,
        minimum_gap=4.0,
    )

    assert selected.size < depth.size
    np.testing.assert_array_equal(depth, original_depth)
    np.testing.assert_array_equal(values, original_values)
