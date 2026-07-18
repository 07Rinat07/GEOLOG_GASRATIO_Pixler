from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable, Literal

import numpy as np

from geoworkbench.domain.models import InterpretationInterval


class IntervalEditMode(StrEnum):
    SELECT = "select"
    CREATE = "create"
    RESIZE = "resize"


IntervalEdge = Literal["top", "bottom"]


@dataclass(frozen=True, slots=True)
class IntervalDragResult:
    top_depth: float
    bottom_depth: float

    @property
    def span(self) -> float:
        return self.bottom_depth - self.top_depth


def snap_depth_to_samples(depth: float, samples: Iterable[float]) -> float:
    values = np.asarray(tuple(samples), dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0 or not np.isfinite(depth):
        return float(depth)
    index = int(np.argmin(np.abs(values - float(depth))))
    return float(values[index])


def normalize_drag_range(
    start_depth: float,
    current_depth: float,
    *,
    minimum_span: float = 0.0,
) -> IntervalDragResult | None:
    top, bottom = sorted((float(start_depth), float(current_depth)))
    if not np.isfinite(top) or not np.isfinite(bottom):
        return None
    if bottom - top <= max(0.0, float(minimum_span)):
        return None
    return IntervalDragResult(top, bottom)


def choose_resize_edge(
    interval: InterpretationInterval,
    depth: float,
    *,
    tolerance: float,
) -> IntervalEdge | None:
    value = float(depth)
    allowed = max(0.0, float(tolerance))
    top_distance = abs(value - interval.top_depth)
    bottom_distance = abs(value - interval.bottom_depth)
    nearest = min(top_distance, bottom_distance)
    if nearest > allowed:
        return None
    return "top" if top_distance <= bottom_distance else "bottom"


def resize_interval_range(
    interval: InterpretationInterval,
    edge: IntervalEdge,
    depth: float,
    *,
    minimum_span: float,
) -> IntervalDragResult | None:
    if edge == "top":
        top, bottom = float(depth), interval.bottom_depth
    else:
        top, bottom = interval.top_depth, float(depth)
    if top >= bottom or bottom - top <= max(0.0, float(minimum_span)):
        return None
    return IntervalDragResult(top, bottom)
