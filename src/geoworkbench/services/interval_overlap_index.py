from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from typing import Generic, Iterable, Protocol, TypeVar


class DepthInterval(Protocol):
    top_depth: float
    bottom_depth: float


T = TypeVar("T", bound=DepthInterval)


@dataclass(frozen=True, slots=True)
class IntervalOverlapIndex(Generic[T]):
    """Immutable overlap index for depth intervals.

    The index preserves the legacy inclusive boundary semantics used by the
    Masterlog renderer: an interval is visible when bottom_depth >= page_top
    and top_depth <= page_bottom.

    Query cost is O(log n + k) for ordinary non-pathological data instead of
    scanning every interval for every rendered page/track.
    """

    _items: tuple[T, ...]
    _tops: tuple[float, ...]
    _prefix_max_bottom: tuple[float, ...]

    @classmethod
    def build(cls, items: Iterable[T]) -> "IntervalOverlapIndex[T]":
        ordered = tuple(
            sorted(
                items,
                key=lambda item: (
                    float(item.top_depth),
                    float(item.bottom_depth),
                ),
            )
        )
        tops = tuple(float(item.top_depth) for item in ordered)
        prefix: list[float] = []
        maximum_bottom = float("-inf")
        for item in ordered:
            maximum_bottom = max(maximum_bottom, float(item.bottom_depth))
            prefix.append(maximum_bottom)
        return cls(ordered, tops, tuple(prefix))

    @property
    def items(self) -> tuple[T, ...]:
        return self._items

    def overlapping(self, top_depth: float, bottom_depth: float) -> tuple[T, ...]:
        top = float(top_depth)
        bottom = float(bottom_depth)
        if bottom < top:
            raise ValueError("Нижняя граница интервала должна быть не меньше верхней")
        if not self._items:
            return ()

        end = bisect_right(self._tops, bottom)
        if end <= 0:
            return ()

        start = bisect_left(self._prefix_max_bottom, top, 0, end)
        if start >= end:
            return ()

        return tuple(
            item
            for item in self._items[start:end]
            if float(item.bottom_depth) >= top
        )


__all__ = ["DepthInterval", "IntervalOverlapIndex"]
