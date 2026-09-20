from __future__ import annotations

from pathlib import Path

import numpy as np

from geoworkbench.tablet.geometry_cache import CurveGeometryKey
from geoworkbench.tablet.render_invalidation import DirtyReason
from geoworkbench.tablet.render_state import TabletRenderState
from geoworkbench.tablet.static_layer_cache import StaticLayerKey


def _geometry_key(curve_id: str) -> CurveGeometryKey:
    return CurveGeometryKey(
        curve_id=curve_id,
        axis_id="depth",
        values_revision="values-r1",
        axis_revision="depth-r1",
        top=0.0,
        bottom=3.0,
        max_points=100,
        positive_values_only=False,
    )


def test_render_state_invalidates_geometry_and_static_cache_for_track() -> None:
    state = TabletRenderState()
    axis = np.asarray([0.0, 1.0, 2.0, 3.0], dtype=np.float64)
    values = np.asarray([10.0, 11.0, 12.0, 13.0], dtype=np.float64)
    state.geometry_cache.get_or_build(_geometry_key("GR"), axis, values)
    static_key = StaticLayerKey("track-1", "grid", "r1")
    state.static_layer_cache.get_or_build(static_key, lambda: ("grid", 1))

    state.invalidate_track(
        "track-1",
        DirtyReason.DATA | DirtyReason.STATIC,
        curve_ids=("GR",),
    )

    assert state.geometry_cache.entry_count == 0
    assert state.static_layer_cache.stats().entries == 0
    dirty = state.dirty_registry.consume()
    assert dirty == {"track-1": DirtyReason.DATA | DirtyReason.STATIC}


def test_render_state_layout_invalidation_clears_both_cache_scopes() -> None:
    state = TabletRenderState()
    axis = np.asarray([0.0, 1.0, 2.0], dtype=np.float64)
    values = np.asarray([1.0, 2.0, 3.0], dtype=np.float64)
    state.geometry_cache.get_or_build(_geometry_key("ROP"), axis, values)
    state.static_layer_cache.get_or_build(
        StaticLayerKey("track-2", "axis", "r1"),
        lambda: ("axis", 1),
    )

    state.invalidate_track(
        "track-2",
        DirtyReason.LAYOUT,
        curve_ids=("ROP",),
    )

    assert state.geometry_cache.entry_count == 0
    assert state.static_layer_cache.stats().entries == 0
    assert state.dirty_stats().pending_tracks == 1


def test_render_state_clear_methods_reset_owned_components() -> None:
    state = TabletRenderState()
    axis = np.asarray([0.0, 1.0], dtype=np.float64)
    values = np.asarray([1.0, 2.0], dtype=np.float64)
    state.geometry_cache.get_or_build(_geometry_key("GR"), axis, values)
    state.static_layer_cache.get_or_build(
        StaticLayerKey("track-1", "title", "r1"),
        lambda: "title",
    )
    state.dirty_registry.mark("track-1", DirtyReason.DATA)

    state.clear_caches()
    state.clear_render_state()

    assert state.geometry_cache.entry_count == 0
    assert state.static_layer_cache.stats().entries == 0
    assert state.dirty_stats().pending_tracks == 0


def test_tablet_view_delegates_render_state_ownership() -> None:
    source = Path("src/geoworkbench/tablet/tablet_view.py").read_text(encoding="utf-8")

    assert "self._render_state = TabletRenderState()" in source
    assert "self._geometry_cache = CurveGeometryCache(" not in source
    assert "self._static_layer_cache = StaticLayerCache(" not in source
    assert "self._dirty_registry = TrackDirtyRegistry()" not in source
    assert "self._overlay_layers = OverlayLayerManager()" not in source
    assert "self._render_state.invalidate_track(" in source
