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
    TimeDepthMappingProfile,
)
from geoworkbench.services.time_depth_aggregation import (
    analyze_time_depth_aggregation,
    create_time_depth_aggregated_copy,
)


def make_dataset(*, datetime: bool = False) -> Dataset:
    dataset = Dataset(
        "source", "Log", DatasetKind.GTI, DepthDomain.MD,
        np.array([100.0, 110.0, 120.0, 130.0, np.nan]),
    )
    time_values = (
        np.array(
            [
                "2026-01-01T00:00:00", "2026-01-01T00:00:04",
                "2026-01-01T00:00:10", "2026-01-01T00:00:14", "NaT",
            ],
            dtype="datetime64[ns]",
        )
        if datetime
        else np.array([0.0, 4000.0, 10000.0, 14000.0, np.nan])
    )
    dataset.add_index(
        DatasetIndex(
            "time", "TIME",
            IndexType.DATETIME if datetime else IndexType.RELATIVE_TIME,
            IndexRole.TIME, "s" if datetime else "ms", time_values,
            timezone="UTC" if datetime else None,
        )
    )
    dataset.upsert_curve("C1", np.array([1.0, 3.0, 5.0, np.nan, 99.0]), unit="%")
    return dataset


def profile(dataset: Dataset, policy: TimeDepthAggregationPolicy) -> TimeDepthMappingProfile:
    return TimeDepthMappingProfile(
        "profile", "Mapping", dataset.dataset_id, "time", dataset.active_index_id, policy
    )


@pytest.mark.parametrize(
    ("policy", "depths"),
    [
        (TimeDepthAggregationPolicy.FIRST, [100.0, 120.0]),
        (TimeDepthAggregationPolicy.LAST, [110.0, 130.0]),
        (TimeDepthAggregationPolicy.MIN, [100.0, 120.0]),
        (TimeDepthAggregationPolicy.MAX, [110.0, 130.0]),
        (TimeDepthAggregationPolicy.MEAN, [105.0, 125.0]),
    ],
)
def test_time_depth_aggregation_creates_derived_copy(
    policy: TimeDepthAggregationPolicy, depths: list[float]
) -> None:
    source = make_dataset()
    selected_profile = profile(source, policy)
    plan = analyze_time_depth_aggregation(source, selected_profile, 10.0)

    result = create_time_depth_aggregated_copy(source, selected_profile, plan)

    assert result.dataset.kind is DatasetKind.DERIVED
    np.testing.assert_allclose(result.dataset.depth, depths)
    np.testing.assert_allclose(result.dataset.indexes[next(
        key for key, value in result.dataset.indexes.items() if value.role is IndexRole.TIME
    )].values, [2000.0, 12000.0])
    np.testing.assert_allclose(result.dataset.curve_by_mnemonic("C1").values, [2.0, 5.0])
    assert result.rows_per_bin == (2, 2)
    assert plan.valid_row_count == 4
    assert plan.dropped_row_count == 1
    assert source.depth.shape == (5,)
    assert "transform:time-depth:source:profile:v1" in (
        result.dataset.curve_by_mnemonic("C1").metadata.provenance
    )


def test_time_depth_aggregation_preserves_datetime_index() -> None:
    source = make_dataset(datetime=True)
    selected_profile = profile(source, TimeDepthAggregationPolicy.MEAN)
    plan = analyze_time_depth_aggregation(source, selected_profile, 10.0)

    result = create_time_depth_aggregated_copy(source, selected_profile, plan)
    time_index = next(
        value for value in result.dataset.indexes.values() if value.role is IndexRole.TIME
    )

    assert time_index.index_type is IndexType.DATETIME
    assert time_index.timezone == "UTC"
    np.testing.assert_array_equal(
        time_index.values,
        np.array(["2026-01-01T00:00:02", "2026-01-01T00:00:12"], dtype="datetime64[ns]"),
    )


def test_time_depth_aggregation_error_policy_rejects_ambiguous_bin() -> None:
    source = make_dataset()
    with pytest.raises(ValueError, match="неоднозначно"):
        analyze_time_depth_aggregation(
            source, profile(source, TimeDepthAggregationPolicy.ERROR), 10.0
        )


def test_time_depth_aggregation_rejects_stale_plan_and_unknown_unit() -> None:
    source = make_dataset()
    selected_profile = profile(source, TimeDepthAggregationPolicy.FIRST)
    plan = analyze_time_depth_aggregation(source, selected_profile, 10.0)
    source.depth[0] = 101.0
    source.active_index.values[0] = 101.0
    with pytest.raises(ValueError, match="изменился"):
        create_time_depth_aggregated_copy(source, selected_profile, plan)

    source.indexes["time"].unit = "fortnight"
    with pytest.raises(ValueError, match="не поддерживается"):
        analyze_time_depth_aggregation(source, selected_profile, 10.0)


def test_time_depth_aggregation_rejects_plan_after_curve_change() -> None:
    source = make_dataset()
    selected_profile = profile(source, TimeDepthAggregationPolicy.FIRST)
    plan = analyze_time_depth_aggregation(source, selected_profile, 10.0)
    source.curve_by_mnemonic("C1").values[0] = 500.0

    with pytest.raises(ValueError, match="изменился"):
        create_time_depth_aggregated_copy(source, selected_profile, plan)
