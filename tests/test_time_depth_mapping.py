import numpy as np
import pytest

from geoworkbench.domain.models import (
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
    TimeDepthAggregationPolicy,
)
from geoworkbench.services.time_depth_mapping import (
    TimeDepthMappingError,
    resolve_time_to_depth,
)


def make_dataset() -> Dataset:
    depth = np.array([100.0, 110.0, 120.0])
    dataset = Dataset("dataset", "Log", DatasetKind.GTI, DepthDomain.MD, depth)
    dataset.add_index(
        DatasetIndex(
            "time",
            "TIME",
            IndexType.DATETIME,
            IndexRole.TIME,
            "UTC",
            np.array(
                ["2026-07-15T05:00:00", "2026-07-15T05:00:10", "2026-07-15T05:00:20"],
                dtype="datetime64[ns]",
            ),
            timezone="UTC",
        )
    )
    return dataset


def test_time_depth_mapping_resolves_nearest_datetime_row() -> None:
    match = resolve_time_to_depth(make_dataset(), "2026-07-15T10:00:11+05:00")

    assert match.time_index_id == "time"
    assert match.depth == 110.0
    assert match.row == 1
    assert match.distance == 1_000_000_000.0
    assert match.policy is TimeDepthAggregationPolicy.ERROR
    assert match.matched_rows == (1,)


def test_time_depth_mapping_supports_relative_time() -> None:
    dataset = make_dataset()
    dataset.indexes["time"] = DatasetIndex(
        "time", "TIME", IndexType.RELATIVE_TIME, IndexRole.TIME, "s", np.array([0.0, 5.0, 10.0])
    )

    assert resolve_time_to_depth(dataset, "6").depth == 110.0


def test_time_depth_mapping_rejects_ambiguous_or_missing_index_selection() -> None:
    dataset = make_dataset()
    dataset.indexes["time-2"] = DatasetIndex(
        "time-2",
        "TIME2",
        IndexType.RELATIVE_TIME,
        IndexRole.TIME,
        "s",
        np.array([0.0, 1.0, 2.0]),
    )
    with pytest.raises(TimeDepthMappingError, match="ровно один"):
        resolve_time_to_depth(dataset, "1")

    del dataset.indexes["time-2"]
    dataset.indexes["time"].values = np.array(
        ["2026-07-15T05:00:00", "2026-07-15T05:00:10", "2026-07-15T05:00:10"],
        dtype="datetime64[ns]",
    )
    dataset.depth[2] = 130.0
    dataset.indexes[dataset.active_index_id].values[2] = 130.0
    with pytest.raises(TimeDepthMappingError, match="неоднозначно"):
        resolve_time_to_depth(dataset, "2026-07-15T05:00:10Z")


def test_time_depth_mapping_rejects_timezone_awareness_mismatch() -> None:
    dataset = make_dataset()

    with pytest.raises(TimeDepthMappingError, match="Часовой пояс"):
        resolve_time_to_depth(dataset, "2026-07-15T05:00:10")


@pytest.mark.parametrize(
    ("policy", "expected_depth", "expected_row"),
    [
        (TimeDepthAggregationPolicy.FIRST, 110.0, 1),
        (TimeDepthAggregationPolicy.LAST, 130.0, 2),
        (TimeDepthAggregationPolicy.MIN, 110.0, 1),
        (TimeDepthAggregationPolicy.MAX, 130.0, 2),
        (TimeDepthAggregationPolicy.MEAN, 120.0, None),
    ],
)
def test_time_depth_mapping_applies_explicit_repeated_pass_policy(
    policy: TimeDepthAggregationPolicy,
    expected_depth: float,
    expected_row: int | None,
) -> None:
    dataset = make_dataset()
    dataset.indexes["time"].values = np.array(
        ["2026-07-15T05:00:00", "2026-07-15T05:00:10", "2026-07-15T05:00:10"],
        dtype="datetime64[ns]",
    )
    dataset.depth[2] = 130.0
    dataset.indexes[dataset.active_index_id].values[2] = 130.0

    match = resolve_time_to_depth(
        dataset,
        "2026-07-15T05:00:10Z",
        policy=policy,
    )

    assert match.depth == expected_depth
    assert match.row == expected_row
    assert match.policy is policy
    assert match.matched_rows == (1, 2)


def test_time_depth_mapping_rejects_untyped_policy() -> None:
    with pytest.raises(TimeDepthMappingError, match="Неизвестная политика"):
        resolve_time_to_depth(make_dataset(), "2026-07-15T05:00:10Z", policy="first")  # type: ignore[arg-type]
