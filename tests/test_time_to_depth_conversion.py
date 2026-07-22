from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
)
from geoworkbench.services.time_to_depth_conversion import (
    DepthAggregationMethod,
    TimeToDepthPlan,
    convert_time_dataset_to_depth,
)


def make_time_dataset() -> Dataset:
    dataset = Dataset(
        "source",
        "Time log",
        DatasetKind.USER,
        DepthDomain.TIME,
        np.array([0.0, 1.0, 2.0, 3.0]),
        indexes={
            "time": DatasetIndex(
                "time",
                "TIME",
                IndexType.RELATIVE_TIME,
                IndexRole.TIME,
                "s",
                np.array([0.0, 1.0, 2.0, 3.0]),
            ),
            "depth": DatasetIndex(
                "depth",
                "DEPTH",
                IndexType.MD,
                IndexRole.DEPTH,
                "m",
                np.array([100.0, 100.1, 100.1, 100.2]),
            ),
        },
        active_index_id="time",
    )
    dataset.curves["gas"] = CurveData(
        CurveMetadata("gas", "GAS", "GAS", "%", "Gas", dataset.dataset_id),
        np.array([1.0, 2.0, 4.0, 8.0]),
    )
    return dataset


def test_time_to_depth_mean_aggregates_duplicate_depth_rows() -> None:
    source = make_time_dataset()
    plan = TimeToDepthPlan(
        source.dataset_id,
        "depth",
        "time",
        100.0,
        100.2,
        0.1,
        DepthAggregationMethod.MEAN,
    )

    result = convert_time_dataset_to_depth(source, plan)

    assert result.dataset.active_index.role is IndexRole.DEPTH
    np.testing.assert_allclose(result.dataset.depth, [100.0, 100.1, 100.2])
    np.testing.assert_allclose(result.dataset.curve_by_mnemonic("GAS").values, [1.0, 3.0, 8.0])
    assert result.rows_per_bin == (1, 2, 1)
    assert result.empty_bin_count == 0
    assert source.curve_by_mnemonic("GAS").values.tolist() == [1.0, 2.0, 4.0, 8.0]


def test_time_to_depth_does_not_interpolate_empty_bins_unless_selected() -> None:
    source = make_time_dataset()
    source.indexes["depth"].values[:] = [100.0, 100.0, 100.2, 100.2]
    mean = convert_time_dataset_to_depth(
        source,
        TimeToDepthPlan(source.dataset_id, "depth", "time", 100.0, 100.2, 0.1),
    )
    linear = convert_time_dataset_to_depth(
        source,
        TimeToDepthPlan(
            source.dataset_id,
            "depth",
            "time",
            100.0,
            100.2,
            0.1,
            DepthAggregationMethod.LINEAR,
        ),
    )

    assert np.isnan(mean.dataset.curve_by_mnemonic("GAS").values[1])
    assert np.isfinite(linear.dataset.curve_by_mnemonic("GAS").values[1])
    assert mean.empty_bin_count == 1


def test_time_to_depth_plan_rejects_unsafe_or_invalid_ranges() -> None:
    with pytest.raises(ValueError, match="положительным"):
        TimeToDepthPlan("source", "depth", None, 100.0, 101.0, 0.0)
    with pytest.raises(ValueError, match="меньше"):
        TimeToDepthPlan("source", "depth", None, 101.0, 100.0, 0.1)
