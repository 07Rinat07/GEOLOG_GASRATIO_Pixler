from __future__ import annotations

from dataclasses import dataclass
from html import escape
from math import ceil, floor, log10
import re
from typing import Any

import numpy as np
from PySide6.QtCore import QLineF, QRectF, Qt
from PySide6.QtGui import QColor, QPageLayout, QPainter, QPen, QTextDocument

from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.printing.unicode_support import print_font
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
    hydrocarbon_interpretation_html,
)
from geoworkbench.services.hydrocarbon_interpretation_gas_html import (
    inject_interval_gas_statistics_html,
)
from geoworkbench.services.localization import AppLanguage


_POINTS_PER_MM = 72.0 / 25.4
_STANDARD_DEPTH_SCALES = (
    50,
    100,
    200,
    250,
    500,
    750,
    1_000,
    1_500,
    2_000,
    2_500,
    5_000,
    10_000,
    20_000,
)
_MAX_AUTOMATIC_CHART_PAGES = 12
_TARGET_DEPTH_PER_PAGE = 150.0
_PAGE_FOOTER_HEIGHT = 16.0
_CHART_HEADER_HEIGHT = 58.0
_CHART_TRACK_HEADER_HEIGHT = 34.0
_CHART_LEGEND_HEIGHT = 92.0
_CHART_NOTE_HEIGHT = 28.0
_MIN_CHART_HEIGHT = 42.0

_PANEL_METHOD_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "total",
        (
            "TG_NORM_CALC",
            "TG_NORM",
            "NORMALIZED_TOTAL_GAS",
            "TOTAL_GAS_NORM",
            "NORM_TG",
            "TGNORM",
            "TG_CALC",
            "TG",
            "TGAS",
            "TOTALGAS",
            "TOTAL_GAS",
        ),
    ),
    (
        "ratios",
        ("WH", "BH", "CH", "C1_C2", "C1_C3", "C1_C4", "C1_C5"),
    ),
    (
        "drilling",
        (
            "DEXP",
            "DEXPC",
            "NCT",
            "DEXPC_NCT",
            "ROP",
            "BIT",
            "BS",
            "FLOW_IN",
            "FLOW_OUT",
        ),
    ),
)

_COLORS = (
    "#1d4ed8",
    "#dc2626",
    "#16a34a",
    "#9333ea",
    "#ea580c",
    "#0891b2",
    "#64748b",
)

_VOID_TAGS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)
_TAG_PATTERN = re.compile(r"<!--.*?-->|<![^>]*>|<\s*(/?)\s*([A-Za-z0-9]+)\b[^>]*>", re.S)
_STYLE_PATTERN = re.compile(r"<style\b[^>]*>(.*?)</style>", re.I | re.S)
_BODY_PATTERN = re.compile(r"<body\b[^>]*>(.*?)</body>", re.I | re.S)
_ROW_PATTERN = re.compile(r"<tr\b[^>]*>.*?</tr>", re.I | re.S)
_THEAD_PATTERN = re.compile(r"<thead\b[^>]*>.*?</thead>", re.I | re.S)
_TBODY_PATTERN = re.compile(r"<tbody\b[^>]*>(.*?)</tbody>", re.I | re.S)
_COLGROUP_PATTERN = re.compile(r"<colgroup\b[^>]*>.*?</colgroup>", re.I | re.S)
_LIST_ITEM_PATTERN = re.compile(r"<li\b[^>]*>.*?</li>", re.I | re.S)


@dataclass(frozen=True, slots=True)
class DepthPage:
    top_depth: float
    bottom_depth: float
    scale_denominator: int
    plot_height_points: float

    @property
    def span(self) -> float:
        return self.bottom_depth - self.top_depth


@dataclass(frozen=True, slots=True)
class ChartGeometry:
    page_rect: QRectF
    plot_rect: QRectF
    left_axis_rect: QRectF
    right_axis_rect: QRectF
    panel_rects: tuple[QRectF, ...]
    legend_rect: QRectF
    note_rect: QRectF


@dataclass(frozen=True, slots=True)
class _TableParts:
    opening: str
    colgroup: str
    thead: str
    rows: tuple[str, ...]


class _PageCanvas:
    def __init__(self, device: Any, painter: QPainter, language: AppLanguage) -> None:
        self.device = device
        self.painter = painter
        self.language = language
        self.page_rect = QRectF(
            device.pageLayout().paintRect(QPageLayout.Unit.Point)
        )
        self.content_rect = self.page_rect.adjusted(
            0.0,
            0.0,
            0.0,
            -_PAGE_FOOTER_HEIGHT,
        )
        self.page_number = 0
        self.y = self.content_rect.top()
        self.started = False

    @property
    def remaining_height(self) -> float:
        return max(0.0, self.content_rect.bottom() - self.y)

    @property
    def has_content(self) -> bool:
        return self.y > self.content_rect.top() + 0.5

    def new_page(self) -> None:
        if self.started and not self.device.newPage():
            raise RuntimeError("Не удалось создать следующую страницу печатного отчёта")
        self.started = True
        self.page_number += 1
        self.y = self.content_rect.top()
        self.painter.fillRect(self.page_rect, QColor("#ffffff"))
        self._draw_page_number()

    def reserve(self, height: float, *, force_new_page: bool = False) -> None:
        if not self.started:
            self.new_page()
        if force_new_page or (height > self.remaining_height and self.has_content):
            self.new_page()

    def advance(self, height: float, spacing: float = 5.0) -> None:
        self.y += height + spacing

    def _draw_page_number(self) -> None:
        label = {
            AppLanguage.RU: "Страница",
            AppLanguage.KK: "Бет",
            AppLanguage.EN: "Page",
        }[self.language]
        footer = QRectF(
            self.page_rect.left(),
            self.content_rect.bottom() + 2.0,
            self.page_rect.width(),
            _PAGE_FOOTER_HEIGHT - 2.0,
        )
        self.painter.setPen(QColor("#64748b"))
        self.painter.setFont(print_font(7.5, text=f"{label} {self.page_number}"))
        self.painter.drawText(
            footer,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"{label} {self.page_number}",
        )


def plan_depth_pages(
    depth_min: float,
    depth_max: float,
    available_plot_height_points: float,
    *,
    max_pages: int = _MAX_AUTOMATIC_CHART_PAGES,
) -> tuple[DepthPage, ...]:
    """Choose a readable standard scale and split a well into continuous pages."""

    low = float(min(depth_min, depth_max))
    high = float(max(depth_min, depth_max))
    if not np.isfinite(low) or not np.isfinite(high) or high <= low:
        return ()
    if not np.isfinite(available_plot_height_points) or available_plot_height_points <= 0:
        raise ValueError("Высота области графика должна быть больше нуля")
    if max_pages < 1:
        raise ValueError("Число страниц графика должно быть не меньше одной")

    span = high - low
    height_mm = available_plot_height_points / _POINTS_PER_MM
    desired_pages = min(max_pages, max(1, int(ceil(span / _TARGET_DEPTH_PER_PAGE))))
    required_scale = span * 1_000.0 / (height_mm * desired_pages)
    scale = next(
        (candidate for candidate in _STANDARD_DEPTH_SCALES if candidate >= required_scale),
        _STANDARD_DEPTH_SCALES[-1],
    )
    depth_capacity = height_mm * scale / 1_000.0
    pages: list[DepthPage] = []
    top = low
    tolerance = max(1e-9, span * 1e-12)
    while top < high - tolerance:
        bottom = min(high, top + depth_capacity)
        page_span = bottom - top
        plot_height_mm = page_span * 1_000.0 / scale
        pages.append(
            DepthPage(
                top,
                bottom,
                scale,
                plot_height_mm * _POINTS_PER_MM,
            )
        )
        top = bottom
    return tuple(pages)


def chart_geometry(
    content_rect: QRectF,
    page: DepthPage,
    panel_count: int,
) -> ChartGeometry:
    """Return chart rectangles guaranteed to remain inside the printable area."""

    if panel_count < 1:
        raise ValueError("Для графика требуется хотя бы одна дорожка")
    chart_top = content_rect.top() + _CHART_HEADER_HEIGHT + _CHART_TRACK_HEADER_HEIGHT
    maximum_plot_height = max(
        _MIN_CHART_HEIGHT,
        content_rect.height()
        - _CHART_HEADER_HEIGHT
        - _CHART_TRACK_HEADER_HEIGHT
        - _CHART_LEGEND_HEIGHT
        - _CHART_NOTE_HEIGHT,
    )
    plot_height = min(maximum_plot_height, max(_MIN_CHART_HEIGHT, page.plot_height_points))
    axis_width = 54.0
    axis_gap = 7.0
    panel_gap = 8.0
    left_axis = QRectF(content_rect.left(), chart_top, axis_width, plot_height)
    right_axis = QRectF(
        content_rect.right() - axis_width,
        chart_top,
        axis_width,
        plot_height,
    )
    panels_left = left_axis.right() + axis_gap
    panels_right = right_axis.left() - axis_gap
    panels_width = panels_right - panels_left
    panel_width = (panels_width - panel_gap * (panel_count - 1)) / panel_count
    panel_rects = tuple(
        QRectF(
            panels_left + index * (panel_width + panel_gap),
            chart_top,
            panel_width,
            plot_height,
        )
        for index in range(panel_count)
    )
    legend_top = chart_top + plot_height + 7.0
    legend = QRectF(
        panels_left,
        legend_top,
        panels_width,
        _CHART_LEGEND_HEIGHT - 7.0,
    )
    note = QRectF(
        content_rect.left(),
        content_rect.bottom() - _CHART_NOTE_HEIGHT,
        content_rect.width(),
        _CHART_NOTE_HEIGHT,
    )
    return ChartGeometry(content_rect, QRectF(panels_left, chart_top, panels_width, plot_height), left_axis, right_axis, panel_rects, legend, note)


def render_hydrocarbon_interpretation_report(
    device: Any,
    report: HydrocarbonInterpretationReport,
    *,
    language: AppLanguage = AppLanguage.RU,
    dataset: Dataset | None = None,
    include_chart: bool = False,
) -> None:
    """Render one controlled multi-page report to QPdfWriter or QPrinter."""

    html = hydrocarbon_interpretation_html(report, language)
    if dataset is not None:
        html = inject_interval_gas_statistics_html(html, report, dataset, language)

    painter = QPainter(device)
    if not painter.isActive():
        raise RuntimeError("Не удалось запустить движок печати отчёта")
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    x_scale = float(device.logicalDpiX()) / 72.0
    y_scale = float(device.logicalDpiY()) / 72.0
    painter.scale(x_scale, y_scale)
    canvas = _PageCanvas(device, painter, language)
    try:
        style = _document_style(html)
        blocks = _top_level_body_blocks(html)
        canvas.new_page()

        split_index = min(2, len(blocks))
        for block in blocks[:split_index]:
            _render_atomic_html(canvas, style, block)

        if include_chart and dataset is not None:
            _render_chart_pages(canvas, report, dataset, language)

        if split_index < len(blocks):
            if canvas.has_content:
                canvas.new_page()
            _render_html_blocks(canvas, style, blocks[split_index:])
    finally:
        painter.end()


def _render_chart_pages(
    canvas: _PageCanvas,
    report: HydrocarbonInterpretationReport,
    dataset: Dataset,
    language: AppLanguage,
) -> None:
    depth = np.asarray(dataset.depth, dtype=np.float64)
    finite_depth = np.isfinite(depth)
    if depth.ndim != 1 or np.count_nonzero(finite_depth) < 2:
        return
    panels = tuple(
        (name, curves)
        for name, curves in _panel_curves(report, dataset)
        if curves
    )
    if not panels:
        return

    available_plot_height = (
        canvas.content_rect.height()
        - _CHART_HEADER_HEIGHT
        - _CHART_TRACK_HEADER_HEIGHT
        - _CHART_LEGEND_HEIGHT
        - _CHART_NOTE_HEIGHT
    )
    pages = plan_depth_pages(
        float(np.nanmin(depth[finite_depth])),
        float(np.nanmax(depth[finite_depth])),
        available_plot_height,
    )
    if not pages:
        return

    curve_ranges = _curve_ranges(panels, dataset)
    for page_index, page in enumerate(pages, start=1):
        canvas.new_page()
        geometry = chart_geometry(canvas.content_rect, page, len(panels))
        _draw_chart_page(
            canvas.painter,
            geometry,
            page,
            page_index,
            len(pages),
            report,
            dataset,
            panels,
            curve_ranges,
            language,
        )
        canvas.y = canvas.content_rect.bottom()


def _draw_chart_page(
    painter: QPainter,
    geometry: ChartGeometry,
    page: DepthPage,
    page_index: int,
    page_count: int,
    report: HydrocarbonInterpretationReport,
    dataset: Dataset,
    panels: tuple[tuple[str, tuple[CurveData, ...]], ...],
    curve_ranges: dict[str, tuple[float, float]],
    language: AppLanguage,
) -> None:
    labels = _chart_labels(language)
    title = labels["title"]
    title_font = print_font(15.0, text=title)
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.setPen(QColor("#172033"))
    painter.drawText(
        QRectF(
            geometry.page_rect.left(),
            geometry.page_rect.top(),
            geometry.page_rect.width(),
            25.0,
        ),
        Qt.AlignmentFlag.AlignCenter,
        title,
    )
    subtitle = labels["page"].format(
        current=page_index,
        total=page_count,
        top=page.top_depth,
        bottom=page.bottom_depth,
        unit=report.depth_unit,
        scale=page.scale_denominator,
    )
    painter.setFont(print_font(8.5, text=subtitle))
    painter.setPen(QColor("#475569"))
    painter.drawText(
        QRectF(
            geometry.page_rect.left(),
            geometry.page_rect.top() + 27.0,
            geometry.page_rect.width(),
            20.0,
        ),
        Qt.AlignmentFlag.AlignCenter,
        subtitle,
    )

    _draw_depth_axis(
        painter,
        geometry.left_axis_rect,
        page,
        report.depth_unit,
        side="left",
        language=language,
    )
    _draw_depth_axis(
        painter,
        geometry.right_axis_rect,
        page,
        report.depth_unit,
        side="right",
        language=language,
    )

    intervals = tuple(
        (candidate.top_depth, candidate.bottom_depth)
        for candidate in report.candidates
    )
    for panel_index, ((panel_name, curves), rect) in enumerate(
        zip(panels, geometry.panel_rects, strict=True)
    ):
        _draw_panel(
            painter,
            rect,
            page,
            dataset,
            panel_name,
            curves,
            curve_ranges,
            intervals,
            language,
        )
        _draw_panel_legend(
            painter,
            geometry.legend_rect,
            panel_index,
            len(panels),
            curves,
            curve_ranges,
        )

    painter.setPen(QColor("#475569"))
    painter.setFont(print_font(6.8, text=labels["note"]))
    painter.drawText(
        geometry.note_rect,
        Qt.AlignmentFlag.AlignLeft
        | Qt.AlignmentFlag.AlignTop
        | Qt.TextFlag.TextWordWrap,
        labels["note"],
    )


def _draw_depth_axis(
    painter: QPainter,
    rect: QRectF,
    page: DepthPage,
    unit: str,
    *,
    side: str,
    language: AppLanguage,
) -> None:
    labels = _chart_labels(language)
    painter.fillRect(rect, QColor("#f8fafc"))
    painter.setPen(QPen(QColor("#334155"), 0.9))
    painter.drawRect(rect)
    title = labels["depth"] + (f", {unit}" if unit else "")
    font = print_font(7.0, text=title)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor("#172033"))
    painter.drawText(
        QRectF(rect.left() - 2.0, rect.top() - 28.0, rect.width() + 4.0, 18.0),
        Qt.AlignmentFlag.AlignCenter,
        title,
    )

    step = _nice_tick_step(page.span, target_ticks=8)
    start = floor(page.top_depth / step) * step
    ticks: list[float] = []
    value = start
    tolerance = step * 1e-7
    while value <= page.bottom_depth + tolerance:
        if value >= page.top_depth - tolerance:
            ticks.append(float(value))
        value += step
    for endpoint in (page.top_depth, page.bottom_depth):
        if not any(abs(endpoint - tick) <= tolerance for tick in ticks):
            ticks.append(endpoint)
    ticks.sort()

    painter.setFont(print_font(6.7, text=f"{page.bottom_depth:.1f}"))
    for value in ticks:
        y = _depth_y(value, page, rect)
        painter.setPen(QPen(QColor("#64748b"), 0.6))
        if side == "left":
            painter.drawLine(QLineF(rect.right() - 8.0, y, rect.right(), y))
            text_rect = QRectF(rect.left() + 1.0, y - 7.0, rect.width() - 11.0, 14.0)
            alignment = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        else:
            painter.drawLine(QLineF(rect.left(), y, rect.left() + 8.0, y))
            text_rect = QRectF(rect.left() + 10.0, y - 7.0, rect.width() - 11.0, 14.0)
            alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        painter.setPen(QColor("#334155"))
        painter.drawText(text_rect, alignment, _depth_label(value, step))

    painter.setPen(QPen(QColor("#334155"), 0.9))
    painter.drawRect(rect)


def _draw_panel(
    painter: QPainter,
    rect: QRectF,
    page: DepthPage,
    dataset: Dataset,
    panel_name: str,
    curves: tuple[CurveData, ...],
    curve_ranges: dict[str, tuple[float, float]],
    intervals: tuple[tuple[float, float], ...],
    language: AppLanguage,
) -> None:
    labels = _chart_labels(language)
    painter.fillRect(rect, QColor("#ffffff"))
    tick_step = _nice_tick_step(page.span, target_ticks=8)
    tick = floor(page.top_depth / tick_step) * tick_step
    while tick <= page.bottom_depth + tick_step * 1e-7:
        if tick >= page.top_depth - tick_step * 1e-7:
            y = _depth_y(tick, page, rect)
            painter.setPen(QPen(QColor("#d8e0e8"), 0.45))
            painter.drawLine(QLineF(rect.left(), y, rect.right(), y))
        tick += tick_step
    for index in range(5):
        x = rect.left() + index / 4.0 * rect.width()
        painter.setPen(QPen(QColor("#e4e9ef"), 0.4))
        painter.drawLine(QLineF(x, rect.top(), x, rect.bottom()))
        painter.setFont(print_font(5.8, text="100"))
        painter.setPen(QColor("#64748b"))
        painter.drawText(
            QRectF(x - 14.0, rect.top() - 19.0, 28.0, 12.0),
            Qt.AlignmentFlag.AlignCenter,
            str(index * 25),
        )

    for top_depth, bottom_depth in intervals:
        overlap_top = max(page.top_depth, min(top_depth, bottom_depth))
        overlap_bottom = min(page.bottom_depth, max(top_depth, bottom_depth))
        if overlap_bottom <= overlap_top:
            continue
        y1 = _depth_y(overlap_top, page, rect)
        y2 = _depth_y(overlap_bottom, page, rect)
        color = QColor("#f59e0b")
        color.setAlpha(42)
        painter.fillRect(
            QRectF(rect.left(), min(y1, y2), rect.width(), max(1.0, abs(y2 - y1))),
            color,
        )

    heading = labels[panel_name]
    heading_font = print_font(7.5, text=heading)
    heading_font.setBold(True)
    painter.setFont(heading_font)
    painter.setPen(QColor("#172033"))
    painter.drawText(
        QRectF(rect.left(), rect.top() - 32.0, rect.width(), 15.0),
        Qt.AlignmentFlag.AlignCenter,
        heading,
    )

    depth = np.asarray(dataset.depth, dtype=np.float64)
    page_indices = np.flatnonzero(
        np.isfinite(depth)
        & (depth >= page.top_depth)
        & (depth <= page.bottom_depth)
    )
    page_indices = page_indices[np.argsort(depth[page_indices], kind="stable")]
    if page_indices.size > 2_500:
        sample_positions = np.linspace(0, page_indices.size - 1, 2_500, dtype=np.int64)
        page_indices = page_indices[sample_positions]

    painter.save()
    painter.setClipRect(rect.adjusted(0.8, 0.8, -0.8, -0.8))
    curve_rect = rect.adjusted(3.0, 0.0, -3.0, 0.0)
    for curve_index, curve in enumerate(curves):
        values = np.asarray(curve.values, dtype=np.float64)
        value_range = curve_ranges.get(curve.metadata.curve_id)
        if values.shape != depth.shape or value_range is None:
            continue
        low, high = value_range
        painter.setPen(QPen(QColor(_COLORS[curve_index % len(_COLORS)]), 0.8))
        previous: tuple[float, float] | None = None
        for row_index in page_indices:
            value = values[row_index]
            if not np.isfinite(value):
                previous = None
                continue
            normalized = float(np.clip((value - low) / (high - low), 0.0, 1.0))
            point = (
                curve_rect.left() + normalized * curve_rect.width(),
                _depth_y(float(depth[row_index]), page, curve_rect),
            )
            if previous is not None:
                painter.drawLine(QLineF(previous[0], previous[1], point[0], point[1]))
            previous = point
    painter.restore()
    painter.setPen(QPen(QColor("#334155"), 1.0))
    painter.drawRect(rect)


def _draw_panel_legend(
    painter: QPainter,
    legend_rect: QRectF,
    panel_index: int,
    panel_count: int,
    curves: tuple[CurveData, ...],
    curve_ranges: dict[str, tuple[float, float]],
) -> None:
    column_gap = 8.0
    column_width = (legend_rect.width() - column_gap * (panel_count - 1)) / panel_count
    column = QRectF(
        legend_rect.left() + panel_index * (column_width + column_gap),
        legend_rect.top(),
        column_width,
        legend_rect.height(),
    )
    for row_index, curve in enumerate(curves[:5]):
        value_range = curve_ranges.get(curve.metadata.curve_id)
        if value_range is None:
            continue
        low, high = value_range
        y = column.top() + row_index * 14.5
        color = QColor(_COLORS[row_index % len(_COLORS)])
        painter.setPen(QPen(color, 1.8))
        painter.drawLine(QLineF(column.left(), y + 5.0, column.left() + 17.0, y + 5.0))
        text = curve.metadata.original_mnemonic
        if curve.metadata.unit:
            text += f" [{curve.metadata.unit}]"
        text += f"  p1={low:.4g}; p99={high:.4g}"
        painter.setPen(QColor("#172033"))
        painter.setFont(print_font(5.9, text=text))
        painter.drawText(
            QRectF(column.left() + 21.0, y, column.width() - 21.0, 12.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            text,
        )


def _curve_ranges(
    panels: tuple[tuple[str, tuple[CurveData, ...]], ...],
    dataset: Dataset,
) -> dict[str, tuple[float, float]]:
    result: dict[str, tuple[float, float]] = {}
    for _panel_name, curves in panels:
        for curve in curves:
            values = np.asarray(curve.values, dtype=np.float64)
            finite = values[np.isfinite(values)] if values.shape == dataset.depth.shape else np.array([])
            if finite.size < 2:
                continue
            low = float(np.nanpercentile(finite, 1.0))
            high = float(np.nanpercentile(finite, 99.0))
            if not np.isfinite(low) or not np.isfinite(high):
                continue
            if high <= low:
                high = low + max(1.0, abs(low) * 0.01)
            result[curve.metadata.curve_id] = (low, high)
    return result


def _panel_curves(
    report: HydrocarbonInterpretationReport,
    dataset: Dataset,
) -> tuple[tuple[str, tuple[CurveData, ...]], ...]:
    preferred: list[str] = []
    if report.primary_mnemonic:
        preferred.extend(
            part.strip()
            for part in report.primary_mnemonic.split("|")
            if part.strip()
        )
    for method in report.methods:
        preferred.extend(method.available_mnemonics)

    result: list[tuple[str, tuple[CurveData, ...]]] = []
    for panel_name, fallback_order in _PANEL_METHOD_MARKERS:
        curves: list[CurveData] = []
        seen: set[str] = set()
        for mnemonic in (*preferred, *fallback_order):
            curve = dataset.curve_by_mnemonic(_strip_source_prefix(mnemonic))
            if curve is None or curve.metadata.curve_id in seen:
                continue
            if curve.metadata.original_mnemonic.upper() not in fallback_order:
                continue
            values = np.asarray(curve.values, dtype=np.float64)
            if values.shape != dataset.depth.shape or np.count_nonzero(np.isfinite(values)) < 2:
                continue
            curves.append(curve)
            seen.add(curve.metadata.curve_id)
            if len(curves) >= (3 if panel_name == "total" else 5):
                break
        result.append((panel_name, tuple(curves)))
    return tuple(result)


def _render_html_blocks(
    canvas: _PageCanvas,
    style: str,
    blocks: tuple[str, ...],
) -> None:
    index = 0
    while index < len(blocks):
        block = blocks[index]
        next_block = blocks[index + 1] if index + 1 < len(blocks) else ""
        if _is_heading(block) and next_block.lstrip().lower().startswith("<table"):
            _render_table(canvas, style, next_block, heading=block)
            index += 2
            continue
        if _is_heading(block) and _is_notice(next_block):
            _render_notice(canvas, style, next_block, heading=block)
            index += 2
            continue
        if block.lstrip().lower().startswith("<table"):
            _render_table(canvas, style, block)
        elif _is_notice(block):
            _render_notice(canvas, style, block)
        elif _is_heading(block) and next_block:
            _render_atomic_html(canvas, style, block + next_block)
            index += 1
        else:
            _render_atomic_html(canvas, style, block)
        index += 1


def _render_table(
    canvas: _PageCanvas,
    style: str,
    table_html: str,
    *,
    heading: str = "",
) -> None:
    parts = _table_parts(table_html)
    if not parts.rows:
        _render_atomic_html(canvas, style, heading + table_html, table=True)
        return

    row_index = 0
    first_chunk = True
    while row_index < len(parts.rows):
        prefix = heading if first_chunk else ""
        available = canvas.remaining_height
        if available < 80.0 and canvas.has_content:
            canvas.new_page()
            available = canvas.remaining_height
        best_end = row_index
        best_html = ""
        best_height = 0.0
        end = row_index + 1
        while end <= len(parts.rows):
            candidate = prefix + _table_html(parts, parts.rows[row_index:end])
            document, height = _html_document(style, candidate, canvas.content_rect.width(), table=True)
            del document
            if height <= available + 0.5:
                best_end = end
                best_html = candidate
                best_height = height
                end += 1
                continue
            break
        if best_end == row_index:
            if canvas.has_content:
                canvas.new_page()
                continue
            candidate = prefix + _table_html(parts, (parts.rows[row_index],))
            _render_atomic_html(canvas, style, candidate, table=True, allow_scale=True)
            row_index += 1
            first_chunk = False
            continue
        _draw_html(canvas, style, best_html, best_height, table=True)
        row_index = best_end
        first_chunk = False
        if row_index < len(parts.rows):
            canvas.new_page()


def _render_notice(
    canvas: _PageCanvas,
    style: str,
    notice_html: str,
    *,
    heading: str = "",
) -> None:
    items = tuple(_LIST_ITEM_PATTERN.findall(notice_html))
    if not items:
        _render_atomic_html(canvas, style, heading + notice_html)
        return
    open_match = re.match(r"\s*(<div\b[^>]*>)", notice_html, re.I | re.S)
    opening = open_match.group(1) if open_match else "<div class='notice'>"
    inner_heading = "".join(re.findall(r"<h2\b[^>]*>.*?</h2>", notice_html, re.I | re.S))
    item_index = 0
    first_chunk = True
    while item_index < len(items):
        prefix = heading if first_chunk else ""
        available = canvas.remaining_height
        if available < 70.0 and canvas.has_content:
            canvas.new_page()
            available = canvas.remaining_height
        best_end = item_index
        best_html = ""
        best_height = 0.0
        end = item_index + 1
        while end <= len(items):
            candidate = prefix + opening + inner_heading + "<ul>" + "".join(items[item_index:end]) + "</ul></div>"
            document, height = _html_document(style, candidate, canvas.content_rect.width())
            del document
            if height <= available + 0.5:
                best_end = end
                best_html = candidate
                best_height = height
                end += 1
                continue
            break
        if best_end == item_index:
            if canvas.has_content:
                canvas.new_page()
                continue
            candidate = prefix + opening + inner_heading + "<ul>" + items[item_index] + "</ul></div>"
            _render_atomic_html(canvas, style, candidate, allow_scale=True)
            item_index += 1
            first_chunk = False
            continue
        _draw_html(canvas, style, best_html, best_height)
        item_index = best_end
        first_chunk = False
        if item_index < len(items):
            canvas.new_page()


def _render_atomic_html(
    canvas: _PageCanvas,
    style: str,
    fragment: str,
    *,
    table: bool = False,
    allow_scale: bool = False,
) -> None:
    document, height = _html_document(style, fragment, canvas.content_rect.width(), table=table)
    canvas.reserve(height)
    if height <= canvas.remaining_height + 0.5:
        _draw_document(canvas, document, height)
        return
    if canvas.has_content:
        canvas.new_page()
    if height <= canvas.remaining_height + 0.5:
        _draw_document(canvas, document, height)
        return
    if not allow_scale:
        allow_scale = True
    if allow_scale:
        scale = max(0.68, min(1.0, canvas.remaining_height / max(height, 1.0)))
        _draw_document(canvas, document, height, scale=scale)


def _draw_html(
    canvas: _PageCanvas,
    style: str,
    fragment: str,
    height: float,
    *,
    table: bool = False,
) -> None:
    document, measured = _html_document(style, fragment, canvas.content_rect.width(), table=table)
    _draw_document(canvas, document, max(height, measured))


def _draw_document(
    canvas: _PageCanvas,
    document: QTextDocument,
    height: float,
    *,
    scale: float = 1.0,
) -> None:
    painter = canvas.painter
    painter.save()
    try:
        painter.translate(canvas.content_rect.left(), canvas.y)
        if scale != 1.0:
            painter.scale(scale, scale)
        document.drawContents(
            painter,
            QRectF(0.0, 0.0, canvas.content_rect.width() / scale, height),
        )
    finally:
        painter.restore()
    canvas.advance(height * scale)


def _html_document(
    style: str,
    fragment: str,
    width: float,
    *,
    table: bool = False,
) -> tuple[QTextDocument, float]:
    overrides = """
html, body { background: #ffffff; color: #172033; }
body { margin: 0; font-size: 9pt; }
h1 { margin: 0 0 8px 0; font-size: 17pt; }
h2 { margin: 8px 0 5px 0; font-size: 12pt; page-break-before: auto; break-before: auto; }
.prospective-intervals-heading { page-break-before: auto; break-before: auto; }
.candidate-detail { page-break-inside: avoid; break-inside: avoid; }
"""
    if table:
        overrides += """
table { font-size: 7.2pt; border-collapse: collapse; }
th, td { padding: 3px; }
tr { page-break-inside: avoid; break-inside: avoid; }
"""
    html = f"<html><head><meta charset='utf-8'><style>{style}\n{overrides}</style></head><body>{fragment}</body></html>"
    document = QTextDocument()
    document.setDocumentMargin(0.0)
    document.setDefaultFont(print_font(9.0, text=html))
    document.setTextWidth(width)
    document.setHtml(html)
    size = document.documentLayout().documentSize()
    return document, float(size.height())


def _document_style(html: str) -> str:
    match = _STYLE_PATTERN.search(html)
    return match.group(1) if match else ""


def _top_level_body_blocks(html: str) -> tuple[str, ...]:
    match = _BODY_PATTERN.search(html)
    body = match.group(1) if match else html
    blocks: list[str] = []
    depth = 0
    start: int | None = None
    for tag in _TAG_PATTERN.finditer(body):
        token = tag.group(0)
        if token.startswith(("<!--", "<!")):
            continue
        closing = bool(tag.group(1))
        name = tag.group(2).casefold()
        self_closing = token.rstrip().endswith("/>") or name in _VOID_TAGS
        if not closing:
            if depth == 0:
                start = tag.start()
            if not self_closing:
                depth += 1
            elif depth == 0 and start is not None:
                blocks.append(body[start : tag.end()].strip())
                start = None
        else:
            depth = max(0, depth - 1)
            if depth == 0 and start is not None:
                blocks.append(body[start : tag.end()].strip())
                start = None
    return tuple(block for block in blocks if block)


def _table_parts(table_html: str) -> _TableParts:
    opening_match = re.match(r"\s*(<table\b[^>]*>)", table_html, re.I | re.S)
    opening = opening_match.group(1) if opening_match else "<table>"
    colgroup_match = _COLGROUP_PATTERN.search(table_html)
    thead_match = _THEAD_PATTERN.search(table_html)
    tbody_match = _TBODY_PATTERN.search(table_html)
    body = tbody_match.group(1) if tbody_match else table_html
    return _TableParts(
        opening,
        colgroup_match.group(0) if colgroup_match else "",
        thead_match.group(0) if thead_match else "",
        tuple(_ROW_PATTERN.findall(body)),
    )


def _table_html(parts: _TableParts, rows: tuple[str, ...]) -> str:
    return (
        parts.opening
        + parts.colgroup
        + parts.thead
        + "<tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _is_heading(block: str) -> bool:
    return bool(re.match(r"\s*<h[1-6]\b", block, re.I))


def _is_notice(block: str) -> bool:
    return bool(re.match(r"\s*<div\b[^>]*class=[\"'][^\"']*notice", block, re.I))


def _nice_tick_step(span: float, *, target_ticks: int) -> float:
    raw = max(float(span) / max(1, target_ticks), np.finfo(np.float64).eps)
    magnitude = 10.0 ** floor(log10(raw))
    normalized = raw / magnitude
    factor = 1.0 if normalized <= 1.0 else 2.0 if normalized <= 2.0 else 5.0 if normalized <= 5.0 else 10.0
    return factor * magnitude


def _depth_y(depth: float, page: DepthPage, rect: QRectF) -> float:
    return rect.top() + (float(depth) - page.top_depth) / page.span * rect.height()


def _depth_label(value: float, step: float) -> str:
    if step >= 1.0:
        return f"{value:.0f}" if abs(value - round(value)) < 1e-6 else f"{value:.1f}"
    decimals = max(1, int(ceil(-log10(step))) + 1)
    return f"{value:.{decimals}f}"


def _strip_source_prefix(value: str) -> str:
    stripped = value.strip()
    for prefix in ("server:", "local-calculation:"):
        if stripped.casefold().startswith(prefix):
            return stripped[len(prefix) :].strip()
    return stripped


def _chart_labels(language: AppLanguage) -> dict[str, str]:
    return {
        AppLanguage.RU: {
            "title": "Графики интерпретационных кривых по глубине",
            "page": "Лист графика {current} из {total}: {top:.2f}–{bottom:.2f} {unit}; вертикальный масштаб 1:{scale}",
            "depth": "Глубина",
            "total": "Общий и нормализованный газ",
            "ratios": "Haworth и Pixler",
            "drilling": "Буровой контекст и DEXP",
            "note": (
                "Кривые нормированы внутри дорожек по p1–p99. Оранжевые полосы — перспективные интервалы. "
                "Каждый лист сохраняет физический масштаб глубины; шкалы и внешние границы повторяются слева и справа."
            ),
        },
        AppLanguage.KK: {
            "title": "Тереңдік бойынша интерпретациялық қисықтар графиктері",
            "page": "График беті {current}/{total}: {top:.2f}–{bottom:.2f} {unit}; тік масштаб 1:{scale}",
            "depth": "Тереңдік",
            "total": "Жалпы және нормаланған газ",
            "ratios": "Haworth және Pixler",
            "drilling": "Бұрғылау контексті және DEXP",
            "note": (
                "Қисықтар жол ішінде p1–p99 бойынша нормаланады. Қызғылт сары жолақтар — перспективалы аралықтар. "
                "Әр бет тереңдіктің физикалық масштабын сақтайды; шкалалар мен шекаралар екі жақта қайталанады."
            ),
        },
        AppLanguage.EN: {
            "title": "Depth plots of interpretation curves",
            "page": "Chart sheet {current} of {total}: {top:.2f}–{bottom:.2f} {unit}; vertical scale 1:{scale}",
            "depth": "Depth",
            "total": "Total and normalized gas",
            "ratios": "Haworth and Pixler",
            "drilling": "Drilling context and DEXP",
            "note": (
                "Curves are normalized within tracks to p1–p99. Orange bands mark prospective intervals. "
                "Every sheet preserves a physical depth scale; scales and outer borders repeat on both sides."
            ),
        },
    }[language]


__all__ = [
    "ChartGeometry",
    "DepthPage",
    "chart_geometry",
    "plan_depth_pages",
    "render_hydrocarbon_interpretation_report",
]
