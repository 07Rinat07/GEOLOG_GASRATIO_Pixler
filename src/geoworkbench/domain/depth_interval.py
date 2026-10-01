from __future__ import annotations

from dataclasses import dataclass, replace
import math

import numpy as np
from numpy.typing import NDArray

from geoworkbench.domain.models import Dataset, IndexRole


class DepthIntervalError(ValueError):
    """An analysis interval cannot be applied to the active depth axis."""


@dataclass(frozen=True, slots=True)
class DepthInterval:
    top_depth: float
    bottom_depth: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.top_depth) or not math.isfinite(self.bottom_depth):
            raise DepthIntervalError("Границы интервала должны быть конечными числами")
        if self.bottom_depth < self.top_depth:
            raise DepthIntervalError("Нижняя граница интервала меньше верхней")

    def formatted(self, unit: str = "") -> str:
        suffix = f" {unit.strip()}" if unit.strip() else ""
        return f"{self.top_depth:.2f}–{self.bottom_depth:.2f}{suffix}"

    def row_mask(self, dataset: Dataset) -> NDArray[np.bool_]:
        if dataset.active_index.role is not IndexRole.DEPTH:
            raise DepthIntervalError("Для интервала глубин выберите глубинную ось MD/TVD/TVDSS")
        depth = np.asarray(dataset.active_index.values, dtype=np.float64)
        finite = depth[np.isfinite(depth)]
        if finite.size == 0:
            raise DepthIntervalError("В наборе данных нет конечной оси глубины")
        if self.top_depth < float(finite.min()) or self.bottom_depth > float(finite.max()):
            raise DepthIntervalError("Выбранный интервал выходит за диапазон данных")
        mask = np.isfinite(depth) & (depth >= self.top_depth) & (depth <= self.bottom_depth)
        if self.bottom_depth <= self.top_depth or np.unique(depth[mask]).size < 2:
            raise DepthIntervalError("В выбранном интервале нужны как минимум две разные глубины")
        return mask


def scope_dataset(dataset: Dataset, interval: DepthInterval | None) -> Dataset:
    """Copy aligned selected rows; never mutate the original LAS or its indexes."""
    if interval is None:
        return dataset
    mask = interval.row_mask(dataset)
    if any(curve.values.shape != mask.shape for curve in dataset.curves.values()):
        raise DepthIntervalError("Размеры кривых не совпадают с осью глубины")
    return replace(
        dataset,
        depth=dataset.depth[mask].copy(),
        indexes={
            key: replace(index, values=index.values[mask].copy())
            for key, index in dataset.indexes.items()
        },
        curves={
            key: replace(curve, values=curve.values[mask].copy())
            for key, curve in dataset.curves.items()
        },
    )
