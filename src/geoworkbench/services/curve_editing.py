from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class DrawPoint:
    depth: float
    value: float


def interpolate_drawn_curve(
    depth: NDArray[np.float64],
    points: list[DrawPoint],
) -> NDArray[np.float64]:
    if depth.ndim != 1:
        raise ValueError("Шкала глубины должна быть одномерной")
    if len(points) < 2:
        raise ValueError("Требуется минимум две точки")
    ordered = sorted(points, key=lambda point: point.depth)
    point_depth = np.asarray([point.depth for point in ordered], dtype=np.float64)
    point_values = np.asarray([point.value for point in ordered], dtype=np.float64)
    if not np.all(np.isfinite(point_depth)) or not np.all(np.isfinite(point_values)):
        raise ValueError("Точки редактирования должны содержать конечные числа")
    if np.any(np.diff(point_depth) <= 0):
        raise ValueError("Глубины точек должны быть уникальными")
    return np.interp(depth, point_depth, point_values)
