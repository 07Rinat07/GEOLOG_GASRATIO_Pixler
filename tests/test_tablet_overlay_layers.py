from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.tablet.overlay_layers import (
    DEFAULT_Z_ORDER,
    OverlayLayerKind,
    OverlayLayerManager,
)


@dataclass
class FakeItem:
    visible: bool = True
    z: float = 0.0

    def setVisible(self, visible: bool) -> None:
        self.visible = bool(visible)

    def setZValue(self, z: float) -> None:
        self.z = float(z)


def test_overlay_layers_have_independent_visibility_and_z_order() -> None:
    manager = OverlayLayerManager()
    cursor = FakeItem()
    annotation = FakeItem()

    manager.register(OverlayLayerKind.CURSOR, "gas", cursor)
    manager.register(OverlayLayerKind.ANNOTATION, "gas", annotation)

    assert cursor.z == DEFAULT_Z_ORDER[OverlayLayerKind.CURSOR]
    assert annotation.z == DEFAULT_Z_ORDER[OverlayLayerKind.ANNOTATION]
    assert manager.set_visible(OverlayLayerKind.ANNOTATION, False)
    assert not annotation.visible
    assert cursor.visible
    assert manager.set_z_value(OverlayLayerKind.CURSOR, 120.0)
    assert cursor.z == 120.0
    assert annotation.z == DEFAULT_Z_ORDER[OverlayLayerKind.ANNOTATION]


def test_overlay_dirty_state_is_consumed_per_layer() -> None:
    manager = OverlayLayerManager()
    for kind in OverlayLayerKind:
        manager.consume_dirty(kind)

    manager.mark_dirty(OverlayLayerKind.CURSOR)
    manager.mark_dirty(OverlayLayerKind.PREVIEW)

    assert set(manager.dirty_layers()) == {
        OverlayLayerKind.CURSOR,
        OverlayLayerKind.PREVIEW,
    }
    assert manager.consume_dirty(OverlayLayerKind.CURSOR)
    assert not manager.consume_dirty(OverlayLayerKind.CURSOR)
    assert manager.dirty_layers() == (OverlayLayerKind.PREVIEW,)


def test_clear_track_removes_only_target_track_items() -> None:
    manager = OverlayLayerManager()
    first = FakeItem()
    second = FakeItem()
    manager.register(OverlayLayerKind.MARKER, "first", first)
    manager.register(OverlayLayerKind.MARKER, "second", second)

    manager.clear_track("first")

    assert manager.items(OverlayLayerKind.MARKER, "first") == ()
    assert manager.items(OverlayLayerKind.MARKER, "second") == (second,)
    assert manager.stats().items == 1
