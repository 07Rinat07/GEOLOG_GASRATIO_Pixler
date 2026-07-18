from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Hashable


@dataclass(frozen=True, slots=True)
class StaticLayerKey:
    track_id: str
    layer: str
    signature: Hashable


@dataclass(frozen=True, slots=True)
class StaticLayerCacheStats:
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


class StaticLayerCache:
    """Small LRU cache for immutable per-track render descriptors.

    The cache stores lightweight prepared descriptors for titles, axes and grids.
    Qt graphics objects remain owned by their widgets; this cache only prevents
    rebuilding identical static configuration during targeted refreshes.
    """

    def __init__(self, *, max_entries: int = 256) -> None:
        if max_entries < 1:
            raise ValueError("Размер кэша статических слоёв должен быть положительным")
        self._max_entries = max_entries
        self._entries: OrderedDict[StaticLayerKey, object] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get_or_build(self, key: StaticLayerKey, builder) -> object:
        cached = self._entries.get(key)
        if cached is not None:
            self._hits += 1
            self._entries.move_to_end(key)
            return cached
        self._misses += 1
        value = builder()
        self._entries[key] = value
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
            self._evictions += 1
        return value

    def invalidate_track(self, track_id: str) -> int:
        keys = [key for key in self._entries if key.track_id == track_id]
        for key in keys:
            del self._entries[key]
        return len(keys)

    def clear(self) -> None:
        self._entries.clear()

    def stats(self) -> StaticLayerCacheStats:
        return StaticLayerCacheStats(
            hits=self._hits,
            misses=self._misses,
            evictions=self._evictions,
            entries=len(self._entries),
        )
