from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.services.gas_curve_presentation import (
    GAS_PREVIEW_POINTS_PER_PX,
    gas_scatter_point_budget,
    is_gas_point_mnemonic,
    select_gas_scatter_indices,
)


@pytest.mark.parametrize(
    "mnemonic",
    (
        "C1/C2",
        "C1_C2",
        "PIXLER_C1_C5",
        "HAWORTH_WETNESS",
        "OPUS_RATIO_GM_1",
        "CUSTOM_RATIO_SCORE",
    ),
)
def test_ratio_identifiers_use_point_presentation(mnemonic: str) -> None:
    assert is_gas_point_mnemonic(mnemonic)


@pytest.mark.parametrize("mnemonic", ("C1", "TG_CALC", "ROP", "C1_REL"))
def test_non_ratio_identifiers_do_not_use_point_presentation(mnemonic: str) -> None:
    assert not is_gas_point_mnemonic(mnemonic)


def test_scatter_budget_tracks_final_display_height() -> None:
    assert gas_scatter_point_budget(
        180.0,
        density=GAS_PREVIEW_POINTS_PER_PX,
        minimum=16,
        maximum=720,
    ) == 72
    assert gas_scatter_point_budget(
        10_000.0,
        density=GAS_PREVIEW_POINTS_PER_PX,
        minimum=16,
        maximum=720,
    ) == 720


def test_dense_scatter_sampling_is_bounded_and_preserves_value_spread() -> None:
    depth = np.arange(3_600, dtype=np.float64)
    values = np.sin(depth / 25.0) * 5.0 + depth / 3_600.0

    indices = select_gas_scatter_indices(depth, values, max_points=120)

    assert 1 < indices.size <= 120
    assert np.all(np.diff(depth[indices]) >= 0.0)
    assert float(np.min(values[indices])) <= float(np.min(values)) + 0.05
    assert float(np.max(values[indices])) >= float(np.max(values)) - 0.05


def test_sparse_scatter_sampling_never_drops_single_observation() -> None:
    depth = np.arange(5_000, dtype=np.float64)
    values = np.full(depth.shape, np.nan, dtype=np.float64)
    values[2_731] = 3.25

    indices = select_gas_scatter_indices(depth, values, max_points=32)

    np.testing.assert_array_equal(indices, np.asarray([2_731], dtype=np.int64))
