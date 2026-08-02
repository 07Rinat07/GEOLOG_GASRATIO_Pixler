from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Hashable

import numpy as np
from numpy.typing import NDArray

from geoworkbench.tablet.sampling import select_visible_samples


_PARADOX_SPARSE_TIME_AXIS_SUFFIXES = (
    ":paradox-datetime",
    ":paradox-elapsed",
)

_GAS_CURVE_EXACT_IDS = frozenset(
    {
        "C1",
        "C2",
        "C3",
        "C4",
        "C5",
        "IC4",
        "NC4",
        "IC5",
        "NC5",
        "TOTAL_GAS",
        "TG_CALC",
        "TG_NORM",
        "WETNESS",
        "BALANCE",
        "CHARACTER",
        "IC4_NC4",
        "IC5_NC5",
    }
)


def is_gas_curve_id(curve_id: Hashable) -> bool:
    """Return whether a rendered curve uses the sparse gas policy."""

    token = str(curve_id).strip().upper().replace("-", "_")
    token = token.rsplit(":", 1)[-1]
    return (
        token in _GAS_CURVE_EXACT_IDS
        or token.startswith("PIXLER_")
        or token.endswith("_REL")
        or token.endswith("_NORM")
        or token.endswith("_NORM_REF")
    )


def _bridges_sparse_time_updates(axis_id: Hashable) -> bool:
    """Return whether a GeoScape/Paradox time axis uses sparse channel updates.

    GeoScape writes a common time row while individual channels can remain NULL
    until their next update.  Those NULL rows are not an acquisition outage and
    must not fragment every curve on a time-based form.  The importer owns these
    stable index-id suffixes, so depth/LAS axes retain the normal NULL-gap policy.
    """

    normalized = str(axis_id).strip().casefold()
    return normalized.endswith(_PARADOX_SPARSE_TIME_AXIS_SUFFIXES)


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
        gas_curve = is_gas_curve_id(key.curve_id)
        sampled_values, sampled_axis = select_visible_samples(
            axis,
            values,
            key.top,
            key.bottom,
            max_points=key.max_points,
            positive_values_only=key.positive_values_only,
            include_viewport_context=gas_curve,
            bridge_sparse_updates=_bridges_sparse_time_updates(key.axis_id),
            bridge_short_gaps=gas_curve,
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
