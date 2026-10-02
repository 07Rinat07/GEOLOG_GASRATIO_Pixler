from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import cos, pi, sin

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF

from geoworkbench.services.fluid_phase_contract import (
    FluidPhaseContract,
    fluid_phase_label,
    fluid_phase_from_hypothesis,
)
from geoworkbench.services.localization import AppLanguage


class FluidMarkerShape(StrEnum):
    CIRCLE = "circle"
    DIAMOND = "diamond"
    DIAMOND_OUTLINE = "diamond_outline"
    HEXAGON = "hexagon"
    PENTAGON = "pentagon"
    RING = "ring"
    TRIANGLE_UP = "triangle_up"
    TRIANGLE_DOWN = "triangle_down"
    SQUARE = "square"
    BAR = "bar"
    CROSS = "cross"


@dataclass(frozen=True, slots=True)
class FluidMarkerSpec:
    category: str
    code: str
    shape: FluidMarkerShape
    color: str
    phase: FluidPhaseContract
    order: int

    @property
    def label_ru(self) -> str:
        return fluid_phase_label(self.phase, AppLanguage.RU)

    @property
    def label_kk(self) -> str:
        return fluid_phase_label(self.phase, AppLanguage.KK)

    @property
    def label_en(self) -> str:
        return fluid_phase_label(self.phase, AppLanguage.EN)

    def label(self, language: AppLanguage) -> str:
        return fluid_phase_label(self.phase, language)


_SPECS: tuple[FluidMarkerSpec, ...] = (
    FluidMarkerSpec(
        "gas", "G", FluidMarkerShape.CIRCLE, "#2563eb", FluidPhaseContract.GAS, 10,
    ),
    FluidMarkerSpec(
        "liquid_or_condensate", "L/GC", FluidMarkerShape.DIAMOND_OUTLINE, "#7c3aed",
        FluidPhaseContract.LIQUID_OR_CONDENSATE, 20,
    ),
    FluidMarkerSpec(
        "light_oil", "LO", FluidMarkerShape.TRIANGLE_DOWN, "#ea580c",
        FluidPhaseContract.LIGHT_OIL, 30,
    ),
    FluidMarkerSpec(
        "liquid", "L", FluidMarkerShape.PENTAGON, "#ca8a04", FluidPhaseContract.LIQUID, 40,
    ),
    FluidMarkerSpec(
        "indeterminate", "?", FluidMarkerShape.CROSS, "#64748b",
        FluidPhaseContract.INDETERMINATE, 50,
    ),
)
_BY_PHASE = {item.phase: item for item in _SPECS}


def all_fluid_marker_specs() -> tuple[FluidMarkerSpec, ...]:
    return _SPECS


def fluid_marker_spec(fluid_hypothesis: str) -> FluidMarkerSpec:
    return _BY_PHASE[fluid_phase_from_hypothesis(fluid_hypothesis)]


def fluid_marker_legend_specs(
    hypotheses: tuple[str, ...] | list[str],
) -> tuple[FluidMarkerSpec, ...]:
    by_phase = {
        spec.phase: spec
        for spec in (fluid_marker_spec(item) for item in hypotheses)
    }
    return tuple(sorted(by_phase.values(), key=lambda item: item.order))


def marker_lanes(
    y_positions: tuple[float, ...] | list[float],
    *,
    minimum_gap: float,
) -> tuple[int, ...]:
    """Assign horizontal lanes while preserving every marker's true vertical position."""

    if minimum_gap < 0.0:
        raise ValueError("minimum_gap must not be negative")
    if not y_positions:
        return ()

    result = [0] * len(y_positions)
    last_y_by_lane: list[float] = []
    for index, y in sorted(enumerate(y_positions), key=lambda item: item[1]):
        lane = next(
            (
                lane_index
                for lane_index, last_y in enumerate(last_y_by_lane)
                if y - last_y >= minimum_gap
            ),
            len(last_y_by_lane),
        )
        if lane == len(last_y_by_lane):
            last_y_by_lane.append(y)
        else:
            last_y_by_lane[lane] = y
        result[index] = lane
    return tuple(result)


def marker_lane_offsets(
    lane_count: int,
    *,
    zone_width: float,
    max_spacing: float,
) -> tuple[float, ...]:
    """Return right-edge offsets whose centers always remain inside the reserved zone."""

    if lane_count < 0:
        raise ValueError("lane_count must not be negative")
    if lane_count == 0:
        return ()
    if zone_width <= 0.0:
        raise ValueError("zone_width must be positive")
    if max_spacing <= 0.0:
        raise ValueError("max_spacing must be positive")

    spacing = min(float(max_spacing), float(zone_width) / lane_count)
    return tuple((index + 0.5) * spacing for index in range(lane_count))


def draw_fluid_marker(
    painter: QPainter,
    center: QPointF,
    spec: FluidMarkerSpec,
    *,
    size: float,
) -> None:
    """Draw one colour + shape encoded marker; callers may add the short code separately."""

    size = max(1.0, float(size))
    half = size / 2.0
    color = QColor(spec.color)
    painter.save()
    painter.setPen(QPen(color, max(0.4, size * 0.13)))
    painter.setBrush(color)

    if spec.shape is FluidMarkerShape.CIRCLE:
        painter.drawEllipse(QRectF(center.x() - half, center.y() - half, size, size))
    elif spec.shape is FluidMarkerShape.RING:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(center.x() - half, center.y() - half, size, size))
    elif spec.shape in {FluidMarkerShape.DIAMOND, FluidMarkerShape.DIAMOND_OUTLINE}:
        if spec.shape is FluidMarkerShape.DIAMOND_OUTLINE:
            painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(center.x(), center.y() - half),
                    QPointF(center.x() + half, center.y()),
                    QPointF(center.x(), center.y() + half),
                    QPointF(center.x() - half, center.y()),
                ]
            )
        )
    elif spec.shape is FluidMarkerShape.HEXAGON:
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(
                        center.x() + half * cos(pi / 3.0 * index),
                        center.y() + half * sin(pi / 3.0 * index),
                    )
                    for index in range(6)
                ]
            )
        )
    elif spec.shape is FluidMarkerShape.PENTAGON:
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(
                        center.x() + half * cos(-pi / 2.0 + 2.0 * pi * index / 5.0),
                        center.y() + half * sin(-pi / 2.0 + 2.0 * pi * index / 5.0),
                    )
                    for index in range(5)
                ]
            )
        )
    elif spec.shape in {FluidMarkerShape.TRIANGLE_UP, FluidMarkerShape.TRIANGLE_DOWN}:
        direction = -1.0 if spec.shape is FluidMarkerShape.TRIANGLE_UP else 1.0
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(center.x(), center.y() + direction * half),
                    QPointF(center.x() - half, center.y() - direction * half),
                    QPointF(center.x() + half, center.y() - direction * half),
                ]
            )
        )
    elif spec.shape is FluidMarkerShape.SQUARE:
        painter.drawRect(QRectF(center.x() - half, center.y() - half, size, size))
    elif spec.shape is FluidMarkerShape.BAR:
        painter.drawRoundedRect(
            QRectF(center.x() - half, center.y() - size * 0.30, size, size * 0.60),
            size * 0.15,
            size * 0.15,
        )
    else:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(
            QLineF(
                center.x() - half,
                center.y() - half,
                center.x() + half,
                center.y() + half,
            )
        )
        painter.drawLine(
            QLineF(
                center.x() - half,
                center.y() + half,
                center.x() + half,
                center.y() - half,
            )
        )
    painter.restore()


__all__ = [
    "FluidMarkerShape",
    "FluidMarkerSpec",
    "all_fluid_marker_specs",
    "draw_fluid_marker",
    "fluid_marker_legend_specs",
    "fluid_marker_spec",
    "marker_lane_offsets",
    "marker_lanes",
]
