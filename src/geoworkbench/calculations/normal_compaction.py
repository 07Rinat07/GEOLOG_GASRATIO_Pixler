from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


Array = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class NormalCompactionConfig:
    calibration_top: float
    calibration_bottom: float
    minimum_points: int = 3
    require_positive_slope: bool = True

    def __post_init__(self) -> None:
        if not np.isfinite(self.calibration_top) or not np.isfinite(self.calibration_bottom):
            raise ValueError("Границы калибровки NCT должны быть конечными")
        if self.calibration_top >= self.calibration_bottom:
            raise ValueError("Верхняя граница калибровки NCT должна быть меньше нижней")
        if self.minimum_points < 2:
            raise ValueError("Для калибровки NCT требуется минимум две точки")


@dataclass(frozen=True, slots=True)
class NormalCompactionResult:
    trend: Array
    deviation: Array
    calibration_mask: NDArray[np.bool_]
    slope: float
    intercept: float
    calibration_points: int
    rmse: float


def calculate_normal_compaction_trend(
    depth: Array,
    corrected_d_exponent: Array,
    config: NormalCompactionConfig,
    *,
    eligible_mask: NDArray[np.bool_] | None = None,
) -> NormalCompactionResult:
    """Fit a linear NCT only to explicitly selected, eligible calibration points."""

    depth_values = np.asarray(depth, dtype=np.float64)
    dc_values = np.asarray(corrected_d_exponent, dtype=np.float64)
    if depth_values.shape != dc_values.shape:
        raise ValueError("Глубина и DEXPC должны иметь одинаковую форму")
    if depth_values.ndim != 1:
        raise ValueError("Для NCT ожидаются одномерные кривые")

    mask = (
        np.isfinite(depth_values)
        & np.isfinite(dc_values)
        & (depth_values >= config.calibration_top)
        & (depth_values <= config.calibration_bottom)
    )
    if eligible_mask is not None:
        eligibility = np.asarray(eligible_mask, dtype=np.bool_)
        if eligibility.shape != depth_values.shape:
            raise ValueError("Маска пригодных интервалов должна совпадать с глубиной")
        mask &= eligibility

    point_count = int(np.count_nonzero(mask))
    if point_count < config.minimum_points:
        raise ValueError(
            f"Недостаточно точек для NCT: {point_count}, требуется {config.minimum_points}"
        )
    calibration_depth = depth_values[mask]
    if np.unique(calibration_depth).size < 2:
        raise ValueError("Для NCT нужны как минимум две различные глубины")

    slope, intercept = np.polyfit(calibration_depth, dc_values[mask], deg=1)
    if not np.isfinite(slope) or not np.isfinite(intercept):
        raise ValueError("Не удалось построить конечный тренд NCT")
    if config.require_positive_slope and slope <= 0.0:
        raise ValueError("NCT должен возрастать с глубиной на интервале калибровки")

    trend = np.full(depth_values.shape, np.nan, dtype=np.float64)
    valid_depth = np.isfinite(depth_values)
    trend[valid_depth] = slope * depth_values[valid_depth] + intercept
    deviation = np.full(depth_values.shape, np.nan, dtype=np.float64)
    valid_deviation = valid_depth & np.isfinite(dc_values)
    deviation[valid_deviation] = dc_values[valid_deviation] - trend[valid_deviation]
    residuals = dc_values[mask] - trend[mask]
    rmse = float(np.sqrt(np.mean(np.square(residuals))))

    return NormalCompactionResult(
        trend=trend,
        deviation=deviation,
        calibration_mask=mask,
        slope=float(slope),
        intercept=float(intercept),
        calibration_points=point_count,
        rmse=rmse,
    )
