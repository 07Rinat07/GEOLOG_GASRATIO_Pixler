from __future__ import annotations

from dataclasses import dataclass
from math import ceil

import numpy as np
from PySide6.QtCore import QRectF


POINTS_PER_MM = 72.0 / 25.4
STANDARD_DEPTH_SCALES = (
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
MAX_AUTOMATIC_CHART_PAGES = 12
TARGET_DEPTH_PER_PAGE = 150.0
PAGE_FOOTER_HEIGHT = 16.0
CHART_HEADER_HEIGHT = 58.0
CHART_TRACK_HEADER_HEIGHT = 34.0
CHART_LEGEND_HEIGHT = 92.0
CHART_NOTE_HEIGHT = 28.0
MIN_CHART_HEIGHT = 28.0


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


def plan_depth_pages(
    depth_min: float,
    depth_max: float,
    available_plot_height_points: float,
    *,
    max_pages: int = MAX_AUTOMATIC_CHART_PAGES,
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
    height_mm = available_plot_height_points / POINTS_PER_MM
    desired_pages = min(max_pages, max(1, int(ceil(span / TARGET_DEPTH_PER_PAGE))))
    required_scale = span * 1_000.0 / (height_mm * desired_pages)
    scale = next(
        (candidate for candidate in STANDARD_DEPTH_SCALES if candidate >= required_scale),
        0,
    )
    if scale == 0:
        scale = int(ceil(required_scale / 5_000.0) * 5_000)

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
                plot_height_mm * POINTS_PER_MM,
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
    chart_top = content_rect.top() + CHART_HEADER_HEIGHT + CHART_TRACK_HEADER_HEIGHT
    maximum_plot_height = max(
        MIN_CHART_HEIGHT,
        content_rect.height()
        - CHART_HEADER_HEIGHT
        - CHART_TRACK_HEADER_HEIGHT
        - CHART_LEGEND_HEIGHT
        - CHART_NOTE_HEIGHT,
    )
    plot_height = min(
        maximum_plot_height,
        max(MIN_CHART_HEIGHT, page.plot_height_points),
    )
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
    if panel_width <= 0:
        raise ValueError("Печатная область слишком узкая для дорожек графика")
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
        CHART_LEGEND_HEIGHT - 7.0,
    )
    note = QRectF(
        content_rect.left(),
        content_rect.bottom() - CHART_NOTE_HEIGHT,
        content_rect.width(),
        CHART_NOTE_HEIGHT,
    )
    return ChartGeometry(
        content_rect,
        QRectF(panels_left, chart_top, panels_width, plot_height),
        left_axis,
        right_axis,
        panel_rects,
        legend,
        note,
    )


__all__ = [
    "CHART_HEADER_HEIGHT",
    "CHART_LEGEND_HEIGHT",
    "CHART_NOTE_HEIGHT",
    "CHART_TRACK_HEADER_HEIGHT",
    "ChartGeometry",
    "DepthPage",
    "MAX_AUTOMATIC_CHART_PAGES",
    "PAGE_FOOTER_HEIGHT",
    "POINTS_PER_MM",
    "chart_geometry",
    "plan_depth_pages",
]
