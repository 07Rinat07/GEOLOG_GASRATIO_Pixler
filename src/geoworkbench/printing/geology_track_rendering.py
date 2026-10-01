from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QLineF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from geoworkbench.printing.lba_visuals import (
    normalized_lba_intensity,
    resolve_lba_type_style,
)
from geoworkbench.services.lba_standard import lba_color_code, lba_standard_group
from geoworkbench.tablet.lithology_patterns import masterlog_lithology_brush


class LithotypeVisual(Protocol):
    color: str
    pattern_key: str


class CuttingsComponentVisual(Protocol):
    lithotype_id: str
    percentage: float


class CuttingsSampleVisual(Protocol):
    top_depth: float
    bottom_depth: float
    components: Sequence[CuttingsComponentVisual]
    lba_group: int | None
    lba_type_id: str | None
    lba_intensity: int | None
    lba_color: str | None
    lba_distribution: str | None
    lba_cut: str | None
    lba_description: str | None


@dataclass(frozen=True, slots=True)
class FrozenCuttingsComponent:
    lithotype_id: str
    percentage: float


@dataclass(frozen=True, slots=True)
class FrozenCuttingsSample:
    sample_id: str
    top_depth: float
    bottom_depth: float
    components: tuple[FrozenCuttingsComponent, ...]
    lba_group: int | None = None
    lba_type_id: str | None = None
    lba_intensity: int | None = None
    lba_color: str | None = None
    lba_distribution: str | None = None
    lba_cut: str | None = None
    lba_description: str | None = None


def paint_cuttings_track(
    painter: QPainter,
    rect: QRectF,
    samples: Sequence[CuttingsSampleVisual],
    depth_range: tuple[float, float],
    lithotypes: Mapping[str, LithotypeVisual],
    *,
    draw_frame: bool = True,
) -> None:
    top, bottom = depth_range
    if bottom <= top or rect.width() <= 0.0 or rect.height() <= 0.0:
        return
    painter.save()
    painter.setClipRect(rect)
    if draw_frame:
        painter.setPen(QPen(QColor("#94a3b8"), 0.25))
        painter.drawRect(rect)
    for sample in samples:
        if sample.bottom_depth < top or sample.top_depth > bottom:
            continue
        visible_top = max(top, sample.top_depth)
        visible_bottom = min(bottom, sample.bottom_depth)
        if visible_bottom <= visible_top:
            continue
        y_top = rect.top() + (visible_top - top) / (bottom - top) * rect.height()
        y_bottom = rect.top() + (visible_bottom - top) / (bottom - top) * rect.height()
        x = rect.left()
        remaining = rect.right()
        for component in sample.components:
            percentage = min(100.0, max(0.0, float(component.percentage)))
            if percentage <= 0.0:
                continue
            width = rect.width() * percentage / 100.0
            width = min(width, max(0.0, remaining - x))
            definition = lithotypes.get(component.lithotype_id)
            color = definition.color if definition is not None else "#b0b0b0"
            pattern = definition.pattern_key if definition is not None else "solid"
            component_rect = QRectF(x, y_top, width, max(0.1, y_bottom - y_top))
            painter.fillRect(
                component_rect,
                masterlog_lithology_brush(painter, color, pattern),
            )
            painter.setPen(QPen(QColor("#334155"), 0.2))
            painter.drawRect(component_rect)
            x += width
            if x >= remaining:
                break
    painter.restore()


def paint_lba_intensity_symbol(
    painter: QPainter,
    center_x: float,
    center_y: float,
    diameter: float,
    color: QColor,
    intensity: int | None,
) -> None:
    resolved = normalized_lba_intensity(intensity)
    diameter = max(1.2, float(diameter))
    radius = diameter / 2.0
    symbol_rect = QRectF(center_x - radius, center_y - radius, diameter, diameter)
    painter.save()
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if resolved == 1:
        dot = max(0.8, diameter * 0.24)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(
            QRectF(center_x - dot / 2.0, center_y - dot / 2.0, dot, dot)
        )
    elif resolved == 2:
        painter.setPen(QPen(color, max(0.25, diameter * 0.07), Qt.PenStyle.DashLine))
        painter.drawEllipse(symbol_rect)
    elif resolved == 3:
        painter.setPen(QPen(color, max(0.25, diameter * 0.07)))
        painter.drawEllipse(symbol_rect)
    elif resolved == 4:
        painter.setPen(QPen(color, max(0.5, diameter * 0.16)))
        painter.drawEllipse(symbol_rect.adjusted(0.2, 0.2, -0.2, -0.2))
    elif resolved == 5:
        painter.setPen(QPen(color.darker(130), max(0.2, diameter * 0.05)))
        painter.setBrush(color)
        painter.drawEllipse(symbol_rect)
    else:
        painter.setPen(QPen(color, max(0.25, diameter * 0.07)))
        painter.drawEllipse(symbol_rect)
        painter.drawLine(symbol_rect.topLeft(), symbol_rect.bottomRight())
        painter.drawLine(symbol_rect.topRight(), symbol_rect.bottomLeft())
    painter.restore()


def paint_lba_track(
    painter: QPainter,
    rect: QRectF,
    samples: Sequence[CuttingsSampleVisual],
    depth_range: tuple[float, float],
    *,
    draw_frame: bool = True,
) -> None:
    top, bottom = depth_range
    if bottom <= top or rect.width() <= 0.0 or rect.height() <= 0.0:
        return
    painter.save()
    painter.setClipRect(rect)
    if draw_frame:
        painter.setPen(QPen(QColor("#94a3b8"), 0.25))
        painter.drawRect(rect)
    for sample in samples:
        if sample.bottom_depth < top or sample.top_depth > bottom:
            continue
        color_code = lba_color_code(sample.lba_color)
        has_lba = any(
            value not in (None, "")
            for value in (
                sample.lba_group,
                sample.lba_type_id,
                sample.lba_intensity,
                color_code,
                sample.lba_distribution,
                sample.lba_cut,
                sample.lba_description,
            )
        )
        if not has_lba:
            continue
        visible_top = max(top, sample.top_depth)
        visible_bottom = min(bottom, sample.bottom_depth)
        if visible_bottom <= visible_top:
            continue
        y_top = rect.top() + (visible_top - top) / (bottom - top) * rect.height()
        y_bottom = rect.top() + (visible_bottom - top) / (bottom - top) * rect.height()
        sample_rect = QRectF(
            rect.left(),
            y_top,
            rect.width(),
            max(0.2, y_bottom - y_top),
        )
        painter.setPen(QPen(QColor("#cbd5e1"), 0.15))
        painter.drawRect(sample_rect)
        style = resolve_lba_type_style(sample.lba_type_id)
        standard_group = lba_standard_group(sample.lba_group)
        symbol_color = QColor(
            standard_group.display_color if standard_group is not None else style.color
        )
        diameter = min(
            max(2.0, sample_rect.height() * 0.72),
            max(2.0, sample_rect.width() * 0.60),
            7.0,
        )
        paint_lba_intensity_symbol(
            painter,
            sample_rect.center().x(),
            sample_rect.center().y(),
            diameter,
            symbol_color,
            sample.lba_intensity,
        )
    painter.restore()


__all__ = [
    "FrozenCuttingsComponent",
    "FrozenCuttingsSample",
    "paint_cuttings_track",
    "paint_lba_intensity_symbol",
    "paint_lba_track",
]
