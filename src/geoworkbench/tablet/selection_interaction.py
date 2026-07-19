from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Protocol


class SelectableKind(StrEnum):
    TRACK = "track"
    CURVE = "curve"
    INTERVAL = "interval"
    MARKER = "marker"
    ANNOTATION = "annotation"
    COLUMN = "column"


class InteractionMode(StrEnum):
    IDLE = "idle"
    HOVER = "hover"
    PRESSED = "pressed"
    DRAGGING = "dragging"
    RESIZING = "resizing"


@dataclass(frozen=True, slots=True, order=True)
class SelectionRef:
    kind: SelectableKind
    object_id: str
    track_id: str | None = None

    def __post_init__(self) -> None:
        if not self.object_id.strip():
            raise ValueError("object_id должен быть непустой строкой")
        if self.track_id is not None and not self.track_id.strip():
            raise ValueError("track_id должен быть непустой строкой или null")


@dataclass(frozen=True, slots=True)
class HitResult:
    target: SelectionRef
    priority: int = 0
    distance_px: float = 0.0
    local_x: float | None = None
    local_y: float | None = None

    def __post_init__(self) -> None:
        if self.distance_px < 0:
            raise ValueError("distance_px не может быть отрицательным")


def choose_best_hit(hits: list[HitResult] | tuple[HitResult, ...]) -> HitResult | None:
    """Return the most specific hit.

    Higher priority wins; distance is used as the stable secondary criterion.
    The function is UI-independent and can be shared by tracks and overlays.
    """

    if not hits:
        return None
    return min(hits, key=lambda hit: (-hit.priority, hit.distance_px))


@dataclass(frozen=True, slots=True)
class SelectionSnapshot:
    items: tuple[SelectionRef, ...]
    primary: SelectionRef | None


class SelectionManager:
    """Single and multi-selection state shared by tablet objects."""

    def __init__(self) -> None:
        self._items: list[SelectionRef] = []
        self._primary: SelectionRef | None = None
        self._revision = 0

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def primary(self) -> SelectionRef | None:
        return self._primary

    def snapshot(self) -> SelectionSnapshot:
        return SelectionSnapshot(tuple(self._items), self._primary)

    def contains(self, item: SelectionRef) -> bool:
        return item in self._items

    def select(self, item: SelectionRef, *, additive: bool = False, toggle: bool = False) -> bool:
        before = self.snapshot()
        if toggle and item in self._items:
            self._items.remove(item)
            if self._primary == item:
                self._primary = self._items[-1] if self._items else None
        else:
            if not additive:
                self._items.clear()
            if item not in self._items:
                self._items.append(item)
            self._primary = item
        changed = self.snapshot() != before
        if changed:
            self._revision += 1
        return changed

    def replace(self, items: list[SelectionRef] | tuple[SelectionRef, ...], *, primary: SelectionRef | None = None) -> bool:
        unique: list[SelectionRef] = []
        for item in items:
            if item not in unique:
                unique.append(item)
        if primary is not None and primary not in unique:
            raise ValueError("Основной объект должен входить в набор выделения")
        before = self.snapshot()
        self._items = unique
        self._primary = primary if primary is not None else (unique[-1] if unique else None)
        changed = self.snapshot() != before
        if changed:
            self._revision += 1
        return changed

    def clear(self, *, kind: SelectableKind | None = None) -> bool:
        before = self.snapshot()
        if kind is None:
            self._items.clear()
            self._primary = None
        else:
            self._items = [item for item in self._items if item.kind is not kind]
            if self._primary is not None and self._primary.kind is kind:
                self._primary = self._items[-1] if self._items else None
        changed = self.snapshot() != before
        if changed:
            self._revision += 1
        return changed


class UndoableCommand(Protocol):
    description: str

    def redo(self) -> None: ...
    def undo(self) -> None: ...


class CommandStack:
    """Small generic Undo/Redo stack for future tablet interactions."""

    def __init__(self, *, limit: int = 200) -> None:
        if limit <= 0:
            raise ValueError("limit должен быть положительным")
        self._limit = limit
        self._undo: list[UndoableCommand] = []
        self._redo: list[UndoableCommand] = []

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def execute(self, command: UndoableCommand) -> None:
        command.redo()
        self._undo.append(command)
        if len(self._undo) > self._limit:
            del self._undo[0]
        self._redo.clear()

    def undo(self) -> bool:
        if not self._undo:
            return False
        command = self._undo.pop()
        command.undo()
        self._redo.append(command)
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        command = self._redo.pop()
        command.redo()
        self._undo.append(command)
        return True

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()


@dataclass(slots=True)
class CallbackCommand:
    """Undoable command backed by two callbacks."""

    description: str
    _redo_callback: Callable[[], None]
    _undo_callback: Callable[[], None]

    def redo(self) -> None:
        self._redo_callback()

    def undo(self) -> None:
        self._undo_callback()


@dataclass(frozen=True, slots=True)
class TrackHeaderDrag:
    track_id: str
    source_index: int
    start_global_x: int

    def target_index(self, global_x: int, centers: tuple[tuple[int, int], ...]) -> int:
        """Return insertion index using visible track center points.

        ``centers`` contains ``(layout_index, global_center_x)`` pairs.
        """

        if not centers:
            return self.source_index
        ordered = sorted(centers, key=lambda item: item[1])
        for layout_index, center_x in ordered:
            if global_x < center_x:
                return layout_index
        return ordered[-1][0]
