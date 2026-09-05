from __future__ import annotations

from math import floor, isclose

import numpy as np
from PySide6.QtCore import QLineF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart as base_chart
from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import (
    CHART_HEADER_HEIGHT,
    CHART_LEGEND_HEIGHT,
    CHART_NOTE_HEIGHT,
    CHART_TRACK_HEADER_HEIGHT,
    ChartGeometry,
    DepthPage,
    chart_geometry,
    plan_depth_pages,
)
from geoworkbench.printing.hydrocarbon_interpretation_report_range import (
    ReportDepthRange,
)
from geoworkbench.printing.unicode_support import print_font
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
)
from geoworkbench.services.localization import AppLanguage


_MAJOR_TARGET_TICKS = 6
_MINOR_DIVISIONS = 5


def render_chart_pages(
    canvas: PageCanvas,
    report: HydrocarbonInterpretationReport,
    dataset: Dataset,
    language: AppLanguage,
    *,
    depth_range: ReportDepthRange | None = None,
) -> None:
    """Render chart pages with printer-safe major and minor depth graduations."""

    depth = np.asarray(dataset.depth, dtype=np.float64)
    finite_depth = np.isfinite(depth)
    if depth.ndim != 1 or np.count_nonzero(finite_depth) < 2:
        return
    panels = tuple(
        (name, curves)
        for name, curves in base_chart._panel_curves(report, dataset)
        if curves
    )
    if not panels:
        return

    available_height = (
        canvas.content_rect.height()
        - CHART_HEADER_HEIGHT
        - CHART_TRACK_HEADER_HEIGHT
        - CHART_LEGEND_HEIGHT
        - CHART_NOTE_HEIGHT
    )
    depth_min = float(np.nanmin(depth[finite_depth]))
    depth_max = float(np.nanmax(depth[finite_depth]))
    if depth_range is not None:
        depth_min = depth_range.top_depth
        depth_max = depth_range.bottom_depth
    pages = plan_depth_pages(
        depth_min,
        depth_max,
        available_height,
    )
    ranges = base_chart._curve_ranges(panels, dataset)
    for page_index, page in enumerate(pages, start=1):
        canvas.new_page()
        _draw_chart_page(
            canvas.painter,
            chart_geometry(canvas.content_rect, page, len(panels)),
            page,
            page_index,
            len(pages),
            report,
            dataset,
            panels,
            ranges,
            language,
        )
        canvas.y = canvas.content_rect.bottom()


def major_depth_ticks(
    page: DepthPage,
    plot_height_points: float,
) -> tuple[float, ...]:
    """Return readable labelled ticks, always including exact page limits."""

    step = base_chart._nice_tick_step(page.span, target_ticks=_MAJOR_TARGET_TICKS)
    return base_chart._readable_depth_ticks(page, step, plot_height_points)


def minor_depth_ticks(page: DepthPage) -> tuple[float, ...]:
    """Return unlabelled subdivisions between the adaptive major ticks."""

    major_step = base_chart._nice_tick_step(
        page.span,
        target_ticks=_MAJOR_TARGET_TICKS,
    )
    minor_step = major_step / _MINOR_DIVISIONS
    if not np.isfinite(minor_step) or minor_step <= 0.0:
        return ()
    tolerance = minor_step * 1e-7
    value = floor(page.top_depth / minor_step) * minor_step
    ticks: list[float] = []
    while value <= page.bottom_depth + tolerance:
        if page.top_depth + tolerance < value < page.bottom_depth - tolerance:
            ratio = value / major_step
            if not isclose(ratio, round(ratio), abs_tol=1e-7):
                ticks.append(float(value))
        value += minor_step
    return tuple(ticks)


def _draw_chart_page(
    painter: QPainter,
    geometry: ChartGeometry,
    page: DepthPage,
    page_index: int,
    page_count: int,
    report: HydrocarbonInterpretationReport,
    dataset: Dataset,
    panels: tuple[tuple[str, tuple[CurveData, ...]], ...],
    ranges: dict[str, tuple[float, float]],
    language: AppLanguage,
) -> None:
    labels = base_chart._labels(language)
    title_font = print_font(15.0, text=labels["title"])
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
        labels["title"],
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
            ranges,
            intervals,
            language,
        )
        base_chart._draw_legend(
            painter,
            geometry.legend_rect,
            panel_index,
            len(panels),
            curves,
            ranges,
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
    labels = base_chart._labels(language)
    painter.fillRect(rect, QColor("#ffffff"))
    painter.setPen(QPen(QColor("#263746"), 1.15))
    painter.drawRect(rect)
    title = labels["depth"] + (f", {unit}" if unit else "")
    title_font = print_font(7.4, text=title)
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.setPen(QColor("#172033"))
    painter.drawText(
        QRectF(rect.left() - 2.0, rect.top() - 28.0, rect.width() + 4.0, 18.0),
        Qt.AlignmentFlag.AlignCenter,
        title,
    )

    for value in minor_depth_ticks(page):
        y = base_chart._depth_y(value, page, rect)
        painter.setPen(QPen(QColor("#6b7c8c"), 0.55))
        if side == "left":
            painter.drawLine(QLineF(rect.right() - 4.5, y, rect.right(), y))
        else:
            painter.drawLine(QLineF(rect.left(), y, rect.left() + 4.5, y))

    major_step = base_chart._nice_tick_step(
        page.span,
        target_ticks=_MAJOR_TARGET_TICKS,
    )
    ticks = major_depth_ticks(page, rect.height())
    tick_font = print_font(7.5, text=f"{page.bottom_depth:.1f}")
    tick_font.setBold(True)
    painter.setFont(tick_font)
    for value in ticks:
        y = base_chart._depth_y(value, page, rect)
        painter.setPen(QPen(QColor("#263746"), 1.05))
        if side == "left":
            painter.drawLine(QLineF(rect.right() - 10.0, y, rect.right(), y))
            text_rect = QRectF(
                rect.left() + 1.0,
                y - 8.0,
                rect.width() - 13.0,
                16.0,
            )
            alignment = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        else:
            painter.drawLine(QLineF(rect.left(), y, rect.left() + 10.0, y))
            text_rect = QRectF(
                rect.left() + 12.0,
                y - 8.0,
                rect.width() - 13.0,
                16.0,
            )
            alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        painter.setPen(QColor("#172033"))
        painter.drawText(
            text_rect,
            alignment,
            base_chart._depth_label(value, major_step),
        )
    painter.setPen(QPen(QColor("#263746"), 1.15))
    painter.drawRect(rect)


def _draw_panel(
    painter: QPainter,
    rect: QRectF,
    page: DepthPage,
    dataset: Dataset,
    panel_name: str,
    curves: tuple[CurveData, ...],
    ranges: dict[str, tuple[float, float]],
    intervals: tuple[tuple[float, float], ...],
    language: AppLanguage,
) -> None:
    painter.fillRect(rect, QColor("#ffffff"))
    for tick in minor_depth_ticks(page):
        y = base_chart._depth_y(tick, page, rect)
        painter.setPen(QPen(QColor("#e0e7ee"), 0.42))
        painter.drawLine(QLineF(rect.left(), y, rect.right(), y))

    major_step = base_chart._nice_tick_step(
        page.span,
        target_ticks=_MAJOR_TARGET_TICKS,
    )
    for tick in base_chart._depth_ticks(page, major_step):
        y = base_chart._depth_y(tick, page, rect)
        painter.setPen(QPen(QColor("#aebdca"), 0.78))
        painter.drawLine(QLineF(rect.left(), y, rect.right(), y))

    for index in range(5):
        x = rect.left() + index / 4.0 * rect.width()
        painter.setPen(QPen(QColor("#d6dee7"), 0.5))
        painter.drawLine(QLineF(x, rect.top(), x, rect.bottom()))
        painter.setFont(print_font(6.2, text="100"))
        painter.setPen(QColor("#475569"))
        painter.drawText(
            QRectF(x - 14.0, rect.top() - 19.0, 28.0, 12.0),
            Qt.AlignmentFlag.AlignCenter,
            str(index * 25),
        )

    base_chart._draw_interval_bands(painter, rect, page, intervals)
    heading = base_chart._labels(language)[panel_name]
    heading_font = print_font(7.5, text=heading)
    heading_font.setBold(True)
    painter.setFont(heading_font)
    painter.setPen(QColor("#172033"))
    painter.drawText(
        QRectF(rect.left(), rect.top() - 32.0, rect.width(), 15.0),
        Qt.AlignmentFlag.AlignCenter,
        heading,
    )
    base_chart._draw_curves(painter, rect, page, dataset, curves, ranges)
    painter.setPen(QPen(QColor("#263746"), 1.1))
    painter.drawRect(rect)


__all__ = [
    "major_depth_ticks",
    "minor_depth_ticks",
    "render_chart_pages",
]
