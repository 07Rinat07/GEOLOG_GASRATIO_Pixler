from __future__ import annotations

from dataclasses import dataclass, field
from typing import Hashable

from geoworkbench.tablet.geometry_cache import (
    CurveGeometryCache,
    GeometryCacheStats,
)
from geoworkbench.tablet.overlay_layers import (
    OverlayLayerManager,
    OverlayLayerStats,
)
from geoworkbench.tablet.render_invalidation import (
    DirtyReason,
    DirtyRenderStats,
    TrackDirtyRegistry,
)
from geoworkbench.tablet.static_layer_cache import (
    StaticLayerCache,
    StaticLayerCacheStats,
)


@dataclass(slots=True)
class TabletRenderState:
    """Qt-independent owner of tablet render/cache state.

    Rendering code may still consume Qt graphics items through OverlayLayerManager's
    small protocol, but cache/invalidation ownership no longer belongs to
    TabletView itself.
    """

    geometry_cache: CurveGeometryCache = field(
        default_factory=lambda: CurveGeometryCache(max_entries=512)
    )
    static_layer_cache: StaticLayerCache = field(
        default_factory=lambda: StaticLayerCache(max_entries=512)
    )
    dirty_registry: TrackDirtyRegistry = field(default_factory=TrackDirtyRegistry)
    overlay_layers: OverlayLayerManager = field(default_factory=OverlayLayerManager)

    def geometry_stats(self) -> GeometryCacheStats:
        return self.geometry_cache.stats()

    def static_layer_stats(self) -> StaticLayerCacheStats:
        return self.static_layer_cache.stats()

    def dirty_stats(self) -> DirtyRenderStats:
        return self.dirty_registry.stats()

    def overlay_stats(self) -> OverlayLayerStats:
        return self.overlay_layers.stats()

    def invalidate_track(
        self,
        track_id: str,
        reason: DirtyReason,
        *,
        curve_ids: tuple[Hashable, ...] = (),
    ) -> None:
        if not track_id:
            return
        self.dirty_registry.mark(track_id, reason)
        if reason & (DirtyReason.DATA | DirtyReason.LAYOUT):
            for curve_id in curve_ids:
                self.geometry_cache.invalidate_curve(curve_id)
        if reason & (DirtyReason.STATIC | DirtyReason.LAYOUT):
            self.static_layer_cache.invalidate_track(track_id)

    def clear_caches(self) -> None:
        self.geometry_cache.clear()
        self.static_layer_cache.clear()

    def clear_render_state(self) -> None:
        self.dirty_registry.clear()
        self.overlay_layers.clear()


__all__ = ["TabletRenderState"]
