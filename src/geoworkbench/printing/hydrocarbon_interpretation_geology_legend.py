from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Literal

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from geoworkbench.printing.geology_track_rendering import paint_lba_intensity_symbol
from geoworkbench.printing.hydrocarbon_interpretation_geology import (
    InterpretationGeologySnapshot,
)
from geoworkbench.printing.lba_visuals import (
    UNKNOWN_LBA_STYLE,
    lba_intensity_name,
    normalized_lba_intensity,
    resolve_lba_type_style,
)
from geoworkbench.printing.unicode_support import print_font
from geoworkbench.services.lba_standard import (
    LBA_STANDARD_GROUPS,
    lba_color_code,
    lba_standard_group,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.tablet.lithology_patterns import masterlog_lithology_brush


LegendKind = Literal["lithology", "lba-type", "lba-intensity", "lba-color"]


@dataclass(frozen=True, slots=True)
class GeologyLegendItem:
    kind: LegendKind
    key: str
    code: str
    label: str
    color: str = "#64748b"
    pattern_key: str = "solid"
    intensity: int | None = None


@dataclass(frozen=True, slots=True)
class InterpretationGeologyLegend:
    items: tuple[GeologyLegendItem, ...]

    @property
    def empty(self) -> bool:
        return not self.items


def build_interpretation_geology_legend(
    geology: InterpretationGeologySnapshot | None,
    top_depth: float,
    bottom_depth: float,
    language: AppLanguage,
    *,
    include_cuttings: bool = True,
    include_lba: bool = True,
) -> InterpretationGeologyLegend:
    if geology is None or bottom_depth <= top_depth:
        return InterpretationGeologyLegend(())

    visible = tuple(
        sample
        for sample in geology.samples
        if sample.bottom_depth >= top_depth and sample.top_depth <= bottom_depth
    )
    if not visible:
        return InterpretationGeologyLegend(())

    items: list[GeologyLegendItem] = []
    used_keys: set[tuple[LegendKind, str]] = set()
    lithotypes = geology.lithotype_map

    for sample in visible if include_cuttings else ():
        for component in sample.components:
            if float(component.percentage) <= 0.0:
                continue
            legend_key: tuple[LegendKind, str] = (
                "lithology",
                component.lithotype_id,
            )
            if legend_key in used_keys:
                continue
            used_keys.add(legend_key)
            lithotype = lithotypes.get(component.lithotype_id)
            if lithotype is None:
                items.append(
                    GeologyLegendItem(
                        "lithology",
                        component.lithotype_id,
                        "?",
                        component.lithotype_id,
                        "#b0b0b0",
                        "solid",
                    )
                )
                continue
            items.append(
                GeologyLegendItem(
                    "lithology",
                    lithotype.lithotype_id,
                    lithotype.code or lithotype.lithotype_id,
                    lithotype.localized_name(language.value),
                    lithotype.color,
                    lithotype.pattern_key,
                )
            )

    for sample in visible if include_lba else ():
        has_lba = any(
            value not in (None, "")
            for value in (
                sample.lba_group,
                sample.lba_type_id,
                sample.lba_intensity,
                sample.lba_color,
                sample.lba_distribution,
                sample.lba_cut,
                sample.lba_description,
            )
        )
        if not has_lba:
            continue
        standard_group = lba_standard_group(sample.lba_group)
        style = resolve_lba_type_style(sample.lba_type_id)
        if sample.lba_type_id:
            type_code = style.code
            type_label = style.localized_name(language)
            type_key = style.type_id
            type_color = (
                standard_group.display_color
                if standard_group is not None
                else style.color
            )
        elif standard_group is not None:
            type_code = standard_group.code
            type_label = standard_group.localized_type_name(language)
            type_key = standard_group.type_id
            type_color = standard_group.display_color
        else:
            type_code = UNKNOWN_LBA_STYLE.code
            type_label = UNKNOWN_LBA_STYLE.localized_name(language)
            type_key = UNKNOWN_LBA_STYLE.type_id
            type_color = UNKNOWN_LBA_STYLE.color

        if type_key:
            legend_key = ("lba-type", type_key)
            if legend_key not in used_keys:
                used_keys.add(legend_key)
                items.append(
                    GeologyLegendItem(
                        "lba-type",
                        type_key,
                        type_code,
                        type_label,
                        type_color,
                        intensity=3 if type_key != UNKNOWN_LBA_STYLE.type_id else None,
                    )
                )

        intensity = normalized_lba_intensity(sample.lba_intensity)
        if intensity is not None:
            intensity_key = str(intensity)
            legend_key = ("lba-intensity", intensity_key)
            if legend_key not in used_keys:
                used_keys.add(legend_key)
                items.append(
                    GeologyLegendItem(
                        "lba-intensity",
                        intensity_key,
                        str(intensity),
                        lba_intensity_name(intensity, language),
                        "#334155",
                        intensity=intensity,
                    )
                )

        color_code = lba_color_code(sample.lba_color)
        if color_code:
            legend_key = ("lba-color", color_code)
            if legend_key not in used_keys:
                used_keys.add(legend_key)
                items.append(
                    GeologyLegendItem(
                        "lba-color",
                        color_code,
                        color_code,
                        _lba_color_name(color_code, language),
                        "#64748b",
                    )
                )

    return InterpretationGeologyLegend(tuple(items))


def geology_legend_height(
    width: float,
    legend: InterpretationGeologyLegend,
    *,
    compact: bool = False,
) -> float:
    if legend.empty or width <= 0.0:
        return 0.0
    columns = _legend_columns(width, compact=compact)
    rows = ceil(len(legend.items) / columns)
    row_height = 18.0 if compact else 22.0
    title_height = 0.0 if compact else 16.0
    return 6.0 + title_height + rows * row_height + 4.0


def paint_geology_legend(
    painter: QPainter,
    rect: QRectF,
    legend: InterpretationGeologyLegend,
    language: AppLanguage,
    *,
    compact: bool = False,
) -> None:
    if legend.empty or rect.width() <= 0.0 or rect.height() <= 0.0:
        return

    painter.save()
    painter.setClipRect(rect)
    painter.fillRect(rect, QColor("#ffffff"))
    painter.setPen(QPen(QColor("#cbd5e1"), 0.55))
    painter.drawRect(rect)

    top = rect.top() + 3.0
    if not compact:
        title = _labels(language)["title"]
        font = print_font(7.2, text=title)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#172033"))
        painter.drawText(
            QRectF(rect.left() + 4.0, top, rect.width() - 8.0, 13.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            title,
        )
        top += 16.0

    columns = _legend_columns(rect.width(), compact=compact)
    cell_width = rect.width() / columns
    row_height = 18.0 if compact else 22.0
    font_size = 6.2 if compact else 6.6

    for index, item in enumerate(legend.items):
        row = index // columns
        column = index % columns
        cell = QRectF(
            rect.left() + column * cell_width,
            top + row * row_height,
            cell_width,
            row_height,
        )
        _paint_legend_item(
            painter,
            cell,
            item,
            font_size=font_size,
            compact=compact,
        )

    painter.restore()


def _paint_legend_item(
    painter: QPainter,
    rect: QRectF,
    item: GeologyLegendItem,
    *,
    font_size: float,
    compact: bool,
) -> None:
    marker_width = 20.0
    marker = QRectF(
        rect.left() + 3.0,
        rect.center().y() - 5.0,
        marker_width - 5.0,
        10.0,
    )

    if item.kind == "lithology":
        painter.fillRect(
            marker,
            masterlog_lithology_brush(
                painter,
                item.color,
                item.pattern_key,
            ),
        )
        painter.setPen(QPen(QColor("#334155"), 0.45))
        painter.drawRect(marker)
    elif item.kind in {"lba-type", "lba-intensity"}:
        paint_lba_intensity_symbol(
            painter,
            marker.center().x(),
            marker.center().y(),
            8.0,
            QColor(item.color),
            item.intensity,
        )
    else:
        painter.setPen(QPen(QColor("#64748b"), 0.45))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(marker, 2.0, 2.0)
        painter.setFont(print_font(5.7, text=item.code))
        painter.setPen(QColor("#172033"))
        painter.drawText(marker, Qt.AlignmentFlag.AlignCenter, item.code)

    text = item.code if compact else (
        f"{item.code} — {item.label}" if item.code else item.label
    )
    painter.setFont(print_font(font_size, text=text))
    painter.setPen(QColor("#172033"))
    painter.drawText(
        QRectF(
            rect.left() + marker_width + 2.0,
            rect.top() + 1.0,
            rect.width() - marker_width - 5.0,
            rect.height() - 2.0,
        ),
        Qt.AlignmentFlag.AlignLeft
        | Qt.AlignmentFlag.AlignVCenter
        | Qt.TextFlag.TextWordWrap,
        text,
    )


def _legend_columns(width: float, *, compact: bool) -> int:
    target = 90.0 if compact else 120.0
    return max(1, min(8, int(width // target)))


def _lba_color_name(code: str, language: AppLanguage) -> str:
    for group in LBA_STANDARD_GROUPS:
        for color in group.colors:
            if color.code == code:
                return color.localized_name(language)
    return _labels(language)["fluorescence"]


def _labels(language: AppLanguage) -> dict[str, str]:
    return {
        AppLanguage.RU: {
            "title": "Геологическая легенда",
            "fluorescence": "флуоресценция",
        },
        AppLanguage.KK: {
            "title": "Геологиялық легенда",
            "fluorescence": "флуоресценция",
        },
        AppLanguage.EN: {
            "title": "Geology legend",
            "fluorescence": "fluorescence",
        },
    }[language]


__all__ = [
    "GeologyLegendItem",
    "InterpretationGeologyLegend",
    "build_interpretation_geology_legend",
    "geology_legend_height",
    "paint_geology_legend",
]
