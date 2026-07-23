from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import pyqtgraph as pg

from geoworkbench.tablet.models import TrackDefinition


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


@dataclass(frozen=True, slots=True)
class GridLine:
    fraction: float
    major: bool


def engineering_tick_levels(
    minimum: float,
    maximum: float,
    major_divisions: int,
    minor_divisions: int,
) -> tuple[tuple[float, float], ...]:
    """Return pyqtgraph spacing levels for a stable engineering grid."""

    span = abs(float(maximum) - float(minimum))
    if not isfinite(span) or span <= 0.0:
        return ()
    major = max(1, int(major_divisions))
    minor = max(1, int(minor_divisions))
    origin = min(float(minimum), float(maximum))
    major_spacing = span / major
    levels = [(major_spacing, origin)]
    if minor > 1:
        levels.append((major_spacing / minor, origin))
    return tuple(levels)


def normalized_grid_lines(
    major_divisions: int,
    minor_divisions: int,
) -> tuple[GridLine, ...]:
    """Return ordered major/minor positions shared by print renderers."""

    major = max(1, int(major_divisions))
    minor = max(1, int(minor_divisions))
    lines: list[GridLine] = []
    for major_index in range(major + 1):
        lines.append(GridLine(major_index / major, True))
        if major_index == major or minor == 1:
            continue
        lines.extend(
            GridLine((major_index + minor_index / minor) / major, False)
            for minor_index in range(1, minor)
        )
    return tuple(lines)


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
