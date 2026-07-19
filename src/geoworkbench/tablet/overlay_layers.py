from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class OverlayItem(Protocol):
    def setVisible(self, visible: bool) -> None: ...
    def setZValue(self, z: float) -> None: ...


class OverlayLayerKind(str, Enum):
    MARKER = "marker"
    ANNOTATION = "annotation"
    PREVIEW = "preview"
    SELECTION = "selection"
    RUBBER_BAND = "rubber_band"
    TOOLTIP = "tooltip"
    CURSOR = "cursor"


DEFAULT_Z_ORDER: dict[OverlayLayerKind, float] = {
    OverlayLayerKind.MARKER: 60.0,
    OverlayLayerKind.ANNOTATION: 70.0,
    OverlayLayerKind.PREVIEW: 75.0,
    OverlayLayerKind.SELECTION: 80.0,
    OverlayLayerKind.RUBBER_BAND: 85.0,
    OverlayLayerKind.TOOLTIP: 90.0,
    OverlayLayerKind.CURSOR: 100.0,
}


@dataclass(slots=True)
class OverlayLayerState:
    kind: OverlayLayerKind
    z_value: float
    visible: bool = True
    dirty: bool = True
    revision: int = 0
    items_by_track: dict[str, list[OverlayItem]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OverlayLayerStats:
    dirty_marks: int
    updates: int
    item_registrations: int
    item_removals: int
    layers: int
    items: int


class OverlayLayerManager:
    """Owns independent dynamic layers rendered above tablet curves.

    The manager is deliberately UI-toolkit-light: it only requires items to
    support ``setVisible`` and ``setZValue``. This keeps layer state testable
    without rebuilding tracks or touching curve geometry.
    """

    def __init__(self) -> None:
        self._layers = {
            kind: OverlayLayerState(kind=kind, z_value=z)
            for kind, z in DEFAULT_Z_ORDER.items()
        }
        self._dirty_marks = 0
        self._updates = 0
        self._item_registrations = 0
        self._item_removals = 0

    def register(self, kind: OverlayLayerKind, track_id: str, item: OverlayItem) -> None:
        state = self._layers[kind]
        items = state.items_by_track.setdefault(track_id, [])
        if item in items:
            return
        items.append(item)
        item.setZValue(state.z_value)
        if not state.visible:
            item.setVisible(False)
        state.dirty = True
        state.revision += 1
        self._item_registrations += 1

    def unregister(self, kind: OverlayLayerKind, track_id: str, item: OverlayItem) -> None:
        state = self._layers[kind]
        items = state.items_by_track.get(track_id)
        if not items or item not in items:
            return
        items.remove(item)
        if not items:
            state.items_by_track.pop(track_id, None)
        state.dirty = True
        state.revision += 1
        self._item_removals += 1

    def clear_track(self, track_id: str) -> None:
        for state in self._layers.values():
            removed = state.items_by_track.pop(track_id, [])
            if removed:
                state.dirty = True
                state.revision += 1
                self._item_removals += len(removed)

    def clear(self) -> None:
        for state in self._layers.values():
            removed = sum(len(items) for items in state.items_by_track.values())
            state.items_by_track.clear()
            if removed:
                state.dirty = True
                state.revision += 1
                self._item_removals += removed

    def mark_dirty(self, kind: OverlayLayerKind) -> None:
        state = self._layers[kind]
        state.dirty = True
        state.revision += 1
        self._dirty_marks += 1

    def consume_dirty(self, kind: OverlayLayerKind) -> bool:
        state = self._layers[kind]
        was_dirty = state.dirty
        if was_dirty:
            state.dirty = False
            self._updates += 1
        return was_dirty

    def dirty_layers(self) -> tuple[OverlayLayerKind, ...]:
        return tuple(kind for kind, state in self._layers.items() if state.dirty)

    def set_visible(self, kind: OverlayLayerKind, visible: bool) -> bool:
        state = self._layers[kind]
        visible = bool(visible)
        if state.visible == visible:
            return False
        state.visible = visible
        for items in state.items_by_track.values():
            for item in items:
                item.setVisible(visible)
        self.mark_dirty(kind)
        return True

    def is_visible(self, kind: OverlayLayerKind) -> bool:
        return self._layers[kind].visible

    def set_z_value(self, kind: OverlayLayerKind, z_value: float) -> bool:
        state = self._layers[kind]
        z_value = float(z_value)
        if state.z_value == z_value:
            return False
        state.z_value = z_value
        for items in state.items_by_track.values():
            for item in items:
                item.setZValue(z_value)
        self.mark_dirty(kind)
        return True

    def z_value(self, kind: OverlayLayerKind) -> float:
        return self._layers[kind].z_value

    def revision(self, kind: OverlayLayerKind) -> int:
        return self._layers[kind].revision

    def items(self, kind: OverlayLayerKind, track_id: str | None = None) -> tuple[OverlayItem, ...]:
        state = self._layers[kind]
        if track_id is not None:
            return tuple(state.items_by_track.get(track_id, ()))
        return tuple(item for items in state.items_by_track.values() for item in items)

    def stats(self) -> OverlayLayerStats:
        return OverlayLayerStats(
            dirty_marks=self._dirty_marks,
            updates=self._updates,
            item_registrations=self._item_registrations,
            item_removals=self._item_removals,
            layers=len(self._layers),
            items=sum(
                len(items)
                for state in self._layers.values()
                for items in state.items_by_track.values()
            ),
        )
