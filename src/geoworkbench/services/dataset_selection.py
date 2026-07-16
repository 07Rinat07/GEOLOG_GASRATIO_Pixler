from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from PySide6.QtCore import QObject, Signal

from geoworkbench.domain.models import Dataset


class DatasetIntervalSelection(QObject):
    changed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._dataset_id: str | None = None
        self._depth_top: float | None = None
        self._depth_bottom: float | None = None
        self._curve_ids: tuple[str, ...] = ()

    @property
    def dataset_id(self) -> str | None:
        return self._dataset_id

    @property
    def interval(self) -> tuple[float, float] | None:
        if self._depth_top is None or self._depth_bottom is None:
            return None
        return self._depth_top, self._depth_bottom

    @property
    def curve_ids(self) -> tuple[str, ...]:
        return self._curve_ids

    def select(
        self,
        dataset: Dataset,
        depth_top: float,
        depth_bottom: float,
        curve_ids: tuple[str, ...] = (),
    ) -> None:
        indices = depth_interval_indices(dataset, depth_top, depth_bottom)
        missing = [curve_id for curve_id in curve_ids if curve_id not in dataset.curves]
        if missing:
            raise KeyError(f"Кривые не найдены: {', '.join(missing)}")
        top = float(np.min(dataset.depth[indices]))
        bottom = float(np.max(dataset.depth[indices]))
        normalized_curves = tuple(dict.fromkeys(curve_ids))
        state = (dataset.dataset_id, top, bottom, normalized_curves)
        current = (
            self._dataset_id,
            self._depth_top,
            self._depth_bottom,
            self._curve_ids,
        )
        if state == current:
            return
        self._dataset_id, self._depth_top, self._depth_bottom, self._curve_ids = state
        self.changed.emit(self)

    def clear(self) -> None:
        if self._dataset_id is None:
            return
        self._dataset_id = None
        self._depth_top = None
        self._depth_bottom = None
        self._curve_ids = ()
        self.changed.emit(self)


def depth_interval_indices(
    dataset: Dataset, depth_top: float, depth_bottom: float
) -> NDArray[np.int64]:
    if not np.isfinite(depth_top) or not np.isfinite(depth_bottom):
        raise ValueError("Границы интервала должны быть конечными")
    if depth_top > depth_bottom:
        raise ValueError("Кровля интервала должна быть не глубже подошвы")
    depth = dataset.depth
    indices = np.flatnonzero(
        np.isfinite(depth) & (depth >= depth_top) & (depth <= depth_bottom)
    ).astype(np.int64)
    if indices.size == 0:
        raise ValueError("В выбранном глубинном интервале нет отсчётов")
    return indices
