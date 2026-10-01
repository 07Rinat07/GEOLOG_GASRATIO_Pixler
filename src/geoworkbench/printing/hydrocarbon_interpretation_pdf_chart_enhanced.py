from __future__ import annotations

from math import floor, isclose

import numpy as np
from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart as base_chart
from geoworkbench.printing.hydrocarbon_fluid_markers import (
    draw_fluid_marker,
    fluid_marker_legend_specs,
    fluid_marker_spec,
    marker_lane_offsets,
    marker_lanes,
)
from geoworkbench.printing.hydrocarbon_interpretation_curve_labels import (
    report_curve_label_hints,
)
from geoworkbench.printing.geology_track_rendering import (
    paint_cuttings_track,
    paint_lba_track,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology import (
    InterpretationGeologySnapshot,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology_legend import (
    InterpretationGeologyLegend,
    build_interpretation_geology_legend,
    geology_legend_height,
    paint_geology_legend,
    split_geology_legend_pages,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology_settings import (
    DEFAULT_INTERPRETATION_GEOLOGY_TRACK_SETTINGS,
    InterpretationGeologyTrackSettings,
    forced_empty_geology_tracks,
    resolve_geology_track_kinds,
)
from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import (
    CHART_HEADER_HEIGHT,
    CHART_LEGEND_HEIGHT,
    CHART_NOTE_HEIGHT,
    CHART_TRACK_HEADER_HEIGHT,
    MIN_CHART_HEIGHT,
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
    HydrocarbonCandidateInterval,
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
    geology: InterpretationGeologySnapshot | None = None,
    geology_track_settings: InterpretationGeologyTrackSettings = (
        DEFAULT_INTERPRETATION_GEOLOGY_TRACK_SETTINGS
    ),
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

    depth_min = float(np.nanmin(depth[finite_depth]))
    depth_max = float(np.nanmax(depth[finite_depth]))
    if depth_range is not None:
        depth_min = depth_range.top_depth
        depth_max = depth_range.bottom_depth
    geology_tracks = _geology_track_kinds(
        geology,
        depth_min,
        depth_max,
        geology_track_settings,
    )
    empty_state_tracks = _forced_empty_geology_tracks(
        geology,
        depth_min,
        depth_max,
        geology_track_settings,
    )
    geology_legend = build_interpretation_geology_legend(
        geology,
        depth_min,
        depth_max,
        language,
        include_cuttings="cuttings" in geology_tracks,
        include_lba="lba" in geology_tracks,
    )
    full_legend_height = geology_legend_height(
        canvas.content_rect.width(),
        geology_legend,
    )
    repeat_legend_height = geology_legend_height(
        canvas.content_rect.width(),
        geology_legend,
        compact=True,
    )
    base_reserved_height = (
        CHART_HEADER_HEIGHT
        + CHART_TRACK_HEADER_HEIGHT
        + CHART_LEGEND_HEIGHT
        + CHART_NOTE_HEIGHT
    )
    max_inline_legend_height = max(
        0.0,
        canvas.content_rect.height()
        - base_reserved_height
        - MIN_CHART_HEIGHT,
    )
    dedicated_legend_pages: tuple[InterpretationGeologyLegend, ...] = ()
    inline_full_legend_height = full_legend_height
    if (
        not geology_legend.empty
        and full_legend_height > max_inline_legend_height
    ):
        dedicated_legend_pages = split_geology_legend_pages(
            canvas.content_rect.width(),
            geology_legend,
            max(1.0, canvas.content_rect.height() - 12.0),
        )
        inline_full_legend_height = 0.0
        _render_geology_legend_pages(
            canvas,
            dedicated_legend_pages,
            language,
        )

    chart_legend_reserve = (
        repeat_legend_height
        if dedicated_legend_pages
        else max(inline_full_legend_height, repeat_legend_height)
    )
    available_height = (
        canvas.content_rect.height()
        - base_reserved_height
        - chart_legend_reserve
    )
    pages = plan_depth_pages(
        depth_min,
        depth_max,
        available_height,
    )
    for page_index, page in enumerate(pages, start=1):
        canvas.new_page()
        percentiles = base_chart._curve_percentiles(panels, dataset, page=page)
        first_page = page_index == 1
        first_page_legend_height = (
            inline_full_legend_height
            if first_page and not dedicated_legend_pages
            else 0.0
        )
        continuation_legend_height = (
            repeat_legend_height
            if dedicated_legend_pages or not first_page
            else 0.0
        )
        _draw_chart_page(
            canvas.painter,
            chart_geometry(
                canvas.content_rect,
                page,
                len(panels),
                geology_track_count=len(geology_tracks),
                geology_legend_height=first_page_legend_height,
                geology_repeat_legend_height=continuation_legend_height,
            ),
            page,
            page_index,
            len(pages),
            report,
            dataset,
            panels,
            base_chart._display_curve_ranges(percentiles),
            percentiles,
            language,
            geology,
            geology_tracks,
            empty_state_tracks,
            geology_legend,
        )
        canvas.y = canvas.content_rect.bottom()


def _render_geology_legend_pages(
    canvas: PageCanvas,
    pages: tuple[InterpretationGeologyLegend, ...],
    language: AppLanguage,
) -> None:
    for legend_page in pages:
        canvas.new_page()
        height = geology_legend_height(
            canvas.content_rect.width(),
            legend_page,
        )
        rect = QRectF(
            canvas.content_rect.left(),
            canvas.content_rect.top() + 6.0,
            canvas.content_rect.width(),
            height,
        )
        paint_geology_legend(
            canvas.painter,
            rect,
            legend_page,
            language,
        )
        canvas.y = canvas.content_rect.bottom()


def _geology_track_kinds(
    geology: InterpretationGeologySnapshot | None,
    top_depth: float,
    bottom_depth: float,
    settings: InterpretationGeologyTrackSettings,
) -> tuple[str, ...]:
    return resolve_geology_track_kinds(
        geology,
        top_depth,
        bottom_depth,
        settings,
    )


def _forced_empty_geology_tracks(
    geology: InterpretationGeologySnapshot | None,
    top_depth: float,
    bottom_depth: float,
    settings: InterpretationGeologyTrackSettings,
) -> tuple[str, ...]:
    return forced_empty_geology_tracks(
        geology,
        top_depth,
        bottom_depth,
        settings,
    )


def _geology_track_labels(language: AppLanguage) -> dict[str, str]:
    if language is AppLanguage.KK:
        return {"cuttings": "Шламограмма", "lba": "ЛБА"}
    if language is AppLanguage.EN:
        return {"cuttings": "Cuttings", "lba": "LBA"}
    return {"cuttings": "Шламограмма", "lba": "ЛБА"}


def _draw_geology_tracks(
    painter: QPainter,
    geometry: ChartGeometry,
    page: DepthPage,
    geology: InterpretationGeologySnapshot | None,
    geology_tracks: tuple[str, ...],
    empty_state_tracks: tuple[str, ...],
    language: AppLanguage,
) -> None:
    labels = _geology_track_labels(language)
    page_samples = tuple(
        sample
        for sample in (geology.samples if geology is not None else ())
        if sample.bottom_depth >= page.top_depth
        and sample.top_depth <= page.bottom_depth
    )
    lithotypes = geology.lithotype_map if geology is not None else {}
    for track, rect in zip(geology_tracks, geometry.geology_rects, strict=True):
        painter.fillRect(rect, QColor("#ffffff"))
        heading = labels[track]
        font = print_font(6.2, text=heading)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#172033"))
        painter.drawText(
            QRectF(rect.left(), rect.top() - 33.0, rect.width(), 28.0),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            heading,
        )
        for tick in minor_depth_ticks(page):
            y = base_chart._depth_y(tick, page, rect)
            painter.setPen(QPen(QColor("#e2e8f0"), 0.45))
            painter.drawLine(QLineF(rect.left(), y, rect.right(), y))
        for tick in base_chart._depth_ticks(
            page,
            base_chart._nice_tick_step(page.span, target_ticks=_MAJOR_TARGET_TICKS),
        ):
            y = base_chart._depth_y(tick, page, rect)
            painter.setPen(QPen(QColor("#cbd5e1"), 0.65))
            painter.drawLine(QLineF(rect.left(), y, rect.right(), y))
        if track in empty_state_tracks:
            no_data = {
                AppLanguage.RU: "Нет данных",
                AppLanguage.KK: "Дерек жоқ",
                AppLanguage.EN: "No data",
            }[language]
            painter.setPen(QColor("#64748b"))
            painter.setFont(print_font(6.0, text=no_data))
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                no_data,
            )
        elif track == "cuttings":
            paint_cuttings_track(
                painter,
                rect,
                page_samples,
                (page.top_depth, page.bottom_depth),
                lithotypes,
            )
        else:
            paint_lba_track(
                painter,
                rect,
                page_samples,
                (page.top_depth, page.bottom_depth),
            )


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
    percentiles: dict[str, tuple[float, float]],
    language: AppLanguage,
    geology: InterpretationGeologySnapshot | None,
    geology_tracks: tuple[str, ...],
    empty_state_tracks: tuple[str, ...],
    geology_legend: InterpretationGeologyLegend,
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

    if geometry.geology_legend_rect is not None:
        paint_geology_legend(
            painter,
            geometry.geology_legend_rect,
            geology_legend,
            language,
        )
    if geometry.geology_repeat_legend_rect is not None:
        paint_geology_legend(
            painter,
            geometry.geology_repeat_legend_rect,
            geology_legend,
            language,
            compact=True,
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
    if geology_tracks:
        _draw_geology_tracks(
            painter,
            geometry,
            page,
            geology,
            geology_tracks,
            empty_state_tracks,
            language,
        )
    candidates = tuple(report.candidates)
    display_hints = report_curve_label_hints(report)
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
            candidates,
            language,
        )
        base_chart._draw_legend(
            painter,
            geometry.legend_rect,
            panel_index,
            len(panels),
            curves,
            percentiles,
            language=language,
            display_hints=display_hints,
        )

    _draw_fluid_markers(
        painter,
        geometry,
        page,
        candidates,
    )
    _draw_fluid_marker_legend(
        painter,
        geometry.note_rect,
        page,
        candidates,
        language,
        fallback_note=labels["note"],
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
    painter.setBrush(Qt.BrushStyle.NoBrush)
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
    painter.setBrush(Qt.BrushStyle.NoBrush)
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
    candidates: tuple[HydrocarbonCandidateInterval, ...],
    language: AppLanguage,
) -> None:
    painter.fillRect(rect, QColor("#ffffff"))
    for tick in minor_depth_ticks(page):
        y = base_chart._depth_y(tick, page, rect)
        painter.setPen(QPen(QColor("#d4dde6"), 0.55))
        painter.drawLine(QLineF(rect.left(), y, rect.right(), y))

    major_step = base_chart._nice_tick_step(
        page.span,
        target_ticks=_MAJOR_TARGET_TICKS,
    )
    for tick in base_chart._depth_ticks(page, major_step):
        y = base_chart._depth_y(tick, page, rect)
        painter.setPen(QPen(QColor("#8fa3b5"), 0.92))
        painter.drawLine(QLineF(rect.left(), y, rect.right(), y))

    for index in range(5):
        x = rect.left() + index / 4.0 * rect.width()
        painter.setPen(QPen(QColor("#c4d0db"), 0.58))
        painter.drawLine(QLineF(x, rect.top(), x, rect.bottom()))
        painter.setFont(print_font(6.2, text="100"))
        painter.setPen(QColor("#475569"))
        label_left = (
            rect.left() + 2.0 if index == 0 else rect.right() - 30.0 if index == 4 else x - 14.0
        )
        painter.drawText(
            QRectF(label_left, rect.top() - 19.0, 28.0, 12.0),
            Qt.AlignmentFlag.AlignCenter,
            str(index * 25),
        )

    _draw_candidate_bands(painter, rect, page, candidates)
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
    if not any(curve.metadata.curve_id in ranges for curve in curves):
        painter.setPen(QColor("#64748b"))
        label = base_chart._labels(language)["no_data"]
        painter.setFont(print_font(8.0, text=label))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
    else:
        base_chart._draw_curves(painter, rect, page, dataset, curves, ranges)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor("#263746"), 1.1))
    painter.drawRect(rect)



def _draw_candidate_bands(
    painter: QPainter,
    rect: QRectF,
    page: DepthPage,
    candidates: tuple[HydrocarbonCandidateInterval, ...],
) -> None:
    for candidate in candidates:
        overlap_top = max(
            page.top_depth,
            min(candidate.top_depth, candidate.bottom_depth),
        )
        overlap_bottom = min(
            page.bottom_depth,
            max(candidate.top_depth, candidate.bottom_depth),
        )
        if overlap_bottom <= overlap_top:
            continue
        spec = fluid_marker_spec(candidate.fluid_hypothesis)
        band_color = QColor(spec.color)
        band_color.setAlpha(12)
        y1 = base_chart._depth_y(overlap_top, page, rect)
        y2 = base_chart._depth_y(overlap_bottom, page, rect)
        painter.fillRect(
            QRectF(
                rect.left(),
                min(y1, y2),
                rect.width(),
                max(1.0, abs(y2 - y1)),
            ),
            band_color,
        )
        painter.setPen(QPen(QColor(spec.color), 0.65))
        painter.drawLine(QLineF(rect.left(), y1, rect.right(), y1))
        painter.drawLine(QLineF(rect.left(), y2, rect.right(), y2))



def _visible_candidates(
    page: DepthPage,
    candidates: tuple[HydrocarbonCandidateInterval, ...],
) -> tuple[HydrocarbonCandidateInterval, ...]:
    return tuple(
        candidate
        for candidate in candidates
        if min(candidate.top_depth, candidate.bottom_depth) < page.bottom_depth
        and max(candidate.top_depth, candidate.bottom_depth) > page.top_depth
    )


def _draw_fluid_markers(
    painter: QPainter,
    geometry: ChartGeometry,
    page: DepthPage,
    candidates: tuple[HydrocarbonCandidateInterval, ...],
) -> None:
    """Draw compact fluid markers without leaking QPainter state to later pages."""

    if not geometry.panel_rects:
        return
    visible = _visible_candidates(page, candidates)
    if not visible:
        return

    painter.save()
    try:
        _draw_visible_fluid_markers(
            painter,
            geometry,
            page,
            visible,
        )
    finally:
        painter.restore()


def _draw_visible_fluid_markers(
    painter: QPainter,
    geometry: ChartGeometry,
    page: DepthPage,
    visible: tuple[HydrocarbonCandidateInterval, ...],
) -> None:
    target = geometry.panel_rects[-1]
    y_positions = tuple(
        base_chart._depth_y(
            (
                max(page.top_depth, min(item.top_depth, item.bottom_depth))
                + min(page.bottom_depth, max(item.top_depth, item.bottom_depth))
            )
            / 2.0,
            page,
            target,
        )
        for item in visible
    )
    zone_width = min(126.0, max(50.0, target.width() * 0.50))
    badge_width = 34.0
    badge_height = 11.0
    badge_gap = 3.0
    badge_centers = tuple(
        min(
            max(y, target.top() + badge_height / 2.0 + 1.0),
            target.bottom() - badge_height / 2.0 - 1.0,
        )
        for y in y_positions
    )
    coded_lanes = marker_lanes(
        badge_centers,
        minimum_gap=badge_height + 1.0,
    )
    coded_lane_count = max(coded_lanes, default=0) + 1
    show_codes = coded_lane_count * (badge_width + badge_gap) <= zone_width

    if show_codes:
        for candidate, center_y, lane in zip(
            visible,
            badge_centers,
            coded_lanes,
            strict=True,
        ):
            spec = fluid_marker_spec(candidate.fluid_hypothesis)
            box_right = target.right() - 4.0 - lane * (badge_width + badge_gap)
            box = QRectF(
                box_right - badge_width,
                center_y - badge_height / 2.0,
                badge_width,
                badge_height,
            )
            fill = QColor("#ffffff")
            fill.setAlpha(238)
            painter.fillRect(box, fill)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(spec.color), 0.75))
            painter.drawRoundedRect(box, 2.0, 2.0)
            draw_fluid_marker(
                painter,
                QPointF(box.left() + 6.0, box.center().y()),
                spec,
                size=5.0,
            )
            font = print_font(5.5, text=spec.code)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor("#172033"))
            painter.drawText(
                QRectF(
                    box.left() + 11.0,
                    box.top(),
                    box.width() - 13.0,
                    box.height(),
                ),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                spec.code,
            )
        return

    marker_centers = tuple(
        min(max(y, target.top() + 3.0), target.bottom() - 3.0)
        for y in y_positions
    )
    marker_lanes_by_y = marker_lanes(marker_centers, minimum_gap=5.5)
    marker_lane_count = max(marker_lanes_by_y, default=0) + 1
    offsets = marker_lane_offsets(
        marker_lane_count,
        zone_width=zone_width,
        max_spacing=12.0,
    )
    lane_spacing = offsets[1] - offsets[0] if len(offsets) > 1 else min(12.0, zone_width)
    marker_size = max(2.5, min(5.5, lane_spacing * 0.62))
    for candidate, y, lane in zip(
        visible,
        marker_centers,
        marker_lanes_by_y,
        strict=True,
    ):
        spec = fluid_marker_spec(candidate.fluid_hypothesis)
        x = target.right() - 4.0 - offsets[lane]
        halo = QColor("#ffffff")
        halo.setAlpha(220)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(
            QRectF(
                x - marker_size / 2.0 - 1.4,
                y - marker_size / 2.0 - 1.4,
                marker_size + 2.8,
                marker_size + 2.8,
            )
        )
        draw_fluid_marker(
            painter,
            QPointF(x, y),
            spec,
            size=marker_size,
        )


def _draw_fluid_marker_legend(
    painter: QPainter,
    rect: QRectF,
    page: DepthPage,
    candidates: tuple[HydrocarbonCandidateInterval, ...],
    language: AppLanguage,
    *,
    fallback_note: str,
) -> None:
    visible = _visible_candidates(page, candidates)
    specs = fluid_marker_legend_specs(
        [item.fluid_hypothesis for item in visible]
    )
    if not specs:
        painter.setPen(QColor("#475569"))
        painter.setFont(print_font(6.8, text=fallback_note))
        painter.drawText(
            rect,
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignTop
            | Qt.TextFlag.TextWordWrap,
            fallback_note,
        )
        return

    columns = min(6, len(specs))
    rows = (len(specs) + columns - 1) // columns
    row_height = 9.0
    cell_width = rect.width() / columns
    legend_font = print_font(5.2, text="GC/GO heavy/residual oil")
    painter.setFont(legend_font)
    for index, spec in enumerate(specs):
        row = index // columns
        column = index % columns
        left = rect.left() + column * cell_width
        center_y = rect.top() + row * row_height + row_height / 2.0
        draw_fluid_marker(
            painter,
            QPointF(left + 4.0, center_y),
            spec,
            size=4.4,
        )
        painter.setPen(QColor("#172033"))
        painter.drawText(
            QRectF(left + 8.0, center_y - 4.2, cell_width - 9.0, 8.4),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"{spec.code} {spec.label(language)}",
        )

    note = {
        AppLanguage.RU: (
            "Маркеры показывают предварительный тип; полные глубины и формулировки — "
            "в таблице. Кривые масштабированы по p5–p95 каждого листа."
        ),
        AppLanguage.KK: (
            "Маркерлер алдын ала түрді көрсетеді; толық тереңдік пен мәтін кестеде. "
            "Қисықтар әр бетте p5–p95 бойынша масштабталған."
        ),
        AppLanguage.EN: (
            "Markers show preliminary type; full depths and wording are in the table. "
            "Curves are scaled to each page's p5–p95."
        ),
    }[language]
    note_top = rect.top() + rows * row_height + 0.5
    painter.setPen(QColor("#526579"))
    painter.setFont(print_font(4.9, text=note))
    painter.drawText(
        QRectF(
            rect.left(),
            note_top,
            rect.width(),
            max(0.0, rect.bottom() - note_top),
        ),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
        note,
    )


__all__ = [
    "major_depth_ticks",
    "minor_depth_ticks",
    "render_chart_pages",
]
