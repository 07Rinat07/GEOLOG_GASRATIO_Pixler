"""Shared effective-context geometry and monochrome-safe print presentation."""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QPagedPaintDevice, QPaintDevice, QPainter, QPen

from geoworkbench.domain.gas_context_events import (
    GasContextEvent, GasContextRegistry, InterpretationImpact,
)
from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.printing.interpretation_track_headings import paint_track_heading, track_heading_height
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.printing.unicode_support import print_font
from geoworkbench.services.gas_context_report_labels import gas_context_event_label, gas_context_event_code
from geoworkbench.services.localization import AppLanguage


_STYLES = {
    InterpretationImpact.TECHNOLOGICAL_GAS: Qt.PenStyle.DashLine,
    InterpretationImpact.FORMATION_GAS: Qt.PenStyle.SolidLine,
    InterpretationImpact.REVIEW_REQUIRED: Qt.PenStyle.DotLine,
}


@dataclass(frozen=True, slots=True)
class GasContextSegment:
    event: GasContextEvent
    top_depth: float
    bottom_depth: float


def _font_for_device(device: QPaintDevice, size: float, text: str):
    font = print_font(size, text=text)
    font.setPointSizeF(size * 72.0 / device.logicalDpiY())
    return font


def context_title(language: AppLanguage) -> str:
    return {
        AppLanguage.RU: "Газовый контекст",
        AppLanguage.KK: "Газ контексті",
        AppLanguage.EN: "Gas context",
    }[language]


def context_heading(language: AppLanguage) -> str:
    return context_title(language).replace(" ", "\n", 1)


def _context_heading_font_size(device: QPaintDevice, scale: float) -> float:
    size = modern_oilfield_report_profile().typography.table_pt * scale
    # Raster context tracks retain their existing DPI-adjusted pixel contract.
    # Paged tracks delegate physical-point compensation to the shared adapter.
    return size if isinstance(device, QPagedPaintDevice) else size * 72.0 / device.logicalDpiY()


def context_track_heading_height(
    language: AppLanguage, width: float, device: QPaintDevice, *, scale: float = 1.0,
) -> float:
    return track_heading_height(
        context_heading(language), width, _context_heading_font_size(device, scale), device,
        point_coordinates=isinstance(device, QPagedPaintDevice),
    )


def context_label(event: GasContextEvent, language: AppLanguage) -> str:
    return gas_context_event_label(event.event_type, language)


def context_code(event: GasContextEvent) -> str:
    return gas_context_event_code(event.event_type)


def context_segments(
    events: tuple[GasContextEvent, ...], top: float, bottom: float,
) -> tuple[GasContextSegment, ...]:
    """Reuse registry priority; retain actual depths, including point events."""
    if bottom <= top:
        return ()
    visible = tuple(e for e in events if e.confirmed
                    and e.effective_impact is not InterpretationImpact.EXCLUDE_GEOLOGICAL
                    and e.top_depth <= bottom and e.bottom_depth >= top)
    registry = GasContextRegistry(visible)
    boundaries = sorted({top, bottom, *(max(top, e.top_depth) for e in visible),
                         *(min(bottom, e.bottom_depth) for e in visible)})
    segments: list[GasContextSegment] = []
    for low, high in zip(boundaries, boundaries[1:]):
        event = registry.resolve_at_depth((low + high) / 2.0)
        if event is None:
            continue
        if segments and segments[-1].event == event and segments[-1].bottom_depth == low:
            previous = segments.pop()
            low = previous.top_depth
        segments.append(GasContextSegment(event, low, high))
    for event in visible:
        if event.top_depth == event.bottom_depth and registry.resolve_at_depth(event.top_depth) == event:
            segments.append(GasContextSegment(event, event.top_depth, event.bottom_depth))
    return tuple(sorted(segments, key=lambda s: (s.top_depth, s.bottom_depth, s.event.event_id)))


def segment_events(segments: tuple[GasContextSegment, ...]) -> tuple[GasContextEvent, ...]:
    return tuple({s.event.event_id: s.event for s in segments}.values())


def context_legend_rows(segments: tuple[GasContextSegment, ...], language: AppLanguage, unit: str) -> tuple[str, ...]:
    return tuple(f"{context_code(e)} — {context_label(e, language)}; ID: {e.event_id}; "
                 f"{e.top_depth:g}–{e.bottom_depth:g} {unit}"
                 for e in segment_events(segments))


def paint_context_track(
    painter: QPainter, rect: QRectF, events: tuple[GasContextEvent, ...],
    top: float, bottom: float, language: AppLanguage, *, header_height: float,
    scale: float = 1.0,
) -> None:
    visual = modern_oilfield_report_profile()
    painter.save()
    try:
        painter.fillRect(rect, QColor(visual.palette.page))
        painter.setPen(QPen(QColor(visual.palette.border_strong), 0.7 * scale))
        painter.drawRect(rect)
        paint_track_heading(painter, QRectF(rect.left(), rect.top() - header_height + 2 * scale,
                            rect.width(), header_height - 20 * scale), context_heading(language),
                            _context_heading_font_size(painter.device(), scale),
                            point_coordinates=isinstance(painter.device(), QPagedPaintDevice))
        painter.setClipRect(rect, Qt.ClipOperation.IntersectClip)
        for segment in context_segments(events, top, bottom):
            y1 = rect.top() + (segment.top_depth - top) / (bottom - top) * rect.height()
            y2 = rect.top() + (segment.bottom_depth - top) / (bottom - top) * rect.height()
            band = QRectF(rect.left() + scale, y1, rect.width() - 2 * scale, y2 - y1)
            painter.fillRect(band, QColor(visual.palette.table_alt))
            painter.setPen(QPen(QColor(visual.palette.text), 0.8 * scale,
                                _STYLES[segment.event.effective_impact]))
            painter.drawRect(band)
            # Tiny intervals retain their exact position and full legend entry;
            # text is clipped to its own band instead of colliding with neighbours.
            if band.height() >= 10 * scale:
                code = context_code(segment.event)
                painter.setFont(_font_for_device(painter.device(), 6.0 * scale, code))
                painter.setPen(QColor(visual.palette.text))
                painter.drawText(band, Qt.AlignmentFlag.AlignCenter, code)
    finally:
        painter.restore()


_LEGEND_FLAGS = Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap | Qt.TextFlag.TextWrapAnywhere


def _row_height(row: str, width: float, device: QPaintDevice, scale: float) -> float:
    font = _font_for_device(device, modern_oilfield_report_profile().typography.caption_pt * scale, row)
    bounds = QFontMetricsF(font, device).boundingRect(QRectF(0, 0, max(1.0, width), 10000), int(_LEGEND_FLAGS), row)
    return float(ceil(bounds.height() + 5.0 * scale))


def _legend_header_height(device: QPaintDevice, language: AppLanguage, scale: float) -> float:
    font = _font_for_device(device, modern_oilfield_report_profile().typography.section_pt * scale,
                            context_title(language))
    return max(24.0 * scale, float(ceil(QFontMetricsF(font, device).height() + 8.0 * scale)))


def context_legend_height(
    rows: tuple[str, ...], width: float, device: QPaintDevice, *, scale: float = 1.0,
    language: AppLanguage = AppLanguage.RU,
) -> float:
    return (_legend_header_height(device, language, scale)
            + sum(_row_height(row, width, device, scale) for row in rows)) if rows else 0.0


def paint_context_legend(painter: QPainter, rect: QRectF, rows: tuple[str, ...], language: AppLanguage, *, scale: float = 1.0) -> None:
    painter.save()
    try:
        visual = modern_oilfield_report_profile()
        painter.setClipRect(rect, Qt.ClipOperation.IntersectClip)
        painter.setPen(QColor(visual.palette.text))
        title = context_title(language)
        header_height = _legend_header_height(painter.device(), language, scale)
        painter.setFont(_font_for_device(painter.device(), visual.typography.section_pt * scale, title))
        painter.drawText(QRectF(rect.left(), rect.top(), rect.width(), header_height - 4 * scale), title)
        y = rect.top() + header_height - 2 * scale
        for row in rows:
            font = _font_for_device(painter.device(), visual.typography.caption_pt * scale, row)
            painter.setFont(font)
            height = _row_height(row, rect.width(), painter.device(), scale)
            painter.drawText(QRectF(rect.left(), y, rect.width(), height), _LEGEND_FLAGS, row)
            y += height
    finally:
        painter.restore()


def render_context_legend_pages(canvas: PageCanvas, segments: tuple[GasContextSegment, ...], language: AppLanguage, unit: str) -> None:
    rows = context_legend_rows(segments, language, unit)
    if not rows:
        return
    pages: list[tuple[str, ...]] = []
    current: list[str] = []
    header_height = _legend_header_height(canvas.painter.device(), language, 1.0)
    height = header_height
    for row in rows:
        row_height = _row_height(row, canvas.content_rect.width(), canvas.painter.device(), 1.0)
        if current and height + row_height > canvas.content_rect.height():
            pages.append(tuple(current))
            current = []
            height = header_height
        current.append(row)
        height += row_height
    if current:
        pages.append(tuple(current))
    for page in pages:
        canvas.new_page()
        paint_context_legend(canvas.painter, canvas.content_rect, page, language)
        canvas.y = canvas.content_rect.bottom()
