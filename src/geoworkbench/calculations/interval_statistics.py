from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

from geoworkbench.domain.models import Dataset


@dataclass(frozen=True, slots=True)
class CurveIntervalStatistics:
    mnemonic: str
    unit: str | None
    valid_count: int
    minimum: float
    maximum: float
    mean: float


def calculate_interval_statistics(
    dataset: Dataset,
    depth_top: float,
    depth_bottom: float,
    mnemonics: Iterable[str] | None = None,
) -> tuple[CurveIntervalStatistics, ...]:
    if not np.isfinite(depth_top) or not np.isfinite(depth_bottom):
        raise ValueError("Границы интервала должны быть конечными")
    if depth_top >= depth_bottom:
        raise ValueError("Верхняя граница интервала должна быть меньше нижней")

    depth = np.asarray(dataset.depth, dtype=np.float64)
    interval_mask = np.isfinite(depth) & (depth >= depth_top) & (depth <= depth_bottom)
    if not np.any(interval_mask):
        raise ValueError("В выбранном глубинном интервале нет отсчётов")

    requested = {name.casefold() for name in mnemonics} if mnemonics is not None else None
    statistics: list[CurveIntervalStatistics] = []
    for curve in dataset.curves.values():
        mnemonic = curve.metadata.original_mnemonic
        names = {mnemonic.casefold(), (curve.metadata.canonical_mnemonic or "").casefold()}
        if requested is not None and requested.isdisjoint(names):
            continue
        values = np.asarray(curve.values, dtype=np.float64)
        if values.shape != depth.shape:
            continue
        selected = values[interval_mask]
        finite = selected[np.isfinite(selected)]
        if finite.size == 0:
            continue
        statistics.append(
            CurveIntervalStatistics(
                mnemonic=mnemonic,
                unit=curve.metadata.unit,
                valid_count=int(finite.size),
                minimum=float(np.min(finite)),
                maximum=float(np.max(finite)),
                mean=float(np.mean(finite)),
            )
        )
    return tuple(statistics)
