from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import cos, pi, sin

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF

from geoworkbench.services.localization import AppLanguage


class FluidMarkerShape(StrEnum):
    CIRCLE = "circle"
    DIAMOND = "diamond"
    DIAMOND_OUTLINE = "diamond_outline"
    HEXAGON = "hexagon"
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
    label_ru: str
    label_kk: str
    label_en: str
    order: int

    def label(self, language: AppLanguage) -> str:
        if language is AppLanguage.KK:
            return self.label_kk
        if language is AppLanguage.EN:
            return self.label_en
        return self.label_ru


_SPECS: tuple[FluidMarkerSpec, ...] = (
    FluidMarkerSpec("gas", "G", FluidMarkerShape.CIRCLE, "#2563eb", "газ", "газ", "gas", 10),
    FluidMarkerSpec(
        "gas_condensate",
        "GC",
        FluidMarkerShape.DIAMOND,
        "#0f766e",
        "газ-конденсат",
        "газ-конденсат",
        "gas condensate",
        20,
    ),
    FluidMarkerSpec(
        "gas_condensate_or_light_oil",
        "GC/O",
        FluidMarkerShape.DIAMOND_OUTLINE,
        "#7c3aed",
        "ГК / лёгк. нефть",
        "ГК / жеңіл мұнай",
        "GC / light oil",
        30,
    ),
    FluidMarkerSpec(
        "gas_condensate_or_gassy_oil",
        "GC/GO",
        FluidMarkerShape.HEXAGON,
        "#0d9488",
        "ГК / газир. нефть",
        "ГК / газдалған мұнай",
        "GC / gassy oil",
        40,
    ),
    FluidMarkerSpec(
        "dissolved_gas",
        "DG",
        FluidMarkerShape.RING,
        "#0891b2",
        "газ в воде",
        "судағы газ",
        "dissolved gas",
        50,
    ),
    FluidMarkerSpec(
        "gassy_oil",
        "GO",
        FluidMarkerShape.TRIANGLE_UP,
        "#b45309",
        "газир. нефть",
        "газдалған мұнай",
        "gassy oil",
        60,
    ),
    FluidMarkerSpec(
        "light_oil",
        "LO",
        FluidMarkerShape.TRIANGLE_DOWN,
        "#ea580c",
        "лёгк. нефть",
        "жеңіл мұнай",
        "light oil",
        70,
    ),
    FluidMarkerSpec("oil", "O", FluidMarkerShape.SQUARE, "#a16207", "нефть", "мұнай", "oil", 80),
    FluidMarkerSpec(
        "heavy_oil",
        "HO",
        FluidMarkerShape.BAR,
        "#78350f",
        "тяж./остат. нефть",
        "ауыр/қалдық мұнай",
        "heavy/residual oil",
        90,
    ),
    FluidMarkerSpec(
        "liquid_hydrocarbons",
        "LHC",
        FluidMarkerShape.TRIANGLE_UP,
        "#ca8a04",
        "жидкие УВ",
        "сұйық КС",
        "liquid HC",
        100,
    ),
    FluidMarkerSpec(
        "indeterminate",
        "?",
        FluidMarkerShape.CROSS,
        "#64748b",
        "неопред.",
        "анықталмаған",
        "indeterminate",
        110,
    ),
)
_BY_CATEGORY = {item.category: item for item in _SPECS}

_EXACT_CATEGORY = {
    "probable_gas": "gas",
    "very_light_dry_gas": "gas",
    "light_dry_gas": "gas",
    "productive_gas_increasing_wetness": "gas",
    "gas_increasing_wetness": "gas",
    "wet_gas_or_gas_condensate": "gas_condensate",
    "gas_condensate_or_high_api_oil": "gas_condensate_or_light_oil",
    "light_oil_high_gor": "light_oil",
    "productive_oil_decreasing_gravity": "oil",
    "poor_low_gravity_oil": "heavy_oil",
    "heavy_or_residual_oil": "heavy_oil",
    "probable_liquid_hydrocarbons": "liquid_hydrocarbons",
    "indeterminate": "indeterminate",
    "insufficient_data": "indeterminate",
    "opus_oxidized_residual_oil": "heavy_oil",
    "opus_oil": "oil",
    "opus_combustible_gas": "gas",
    "opus_water_dissolved_gas": "dissolved_gas",
    "opus_gas_condensate": "gas_condensate",
    "opus_gassy_oil": "gassy_oil",
    "opus_gas_condensate_or_gassy_oil": "gas_condensate_or_gassy_oil",
    "opus_no_consensus": "indeterminate",
    "opus_gasomer_oxidized_residual_oil": "heavy_oil",
    "opus_gasomer_oil": "oil",
    "opus_gasomer_combustible_gas": "gas",
    "opus_gasomer_water_dissolved_gas": "dissolved_gas",
    "opus_gasomer_gas_condensate": "gas_condensate",
    "opus_gasomer_gassy_oil": "gassy_oil",
    "opus_gasomer_undefined": "indeterminate",
    "opus_gasomer_no_consensus": "indeterminate",
}
_AMBIGUOUS_PREFIX = "opus_gasomer_ambiguous__"
_FALLBACK_PREFIX = "opus_fallback__"


def all_fluid_marker_specs() -> tuple[FluidMarkerSpec, ...]:
    return _SPECS


def fluid_marker_spec(fluid_hypothesis: str) -> FluidMarkerSpec:
    key = str(fluid_hypothesis or "").strip().casefold()
    if key.startswith(_AMBIGUOUS_PREFIX):
        return _BY_CATEGORY["indeterminate"]
    if key.startswith(_FALLBACK_PREFIX):
        key = key[len(_FALLBACK_PREFIX) :]

    category = _EXACT_CATEGORY.get(key)
    if category is None:
        category = _infer_category(key)
    return _BY_CATEGORY[category]


def fluid_marker_legend_specs(
    hypotheses: tuple[str, ...] | list[str],
) -> tuple[FluidMarkerSpec, ...]:
    by_category = {
        spec.category: spec
        for spec in (fluid_marker_spec(item) for item in hypotheses)
    }
    return tuple(sorted(by_category.values(), key=lambda item: item.order))


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


def draw_fluid_marker(
    painter: QPainter,
    center: QPointF,
    spec: FluidMarkerSpec,
    *,
    size: float,
) -> None:
    """Draw one colour + shape encoded marker; callers may add the short code separately."""

    size = max(2.5, float(size))
    half = size / 2.0
    color = QColor(spec.color)
    painter.save()
    painter.setPen(QPen(color, max(0.8, size * 0.13)))
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


def _infer_category(key: str) -> str:
    if not key:
        return "indeterminate"
    if any(token in key for token in ("ambiguous", "no_consensus", "indeterminate", "undefined", "insufficient")):
        return "indeterminate"
    if "gas_condensate_or_gassy_oil" in key:
        return "gas_condensate_or_gassy_oil"
    if "gas_condensate_or_high_api_oil" in key:
        return "gas_condensate_or_light_oil"
    if "water_dissolved_gas" in key:
        return "dissolved_gas"
    if "gas_condensate" in key or "wet_gas" in key:
        return "gas_condensate"
    if "gassy_oil" in key:
        return "gassy_oil"
    if "light_oil" in key:
        return "light_oil"
    if any(token in key for token in ("heavy", "residual", "oxidized", "low_gravity_oil")):
        return "heavy_oil"
    if "liquid_hydrocarbons" in key:
        return "liquid_hydrocarbons"
    if "oil" in key:
        return "oil"
    if any(token in key for token in ("probable_gas", "dry_gas", "combustible_gas", "productive_gas", "gas_increasing")):
        return "gas"
    return "indeterminate"


__all__ = [
    "FluidMarkerShape",
    "FluidMarkerSpec",
    "all_fluid_marker_specs",
    "draw_fluid_marker",
    "fluid_marker_legend_specs",
    "fluid_marker_spec",
    "marker_lanes",
]
