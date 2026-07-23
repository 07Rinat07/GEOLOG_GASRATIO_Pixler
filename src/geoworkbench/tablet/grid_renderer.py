from __future__ import annotations

from dataclasses import dataclass
from typing import cast

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
    "TabletGridOverlay",
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


class TabletGridOverlay:
    """Grid lines that stay visible even when tablet axes are intentionally hidden.

    Tablet curve columns use normalized horizontal geometry because every curve may
    have an independent engineering range.  Their bottom and left ``AxisItem``
    instances are therefore hidden in the workspace, which also disables
    ``PlotItem.showGrid`` in pyqtgraph.  This overlay projects the same normalized
    major/minor contract used by print rendering directly into the current ViewBox.
    It does not intercept input and is refreshed whenever the visible range changes.
    """

    def __init__(self, plot: pg.PlotWidget) -> None:
        self.plot = plot
        self.settings = GridSettings(True, True, 5, 5, 0.2)
        self._vertical: list[tuple[pg.InfiniteLine, bool]] = []
        self._horizontal: list[tuple[pg.InfiniteLine, bool]] = []
        self.plot.getViewBox().sigRangeChanged.connect(self._range_changed)

    @property
    def vertical_line_count(self) -> int:
        return len(self._vertical)

    @property
    def horizontal_line_count(self) -> int:
        return len(self._horizontal)

    def apply(self, settings: GridSettings) -> None:
        self.settings = settings
        self._ensure_lines()
        self._refresh()

    def _ensure_lines(self) -> None:
        divisions = normalized_grid_lines(
            self.settings.major_divisions,
            self.settings.minor_divisions,
        )
        self._resize(self._vertical, len(divisions), angle=90)
        self._resize(self._horizontal, len(divisions), angle=0)
        for collection in (self._vertical, self._horizontal):
            for index, (line, _major) in enumerate(collection):
                major = divisions[index].major
                collection[index] = (line, major)
                line.setPen(self._pen(major))
                line.setVisible(
                    self.settings.show_x if collection is self._vertical else self.settings.show_y
                )

    def _resize(
        self,
        collection: list[tuple[pg.InfiniteLine, bool]],
        target: int,
        *,
        angle: int,
    ) -> None:
        while len(collection) > target:
            line, _major = collection.pop()
            self.plot.removeItem(line)
        while len(collection) < target:
            line = pg.InfiniteLine(
                angle=angle,
                movable=False,
                pen=self._pen(False),
            )
            line.setZValue(-1_000.0)
            line.setAcceptedMouseButtons(0)
            self.plot.addItem(line, ignoreBounds=True)
            collection.append((line, False))

    def _pen(self, major: bool):
        color = pg.mkColor("#64748b" if major else "#94a3b8")
        alpha = self.settings.alpha if major else self.settings.alpha * 0.45
        color.setAlphaF(max(0.0, min(1.0, float(alpha))))
        return pg.mkPen(color, width=0.9 if major else 0.55)

    def _range_changed(self, *_args: object) -> None:
        self._refresh()

    def _refresh(self) -> None:
        ranges = self.plot.getViewBox().viewRange()
        if len(ranges) != 2:
            return
        x_min, x_max = sorted((float(ranges[0][0]), float(ranges[0][1])))
        y_min, y_max = sorted((float(ranges[1][0]), float(ranges[1][1])))
        divisions = normalized_grid_lines(
            self.settings.major_divisions,
            self.settings.minor_divisions,
        )
        for index, grid_line in enumerate(divisions):
            if index < len(self._vertical):
                line, _major = self._vertical[index]
                line.setPos(x_min + (x_max - x_min) * grid_line.fraction)
                line.setVisible(self.settings.show_x)
            if index < len(self._horizontal):
                line, _major = self._horizontal[index]
                line.setPos(y_min + (y_max - y_min) * grid_line.fraction)
                line.setVisible(self.settings.show_y)


class TabletGridRenderer:
    """Apply one saved grid configuration to a tablet plot."""

    _OVERLAY_ATTRIBUTE = "_geoworkbench_grid_overlay"

    @classmethod
    def apply(cls, plot: pg.PlotWidget, settings: GridSettings) -> None:
        for axis_name in ("left", "bottom"):
            axis = plot.getAxis(axis_name)
            if isinstance(axis, EngineeringGridAxisItem):
                axis.set_engineering_divisions(
                    settings.major_divisions,
                    settings.minor_divisions,
                )
        # Axis-based grids disappear when an AxisItem is hidden. Tablet columns
        # intentionally hide those axes, so the independent overlay is the source
        # of truth for screen rendering and prevents a blank graph after loading.
        plot.showGrid(x=False, y=False)
        overlay = cls.overlay_for(plot)
        if overlay is None:
            overlay = TabletGridOverlay(plot)
            setattr(plot, cls._OVERLAY_ATTRIBUTE, overlay)
        overlay.apply(settings)

    @classmethod
    def overlay_for(cls, plot: pg.PlotWidget) -> TabletGridOverlay | None:
        value = getattr(plot, cls._OVERLAY_ATTRIBUTE, None)
        return cast(TabletGridOverlay | None, value)
