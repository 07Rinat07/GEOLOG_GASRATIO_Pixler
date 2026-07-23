from __future__ import annotations

from dataclasses import dataclass

import pyqtgraph as pg

from geoworkbench.tablet.grid_geometry import (
    GridLine,
    engineering_tick_levels,
    normalized_grid_lines,
)
from geoworkbench.tablet.models import TrackDefinition


__all__ = [
    "EngineeringGridAxisItem",
    "GridLine",
    "GridSettings",
    "TabletGridRenderer",
    "engineering_tick_levels",
    "normalized_grid_lines",
]


@dataclass(frozen=True, slots=True)
class GridSettings:
    show_x: bool
    show_y: bool
    major_divisions: int
    minor_divisions: int
    alpha: float

    @classmethod
    def from_track(cls, track: TrackDefinition) -> GridSettings:
        return cls(
            show_x=bool(track.grid_x),
            show_y=bool(track.grid_y),
            major_divisions=int(track.grid_major_divisions),
            minor_divisions=int(track.grid_minor_divisions),
            alpha=float(track.grid_alpha),
        )


class EngineeringGridAxisItem(pg.AxisItem):
    """PyQtGraph axis with stable major and intermediate divisions."""

    def __init__(self, orientation: str) -> None:
        super().__init__(orientation=orientation)
        self._major_divisions = 5
        self._minor_divisions = 5

    def set_engineering_divisions(self, major: int, minor: int) -> None:
        self._major_divisions = max(1, int(major))
        self._minor_divisions = max(1, int(minor))
        self.setStyle(maxTickLevel=1 if self._minor_divisions > 1 else 0)
        self.picture = None
        self.update()

    def tickSpacing(self, minVal, maxVal, size):  # type: ignore[override]
        levels = engineering_tick_levels(
            float(minVal),
            float(maxVal),
            self._major_divisions,
            self._minor_divisions,
        )
        return list(levels) if levels else super().tickSpacing(minVal, maxVal, size)


class TabletGridRenderer:
    """Apply one saved grid configuration to every axis of a tablet plot."""

    @staticmethod
    def apply(plot: pg.PlotWidget, settings: GridSettings) -> None:
        for axis_name in ("left", "bottom"):
            axis = plot.getAxis(axis_name)
            if isinstance(axis, EngineeringGridAxisItem):
                axis.set_engineering_divisions(
                    settings.major_divisions,
                    settings.minor_divisions,
                )
        plot.showGrid(
            x=settings.show_x,
            y=settings.show_y,
            alpha=settings.alpha,
        )
