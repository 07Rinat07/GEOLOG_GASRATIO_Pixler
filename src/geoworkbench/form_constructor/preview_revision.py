from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PreviewRevisionGate:
    """Discards stale preview results after rapid form switching.

    Form Manager can increment the revision on each selection, render outside the
    selection handler, and apply a result only when `accepts(revision)` is true.
    This prevents an older expensive preview from replacing a newer selection.
    """

    _revision: int = 0

    def request(self) -> int:
        self._revision += 1
        return self._revision

    @property
    def current(self) -> int:
        return self._revision

    def accepts(self, revision: int) -> bool:
        return revision == self._revision

    def cancel_all(self) -> None:
        self._revision += 1
