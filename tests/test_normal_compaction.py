import numpy as np
import pytest

from geoworkbench.calculations.normal_compaction import (
    NormalCompactionConfig,
    calculate_normal_compaction_trend,
)


def test_normal_compaction_trend_uses_explicit_calibration_interval() -> None:
    depth = np.array([1000.0, 1100.0, 1200.0, 1300.0, 1400.0])
    dc = np.array([1.0, 1.1, 1.2, 0.9, 1.4])

    result = calculate_normal_compaction_trend(
        depth,
        dc,
        NormalCompactionConfig(1000.0, 1200.0),
    )

    np.testing.assert_allclose(result.trend, [1.0, 1.1, 1.2, 1.3, 1.4])
    np.testing.assert_allclose(result.deviation, [0.0, 0.0, 0.0, -0.4, 0.0], atol=1e-12)
    np.testing.assert_array_equal(result.calibration_mask, [True, True, True, False, False])
    assert result.calibration_points == 3
    assert result.slope == pytest.approx(0.001)
    assert result.rmse == pytest.approx(0.0, abs=1e-12)


def test_normal_compaction_trend_respects_eligible_mask() -> None:
    result = calculate_normal_compaction_trend(
        np.array([1000.0, 1100.0, 1200.0, 1300.0]),
        np.array([1.0, 99.0, 1.2, 1.3]),
        NormalCompactionConfig(1000.0, 1300.0, minimum_points=3),
        eligible_mask=np.array([True, False, True, True]),
    )

    np.testing.assert_allclose(result.trend, [1.0, 1.1, 1.2, 1.3])
    assert result.calibration_points == 3


def test_normal_compaction_trend_rejects_insufficient_or_declining_calibration() -> None:
    depth = np.array([1000.0, 1100.0, 1200.0])

    with pytest.raises(ValueError, match="Недостаточно точек"):
        calculate_normal_compaction_trend(
            depth,
            np.array([1.0, np.nan, 1.2]),
            NormalCompactionConfig(1000.0, 1200.0),
        )

    with pytest.raises(ValueError, match="возрастать"):
        calculate_normal_compaction_trend(
            depth,
            np.array([1.2, 1.1, 1.0]),
            NormalCompactionConfig(1000.0, 1200.0),
        )


@pytest.mark.parametrize(
    "top,bottom",
    [(1000.0, 1000.0), (1200.0, 1000.0), (np.nan, 1200.0)],
)
def test_normal_compaction_config_rejects_invalid_interval(top: float, bottom: float) -> None:
    with pytest.raises(ValueError):
        NormalCompactionConfig(top, bottom)
