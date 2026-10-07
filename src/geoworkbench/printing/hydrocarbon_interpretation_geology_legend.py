from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPaintDevice, QPagedPaintDevice, QPainter, QPen

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
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.services.lba_standard import (
    LBA_ADDITIONAL_COLORS,
    LBA_STANDARD_GROUPS,
    lba_color_code,
    lba_standard_group,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.tablet.lithology_patterns import masterlog_lithology_brush


LegendKind = Literal["lithology", "lba-type", "lba-intensity", "lba-color", "reference"]
_MAX_FULL_ROW_HEIGHT = 64.0
_FULL_LEGEND_OVERHEAD = 26.0
_SECTION_HEIGHT = 14.0
_LEGEND_KINDS: tuple[LegendKind, ...] = (
    "lithology", "lba-type", "lba-intensity", "lba-color", "reference",
)


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

    type_order = {group.type_id: index for index, group in enumerate(LBA_STANDARD_GROUPS)}
    return InterpretationGeologyLegend(tuple(sorted(
        items,
        key=lambda item: (
            _LEGEND_KINDS.index(item.kind),
            type_order.get(item.key, len(type_order)) if item.kind == "lba-type" else 0,
            item.code.casefold(),
            item.key,
        ),
    )))


def geology_legend_height(
    width: float,
    legend: InterpretationGeologyLegend,
    *,
    compact: bool = False,
    paint_device: QPaintDevice | None = None,
) -> float:
    if legend.empty or width <= 0.0:
        return 0.0
    title_height = _legend_heading_height(width, "title", paint_device)
    row_heights = _legend_row_heights(
        width, legend, compact=compact, paint_device=paint_device,
    )
    section_height = sum(
        _legend_heading_height(width, kind, paint_device)
        for kind in {item.kind for item in legend.items}
    )
    return 6.0 + title_height + section_height + sum(row_heights) + 4.0


def paginate_geology_legend(
    width: float,
    legend: InterpretationGeologyLegend,
    maximum_height: float,
    *,
    compact: bool = False,
    paint_device: QPaintDevice | None = None,
) -> tuple[InterpretationGeologyLegend, ...]:
    """Keep every symbol, splitting the full legend at complete row boundaries."""
    if legend.empty:
        return ()
    if width <= 0.0 or maximum_height < (
        _FULL_LEGEND_OVERHEAD + _SECTION_HEIGHT + _MAX_FULL_ROW_HEIGHT
    ):
        raise ValueError("Geology legend page must fit a complete bounded row")
    pages: list[InterpretationGeologyLegend] = []
    current: tuple[GeologyLegendItem, ...] = ()
    for row in _legend_rows(width, legend):
        candidate = InterpretationGeologyLegend((*current, *row))
        if current and geology_legend_height(
            width, candidate, compact=compact, paint_device=paint_device,
        ) > maximum_height:
            pages.append(InterpretationGeologyLegend(current))
            current = ()
        current = (*current, *row)
        if geology_legend_height(
            width,
            InterpretationGeologyLegend(current),
            compact=compact,
            paint_device=paint_device,
        ) > maximum_height:
            raise ValueError("Geology legend page must fit a complete row and its heading")
    pages.append(InterpretationGeologyLegend(current))
    return tuple(pages)


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

    visual = modern_oilfield_report_profile()
    painter.save()
    painter.setClipRect(rect)
    painter.fillRect(rect, QColor(visual.palette.page))
    painter.setPen(QPen(QColor(visual.palette.border), visual.layout.thin_rule_pt))
    painter.drawRect(rect)

    top = rect.top() + 3.0
    if legend.items:
        title = _labels(language)["title"]
        font = _legend_font(visual.typography.caption_pt, title, painter.device())
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(visual.palette.text))
        title_height = _legend_heading_height(rect.width(), "title", painter.device())
        painter.drawText(
            QRectF(rect.left() + 4.0, top, rect.width() - 8.0, title_height),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
            title,
        )
        top += title_height

    columns = _legend_columns(rect.width())
    cell_width = rect.width() / columns
    row_heights = _legend_row_heights(
        rect.width(),
        legend,
        compact=compact,
        paint_device=painter.device(),
    )
    font_size = _legend_body_size(compact)
    previous_kind: LegendKind | None = None
    for row, height in zip(
        _legend_rows(rect.width(), legend), row_heights, strict=True,
    ):
        kind = row[0].kind
        if kind != previous_kind:
            title = _labels(language)[kind]
            font = _legend_font(visual.typography.caption_pt, title, painter.device())
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor(visual.palette.text_secondary))
            section_height = _legend_heading_height(rect.width(), kind, painter.device())
            painter.drawText(
                QRectF(rect.left() + 4.0, top, rect.width() - 8.0, section_height),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                | Qt.TextFlag.TextWordWrap,
                title,
            )
            top += section_height
        for column, item in enumerate(row):
            _paint_legend_item(
                painter,
                QRectF(rect.left() + column * cell_width, top, cell_width, height),
                item,
                font_size=font_size,
                compact=compact,
            )
        top += height
        previous_kind = kind

    painter.restore()


def _paint_legend_item(
    painter: QPainter,
    rect: QRectF,
    item: GeologyLegendItem,
    *,
    font_size: float,
    compact: bool,
) -> None:
    visual = modern_oilfield_report_profile()
    marker_width = 0.0 if item.kind == "reference" else 20.0
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
        painter.setPen(QPen(QColor(visual.palette.border_strong), visual.layout.thin_rule_pt / 2.0))
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
    elif item.kind != "reference":
        painter.setPen(QPen(QColor(visual.palette.border), visual.layout.thin_rule_pt / 2.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(marker, 2.0, 2.0)
        painter.setFont(_legend_font(max(5.0, visual.typography.caption_pt - 1.5), item.code, painter.device()))
        painter.setPen(QColor(visual.palette.text))
        painter.drawText(marker, Qt.AlignmentFlag.AlignCenter, item.code)

    text = _legend_item_text(item, compact=compact)
    font = _legend_font(font_size, text, painter.device())
    painter.setFont(font)
    painter.setPen(QColor(visual.palette.text))
    text_rect = QRectF(
        rect.left() + marker_width + 2.0,
        rect.top() + 1.0,
        max(1.0, rect.width() - marker_width - 5.0),
        rect.height() - 2.0,
    )
    metrics = QFontMetricsF(font, painter.device())
    text = _fit_legend_text(text, metrics, text_rect.width(), text_rect.height())
    painter.drawText(
        text_rect,
        Qt.AlignmentFlag.AlignLeft
        | Qt.AlignmentFlag.AlignVCenter
        | Qt.TextFlag.TextWordWrap,
        text,
    )


def _legend_item_text(
    item: GeologyLegendItem,
    *,
    compact: bool,
) -> str:
    return f"{item.code} — {item.label}" if item.code else item.label


def _legend_rows(
    width: float,
    legend: InterpretationGeologyLegend,
) -> tuple[tuple[GeologyLegendItem, ...], ...]:
    columns = _legend_columns(width)
    rows: list[tuple[GeologyLegendItem, ...]] = []
    for kind in _LEGEND_KINDS:
        items = tuple(item for item in legend.items if item.kind == kind)
        rows.extend(items[start:start + columns] for start in range(0, len(items), columns))
    return tuple(rows)


def _legend_row_heights(
    width: float,
    legend: InterpretationGeologyLegend,
    *,
    compact: bool,
    paint_device: QPaintDevice | None = None,
) -> tuple[float, ...]:
    columns = _legend_columns(width)
    cell_width = width / columns
    text_width = max(1.0, cell_width - 25.0)
    heights: list[float] = []
    flags = (
        Qt.AlignmentFlag.AlignLeft
        | Qt.AlignmentFlag.AlignVCenter
        | Qt.TextFlag.TextWordWrap
    )
    for row_items in _legend_rows(width, legend):
        measured = 0.0
        for item in row_items:
            text = _legend_item_text(item, compact=False)
            font = _legend_font(_legend_body_size(compact), text, paint_device)
            metrics = (
                QFontMetricsF(font, paint_device)
                if paint_device is not None else QFontMetricsF(font)
            )
            bounds = metrics.boundingRect(
                QRectF(0.0, 0.0, text_width, 1_000.0),
                int(flags),
                text,
            )
            measured = max(measured, bounds.height())
        minimum_height = 17.0 if compact else 22.0
        maximum_height = 42.0 if compact else _MAX_FULL_ROW_HEIGHT
        heights.append(min(maximum_height, max(minimum_height, measured + 4.0)))
    return tuple(heights)


def _fit_legend_text(
    text: str,
    metrics: QFontMetricsF,
    width: float,
    height: float,
) -> str:
    """Make exceptional labels visibly abbreviated rather than silently clipped."""
    flags = int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft)
    bounds = QRectF(0.0, 0.0, width, height)

    def fits(value: str) -> bool:
        measured = metrics.boundingRect(bounds, flags, value)
        return measured.height() <= height and measured.width() <= width

    if fits(text):
        return text
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if fits(text[:middle].rstrip() + "…"):
            low = middle
        else:
            high = middle - 1
    return text[:low].rstrip() + "…"


def _legend_columns(width: float) -> int:
    # Both modes share a readable column width; caption size and row bounds
    # make compact rows shorter without causing extra horizontal wrapping.
    typography = modern_oilfield_report_profile().typography
    target = 16.0 * max(typography.table_pt, typography.caption_pt)
    return max(1, min(8, int(width // target)))


def _legend_heading_height(
    width: float,
    key: str,
    paint_device: QPaintDevice | None,
) -> float:
    height = 16.0 if key == "title" else _SECTION_HEIGHT
    for language in AppLanguage:
        text = _labels(language)[key]
        font = _legend_font(modern_oilfield_report_profile().typography.caption_pt, text, paint_device)
        font.setBold(True)
        metrics = QFontMetricsF(font, paint_device) if paint_device else QFontMetricsF(font)
        bounds = metrics.boundingRect(
            QRectF(0.0, 0.0, max(1.0, width - 8.0), 10_000.0),
            int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft), text,
        )
        height = max(height, bounds.height() + 3.0)
    return height


def _legend_body_size(compact: bool) -> float:
    typography = modern_oilfield_report_profile().typography
    return typography.caption_pt if compact else typography.table_pt


def _legend_font(points: float, text: str, device: QPaintDevice | None) -> QFont:
    font = print_font(points, text=text)
    # Paged renderers scale point coordinates to device pixels. Compensate font
    # sizing once; PNG painters retain their existing pixel-coordinate contract.
    if isinstance(device, QPagedPaintDevice):
        font.setPointSizeF(points * 72.0 / device.logicalDpiY())
    return font


def _lba_color_name(code: str, language: AppLanguage) -> str:
    for group in LBA_STANDARD_GROUPS:
        for color in group.colors:
            if color.code == code:
                return color.localized_name(language)
    for color in LBA_ADDITIONAL_COLORS:
        if color.code == code:
            return color.localized_name(language)
    return _labels(language)["unknown-color"]


def _labels(language: AppLanguage) -> dict[str, str]:
    return {
        AppLanguage.RU: {
            "title": "Геологическая легенда",
            "fluorescence": "флуоресценция",
            "lithology": "Литология",
            "lba-type": "ЛБА: тип битумоида",
            "lba-intensity": "ЛБА: интенсивность",
            "lba-color": "ЛБА: цвет флуоресценции",
            "unknown-color": "неизвестный цвет",
            "reference": "Справка",
        },
        AppLanguage.KK: {
            "title": "Геологиялық легенда",
            "fluorescence": "флуоресценция",
            "lithology": "Литология",
            "lba-type": "ЛБА: битумоид түрі",
            "lba-intensity": "ЛБА: қарқындылық",
            "lba-color": "ЛБА: флуоресценция түсі",
            "unknown-color": "анықталмаған түс",
            "reference": "Анықтама",
        },
        AppLanguage.EN: {
            "title": "Geology legend",
            "fluorescence": "fluorescence",
            "lithology": "Lithology",
            "lba-type": "LBA: bitumen type",
            "lba-intensity": "LBA: intensity",
            "lba-color": "LBA: fluorescence colour",
            "unknown-color": "unrecognized colour",
            "reference": "Reference",
        },
    }[language]


__all__ = [
    "GeologyLegendItem",
    "InterpretationGeologyLegend",
    "build_interpretation_geology_legend",
    "geology_legend_height",
    "paint_geology_legend",
    "paginate_geology_legend",
]
