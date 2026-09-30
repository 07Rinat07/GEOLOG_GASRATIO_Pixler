from __future__ import annotations

from dataclasses import dataclass
from enum import IntFlag, auto


class PresentationRefreshIntent(IntFlag):
    """Cheap presentation surfaces that may be safely coalesced."""

    NONE = 0
    PROJECT_TREE = auto()
    WINDOW_TITLE = auto()


@dataclass(frozen=True, slots=True)
class PresentationRefreshBatch:
    intents: PresentationRefreshIntent
    request_count: int

    @property
    def is_empty(self) -> bool:
        return self.intents is PresentationRefreshIntent.NONE


class PresentationRefreshAccumulator:
    """Merge duplicate presentation refresh requests without owning a scheduler."""

    def __init__(self) -> None:
        self._pending = PresentationRefreshIntent.NONE
        self._request_count = 0

    @property
    def pending(self) -> PresentationRefreshIntent:
        return self._pending

    @property
    def request_count(self) -> int:
        return self._request_count

    def request(self, intents: PresentationRefreshIntent) -> bool:
        if not isinstance(intents, PresentationRefreshIntent):
            raise TypeError("intents must be PresentationRefreshIntent")
        if intents is PresentationRefreshIntent.NONE:
            return False
        self._pending |= intents
        self._request_count += 1
        return True

    def consume(self) -> PresentationRefreshBatch:
        batch = PresentationRefreshBatch(
            intents=self._pending,
            request_count=self._request_count,
        )
        self._pending = PresentationRefreshIntent.NONE
        self._request_count = 0
        return batch

    def clear(self) -> None:
        self._pending = PresentationRefreshIntent.NONE
        self._request_count = 0


__all__ = [
    "PresentationRefreshAccumulator",
    "PresentationRefreshBatch",
    "PresentationRefreshIntent",
]
