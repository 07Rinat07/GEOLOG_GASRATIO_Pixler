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
_MIN_PLOT_UTILIZATION = 0.82
_MAX_TARGET_DEPTH_OVERSHOOT = 1.05
MAX_AUTOMATIC_CHART_PAGES = 80
TARGET_DEPTH_PER_PAGE = 100.0
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
    geology_rects: tuple[QRectF, ...] = ()
    geology_legend_rect: QRectF | None = None
    geology_repeat_legend_rect: QRectF | None = None
    track_header_height: float = CHART_TRACK_HEADER_HEIGHT
    context_rect: QRectF | None = None


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
    readable_page_span = TARGET_DEPTH_PER_PAGE * _MAX_TARGET_DEPTH_OVERSHOOT
    desired_pages = min(max_pages, max(1, int(ceil(span / readable_page_span))))
    required_scale = span * 1_000.0 / (height_mm * desired_pages)
    scale = _fit_scale_denominator(required_scale)

    # Keep every sheet equally dense instead of leaving a short, half-empty
    # remainder page.  The selected denominator is always >= required_scale,
    # so the evenly distributed page span remains inside the printable height.
    depth_capacity = height_mm * scale / 1_000.0
    page_count = min(max_pages, max(1, int(ceil(span / depth_capacity))))
    page_span = span / page_count
    plot_height_mm = page_span * 1_000.0 / scale
    utilization = plot_height_mm / height_mm
    if utilization < _MIN_PLOT_UTILIZATION and page_count < max_pages:
        # One more page with a tighter denominator often gives a materially
        # larger plot for short/intermediate report intervals.
        candidate_count = page_count + 1
        candidate_required = span * 1_000.0 / (height_mm * candidate_count)
        candidate_scale = _fit_scale_denominator(candidate_required)
        candidate_span = span / candidate_count
        candidate_height_mm = candidate_span * 1_000.0 / candidate_scale
        candidate_utilization = candidate_height_mm / height_mm
        if candidate_utilization > utilization:
            page_count = candidate_count
            scale = candidate_scale
            page_span = candidate_span
            plot_height_mm = candidate_height_mm

    pages: list[DepthPage] = []
    for index in range(page_count):
        top = low + index * page_span
        bottom = high if index == page_count - 1 else low + (index + 1) * page_span
        actual_span = bottom - top
        actual_height_mm = actual_span * 1_000.0 / scale
        pages.append(
            DepthPage(
                top,
                bottom,
                scale,
                actual_height_mm * POINTS_PER_MM,
            )
        )
    return tuple(pages)


def _fit_scale_denominator(required_scale: float) -> int:
    """Round up just enough to fit instead of jumping to a coarse scale tier."""

    if not np.isfinite(required_scale) or required_scale <= 0.0:
        return STANDARD_DEPTH_SCALES[0]
    if required_scale <= 1_000.0:
        step = 25.0
    elif required_scale <= 5_000.0:
        step = 100.0
    elif required_scale <= 20_000.0:
        step = 500.0
    else:
        step = 1_000.0
    return max(1, int(ceil(required_scale / step) * step))


def chart_geometry(
    content_rect: QRectF,
    page: DepthPage,
    panel_count: int,
    *,
    geology_track_count: int = 0,
    geology_legend_height: float = 0.0,
    geology_repeat_legend_height: float = 0.0,
    track_header_height: float = CHART_TRACK_HEADER_HEIGHT,
    context_track: bool = False,
) -> ChartGeometry:
    """Return chart rectangles guaranteed to remain inside the printable area."""

    if panel_count < 1:
        raise ValueError("Для графика требуется хотя бы одна дорожка")
    safe_legend_height = max(0.0, float(geology_legend_height))
    safe_repeat_height = max(0.0, float(geology_repeat_legend_height))
    safe_header_height = max(CHART_TRACK_HEADER_HEIGHT, float(track_header_height))
    geology_legend_rect = (
        QRectF(
            content_rect.left(),
            content_rect.top() + CHART_HEADER_HEIGHT,
            content_rect.width(),
            safe_legend_height,
        )
        if safe_legend_height > 0.0
        else None
    )
    chart_top = (
        content_rect.top()
        + CHART_HEADER_HEIGHT
        + safe_legend_height
        + safe_header_height
    )
    maximum_plot_height = max(
        MIN_CHART_HEIGHT,
        content_rect.height()
        - CHART_HEADER_HEIGHT
        - safe_header_height
        - CHART_LEGEND_HEIGHT
        - CHART_NOTE_HEIGHT
        - safe_legend_height
        - safe_repeat_height,
    )
    plot_height = min(
        maximum_plot_height,
        max(MIN_CHART_HEIGHT, page.plot_height_points),
    )
    axis_width = 54.0
    axis_gap = 7.0
    panel_gap = 8.0
    geology_track_width = 42.0
    geology_gap = 4.0
    left_axis = QRectF(content_rect.left(), chart_top, axis_width, plot_height)
    right_axis = QRectF(
        content_rect.right() - axis_width,
        chart_top,
        axis_width,
        plot_height,
    )
    geology_left = left_axis.right() + axis_gap
    geology_rects = tuple(
        QRectF(
            geology_left + index * (geology_track_width + geology_gap),
            chart_top,
            geology_track_width,
            plot_height,
        )
        for index in range(max(0, geology_track_count))
    )
    geology_right = (
        geology_rects[-1].right() + axis_gap
        if geology_rects
        else left_axis.right() + axis_gap
    )
    context_rect = QRectF(geology_right, chart_top, 48.0, plot_height) if context_track else None
    panels_left = context_rect.right() + axis_gap if context_rect is not None else geology_right
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
    repeat_legend = (
        QRectF(
            content_rect.left(),
            chart_top + plot_height + CHART_LEGEND_HEIGHT,
            content_rect.width(),
            safe_repeat_height,
        )
        if safe_repeat_height > 0.0
        else None
    )
    note = QRectF(
        content_rect.left(),
        content_rect.bottom() - CHART_NOTE_HEIGHT,
        content_rect.width(),
        CHART_NOTE_HEIGHT,
    )
    plot_left = geology_rects[0].left() if geology_rects else context_rect.left() if context_rect is not None else panels_left
    return ChartGeometry(
        content_rect,
        QRectF(plot_left, chart_top, panels_right - plot_left, plot_height),
        left_axis,
        right_axis,
        panel_rects,
        legend,
        note,
        geology_rects,
        geology_legend_rect,
        repeat_legend,
        safe_header_height,
        context_rect,
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
