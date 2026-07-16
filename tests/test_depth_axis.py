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
from geoworkbench.services.depth_axis import (
    DepthDirection,
    analyze_depth_axis,
    analyze_depth_resample,
    build_depth_grid,
    create_ascending_depth_copy,
    create_resampled_depth_copy,
)


@pytest.mark.parametrize("step", [0.1, 0.2, 0.5, 1.0])
def test_build_depth_grid_accepts_arbitrary_positive_step(step: float) -> None:
    grid = build_depth_grid(100.0, 102.0, step)

    assert grid[0] == pytest.approx(100.0)
    assert np.allclose(np.diff(grid), step)
    assert grid[-1] <= 102.0 + 1e-9


def test_build_depth_grid_rejects_unsafe_sample_count() -> None:
    with pytest.raises(ValueError, match="безопасный предел"):
        build_depth_grid(0.0, 10_000.0, 0.001)


def test_depth_analysis_detects_descending_duplicates_gaps_and_missing() -> None:
    report = analyze_depth_axis(
        np.array([105.0, 104.5, 104.5, np.nan, 103.0, 102.5], dtype=np.float64)
    )

    assert report.direction is DepthDirection.DESCENDING
    assert report.nominal_step == pytest.approx(0.5)
    assert report.duplicate_count == 1
    assert report.missing_count == 1
    assert report.gap_count == 1
    assert report.is_uniform is False


def test_ascending_copy_reverses_every_curve_and_preserves_source() -> None:
    source = Dataset(
        "source",
        "GIS",
        DatasetKind.GIS,
        DepthDomain.MD,
        np.array([102.0, 101.0, 100.0]),
        headers={"STRT": "102", "STOP": "100", "STEP": "-1"},
    )
    source.curves["gr"] = CurveData(
        CurveMetadata("gr", "GR", "GR", "API", "Gamma", source.dataset_id),
        np.array([30.0, 20.0, 10.0]),
    )
    source.add_index(
        DatasetIndex(
            "time",
            "TIME",
            IndexType.RELATIVE_TIME,
            IndexRole.TIME,
            "s",
            np.array([0.0, 1.0, 2.0]),
        )
    )

    result = create_ascending_depth_copy(source)

    np.testing.assert_allclose(result.depth, [100.0, 101.0, 102.0])
    np.testing.assert_allclose(result.curve_by_mnemonic("GR").values, [10.0, 20.0, 30.0])
    np.testing.assert_allclose(source.depth, [102.0, 101.0, 100.0])
    np.testing.assert_allclose(source.curve_by_mnemonic("GR").values, [30.0, 20.0, 10.0])
    assert result.kind is DatasetKind.DERIVED
    assert result.headers == {"STRT": "100", "STOP": "102", "STEP": "1"}
    result_time = next(index for index in result.indexes.values() if index.role is IndexRole.TIME)
    np.testing.assert_allclose(result_time.values, [2.0, 1.0, 0.0])


def test_resampled_copy_uses_depth_spacing_and_does_not_bridge_missing_values() -> None:
    source = Dataset(
        "source",
        "LAS",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0, 103.0, 104.0]),
        headers={"STRT": "100", "STOP": "104", "STEP": ""},
    )
    source.curves["gr"] = CurveData(
        CurveMetadata("gr", "GR", "GR", "API", None, source.dataset_id),
        np.array([10.0, 20.0, np.nan, 50.0]),
    )
    source.add_index(
        DatasetIndex(
            "time",
            "TIME",
            IndexType.RELATIVE_TIME,
            IndexRole.TIME,
            "s",
            np.array([0.0, 10.0, 30.0, 40.0]),
        )
    )

    plan = analyze_depth_resample(source, 100.0, 104.0, 0.5)
    result = create_resampled_depth_copy(source, plan)

    assert plan.source_sample_count == 4
    assert plan.target_sample_count == 9
    np.testing.assert_allclose(result.depth, np.arange(100.0, 104.5, 0.5))
    expected = [10.0, 15.0, 20.0, np.nan, np.nan, np.nan, np.nan, np.nan, 50.0]
    np.testing.assert_allclose(result.curve_by_mnemonic("GR").values, expected, equal_nan=True)
    result_time = next(index for index in result.indexes.values() if index.role is IndexRole.TIME)
    np.testing.assert_allclose(result_time.values, np.arange(0.0, 45.0, 5.0))
    np.testing.assert_allclose(source.depth, [100.0, 101.0, 103.0, 104.0])
    assert result.headers == {"STRT": "100", "STOP": "104", "STEP": "0.5"}


def test_resample_rejects_descending_or_extrapolated_grid() -> None:
    descending = Dataset(
        "source", "LAS", DatasetKind.GTI, DepthDomain.MD, np.array([2.0, 1.0, 0.0])
    )
    with pytest.raises(ValueError, match="возрастающего индекса"):
        analyze_depth_resample(descending, 0.0, 2.0, 0.5)

    ascending = Dataset(
        "source", "LAS", DatasetKind.GTI, DepthDomain.MD, np.array([0.0, 1.0, 2.0])
    )
    with pytest.raises(ValueError, match="внутри исходного диапазона"):
        analyze_depth_resample(ascending, 0.0, 3.0, 0.5)
