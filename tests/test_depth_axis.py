import numpy as np
import pytest

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.services.depth_axis import (
    DepthDirection,
    analyze_depth_axis,
    build_depth_grid,
    create_ascending_depth_copy,
)


@pytest.mark.parametrize("step", [0.1, 0.2, 0.5, 1.0])
def test_build_depth_grid_accepts_arbitrary_positive_step(step: float) -> None:
    grid = build_depth_grid(100.0, 102.0, step)

    assert grid[0] == pytest.approx(100.0)
    assert np.allclose(np.diff(grid), step)
    assert grid[-1] <= 102.0 + 1e-9


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

    result = create_ascending_depth_copy(source)

    np.testing.assert_allclose(result.depth, [100.0, 101.0, 102.0])
    np.testing.assert_allclose(result.curve_by_mnemonic("GR").values, [10.0, 20.0, 30.0])
    np.testing.assert_allclose(source.depth, [102.0, 101.0, 100.0])
    np.testing.assert_allclose(source.curve_by_mnemonic("GR").values, [30.0, 20.0, 10.0])
    assert result.kind is DatasetKind.DERIVED
    assert result.headers == {"STRT": "100", "STOP": "102", "STEP": "1"}
