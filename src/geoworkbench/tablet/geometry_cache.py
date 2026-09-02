from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Hashable

import numpy as np
from numpy.typing import NDArray

from geoworkbench.tablet.derived_gas_sampling import select_derived_gas_samples
from geoworkbench.tablet.sampling import select_visible_samples


DEFAULT_CURVE_GEOMETRY_CACHE_MAX_BYTES = 64 * 1024 * 1024

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

_DERIVED_GAS_CURVE_EXACT_IDS = frozenset(
    {
        "C1_C2",
        "C1_C3",
        "C2_C3",
        "C1_C2C3",
        "C1_C4",
        "C1_C5",
        "WH",
        "BH",
        "CH",
        "WETNESS",
        "BALANCE",
        "CHARACTER",
        "IC4_NC4",
        "IC5_NC5",
    }
)


def _normalized_curve_token(curve_id: Hashable) -> str:
    token = str(curve_id).strip().upper().replace("-", "_")
    return token.rsplit(":", 1)[-1]


def is_derived_gas_curve_id(curve_id: Hashable) -> bool:
    """Return whether a curve is calculated from sparse gas updates."""

    token = _normalized_curve_token(curve_id)
    return (
        token in _DERIVED_GAS_CURVE_EXACT_IDS
        or token.startswith("PIXLER_")
        or token.endswith("_REL")
        or token.endswith("_NORM")
        or token.endswith("_NORM_REF")
    )


def is_gas_curve_id(curve_id: Hashable) -> bool:
    """Return whether a rendered curve uses a gas continuity policy."""

    token = _normalized_curve_token(curve_id)
    return token in _GAS_CURVE_EXACT_IDS or is_derived_gas_curve_id(token)


def _bridges_sparse_time_updates(axis_id: Hashable) -> bool:
    """Return whether a GeoScape/Paradox time axis uses sparse channel updates."""

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


Geometry = tuple[NDArray[np.float64], NDArray[np.float64]]


class CurveGeometryCache:
    """LRU cache for sampled viewport geometry with a hard NumPy byte budget.

    ``max_bytes`` accounts for the payload owned by cached NumPy arrays. Python
    object/key/``OrderedDict`` overhead is implementation-dependent and remains
    bounded separately by ``max_entries``.
    """

    def __init__(
        self,
        *,
        max_entries: int = 256,
        max_bytes: int = DEFAULT_CURVE_GEOMETRY_CACHE_MAX_BYTES,
    ) -> None:
        if max_entries < 1:
            raise ValueError("Размер кэша геометрии должен быть положительным")
        if max_bytes < 1:
            raise ValueError("Бюджет кэша геометрии должен быть положительным")
        self._max_entries = int(max_entries)
        self._max_bytes = int(max_bytes)
        self._current_bytes = 0
        self._entries: OrderedDict[CurveGeometryKey, Geometry] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @property
    def max_entries(self) -> int:
        return self._max_entries

    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    @property
    def current_bytes(self) -> int:
        return self._current_bytes

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    def get_or_build(
        self,
        key: CurveGeometryKey,
        axis: NDArray[np.float64],
        values: NDArray[np.float64],
    ) -> Geometry:
        cached = self._entries.get(key)
        if cached is not None:
            self._hits += 1
            self._entries.move_to_end(key)
            return cached

        self._misses += 1
        derived_gas_curve = is_derived_gas_curve_id(key.curve_id)
        gas_curve = derived_gas_curve or is_gas_curve_id(key.curve_id)
        if derived_gas_curve:
            sampled_values, sampled_axis = select_derived_gas_samples(
                axis,
                values,
                key.top,
                key.bottom,
                max_points=key.max_points,
                positive_values_only=key.positive_values_only,
            )
        else:
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
        sampled_values.setflags(write=False)
        sampled_axis.setflags(write=False)
        geometry = (sampled_values, sampled_axis)
        geometry_bytes = _geometry_nbytes(geometry)

        # A single pathological viewport must never evict the whole cache and
        # then remain resident above the configured hard payload budget.
        if geometry_bytes > self._max_bytes:
            return geometry

        self._entries[key] = geometry
        self._current_bytes += geometry_bytes
        self._entries.move_to_end(key)
        self._evict_to_budget()
        return geometry

    def clear(self) -> None:
        self._entries.clear()
        self._current_bytes = 0

    def invalidate_curve(self, curve_id: Hashable) -> int:
        keys = [key for key in self._entries if key.curve_id == curve_id]
        for key in keys:
            self._remove(key, count_eviction=False)
        return len(keys)

    def stats(self) -> GeometryCacheStats:
        return GeometryCacheStats(
            hits=self._hits,
            misses=self._misses,
            evictions=self._evictions,
            entries=len(self._entries),
        )

    def _evict_to_budget(self) -> None:
        while len(self._entries) > self._max_entries or self._current_bytes > self._max_bytes:
            key = next(iter(self._entries))
            self._remove(key, count_eviction=True)

    def _remove(self, key: CurveGeometryKey, *, count_eviction: bool) -> None:
        geometry = self._entries.pop(key)
        self._current_bytes -= _geometry_nbytes(geometry)
        if count_eviction:
            self._evictions += 1


def _geometry_nbytes(geometry: Geometry) -> int:
    values, axis = geometry
    return int(values.nbytes + axis.nbytes)
