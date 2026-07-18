from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Hashable

import numpy as np
from numpy.typing import NDArray

from geoworkbench.tablet.sampling import select_visible_samples


@dataclass(frozen=True, slots=True)
class CurveGeometryKey:
    """Identity of one sampled curve geometry for a vertical viewport."""

    curve_id: Hashable
    axis_id: Hashable
    values_revision: Hashable
    axis_revision: Hashable
    top: float
    bottom: float
    max_points: int
    positive_values_only: bool


@dataclass(frozen=True, slots=True)
class GeometryCacheStats:
    hits: int
    misses: int
    evictions: int
    entries: int

    @property
    def requests(self) -> int:
        return self.hits + self.misses

    @property
    def hit_ratio(self) -> float:
        return self.hits / self.requests if self.requests else 0.0


class CurveGeometryCache:
    """Small LRU cache for peak-preserving viewport geometry.

    The cache stores already filtered/downsampled arrays. It intentionally does not
    own source LAS data and can therefore be cleared safely on dataset or axis change.
    """

    def __init__(self, *, max_entries: int = 256) -> None:
        if max_entries < 1:
            raise ValueError("Размер кэша геометрии должен быть положительным")
        self._max_entries = max_entries
        self._entries: OrderedDict[
            CurveGeometryKey, tuple[NDArray[np.float64], NDArray[np.float64]]
        ] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get_or_build(
        self,
        key: CurveGeometryKey,
        axis: NDArray[np.float64],
        values: NDArray[np.float64],
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        cached = self._entries.get(key)
        if cached is not None:
            self._hits += 1
            self._entries.move_to_end(key)
            return cached

        self._misses += 1
        sampled_values, sampled_axis = select_visible_samples(
            axis,
            values,
            key.top,
            key.bottom,
            max_points=key.max_points,
            positive_values_only=key.positive_values_only,
        )
        # Prevent accidental mutation of cached geometry by callers.
        sampled_values.setflags(write=False)
        sampled_axis.setflags(write=False)
        geometry = (sampled_values, sampled_axis)
        self._entries[key] = geometry
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
            self._evictions += 1
        return geometry

    def clear(self) -> None:
        self._entries.clear()

    def invalidate_curve(self, curve_id: Hashable) -> int:
        keys = [key for key in self._entries if key.curve_id == curve_id]
        for key in keys:
            del self._entries[key]
        return len(keys)

    def stats(self) -> GeometryCacheStats:
        return GeometryCacheStats(
            hits=self._hits,
            misses=self._misses,
            evictions=self._evictions,
            entries=len(self._entries),
        )
