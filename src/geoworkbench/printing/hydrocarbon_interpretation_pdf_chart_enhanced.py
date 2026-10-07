from __future__ import annotations

from geoworkbench.printing.hydrocarbon_interpretation_curve_selection import chart_panel_render_options

from geoworkbench.printing.gas_ratio_reference import (
    ratio_identifier, ratio_reference_tracks, ratio_reference_color,
)

from geoworkbench.printing.gas_context_track import (
    context_segments, context_heading, paint_context_track, render_context_legend_pages,
)

from math import floor, isclose

import numpy as np
from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QPolygonF, QColor, QPainter, QPen

from geoworkbench.domain.depth_interval import scope_dataset
from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.domain.report_composition import (
    DEFAULT_REPORT_CHART_PANELS,
    ReportChartPanelSettings,
    ReportLegendMode,
)
from geoworkbench.domain.report_annotations import ReportAnnotationRecord
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
    GeologyLegendItem,
    InterpretationGeologyLegend,
    build_interpretation_geology_legend,
    geology_legend_height,
    paint_geology_legend,
    paginate_geology_legend,
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
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.printing.unicode_support import print_font
from geoworkbench.printing.report_annotation_rendering import (
    REFERENCE_PIXEL_TO_POINT,
    build_report_annotation_track_map,
    paint_report_annotations,
)
from geoworkbench.printing.interpretation_track_headings import (
    paint_track_heading,
    track_heading_height,
)
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonCandidateInterval,
    HydrocarbonInterpretationReport,
)
from geoworkbench.services.gas_curve_presentation import (
    gas_ratio_position,
    gas_ratio_scale_ticks,
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
    legend_mode: ReportLegendMode = ReportLegendMode.FULL,
    legend_reference_pages_emitted: bool = False,
    annotations: tuple[ReportAnnotationRecord, ...] = (),
    chart_panels: ReportChartPanelSettings = DEFAULT_REPORT_CHART_PANELS,
) -> None:
    """Render chart pages with printer-safe major and minor depth graduations."""

    interval = getattr(report, "analysis_depth_interval", None)
    depth_range = interval or depth_range
    dataset = scope_dataset(dataset, interval)
    depth = np.asarray(dataset.depth, dtype=np.float64)
    finite_depth = np.isfinite(depth)
    if depth.ndim != 1 or np.count_nonzero(finite_depth) < 2:
        return
    panels = tuple(
        (name, curves)
        for name, curves in base_chart._panel_curves(report, dataset, **chart_panel_render_options(chart_panels))
        if curves
    )
    if not panels:
        return

    depth_min = float(np.nanmin(depth[finite_depth]))
    depth_max = float(np.nanmax(depth[finite_depth]))
    if depth_range is not None:
        depth_min = depth_range.top_depth
        depth_max = depth_range.bottom_depth
    context = context_segments(getattr(report, "gas_context_events", ()), depth_min, depth_max)
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
    legend_compact = legend_mode is ReportLegendMode.COMPACT
    legend_hidden = legend_mode is ReportLegendMode.HIDE
    full_legend_height = (
        0.0
        if legend_hidden
        else geology_legend_height(
            canvas.content_rect.width(),
            geology_legend,
            compact=legend_compact,
            paint_device=canvas.painter.device(),
        )
    )
    provisional = chart_geometry(
        canvas.content_rect, DepthPage(depth_min, depth_max, 1000, MIN_CHART_HEIGHT),
        len(panels), geology_track_count=len(geology_tracks), context_track=bool(context),
    )
    headings = [
        (base_chart._labels(language)[name], rect.width(), 7.5)
        for (name, _curves), rect in zip(panels, provisional.panel_rects, strict=True)
    ]
    headings.extend(
        (_geology_track_labels(language)[name], rect.width(), 6.2)
        for name, rect in zip(geology_tracks, provisional.geology_rects, strict=True)
    )
    if provisional.context_rect is not None:
        headings.append((context_heading(language), provisional.context_rect.width(), 7.0 * 72.0 / canvas.painter.device().logicalDpiY()))
    headings.append((
        base_chart._labels(language)["depth"] + (f", {report.depth_unit}" if report.depth_unit else ""),
        provisional.left_axis_rect.width(), 7.4,
    ))
    header_height = max(CHART_TRACK_HEADER_HEIGHT, 20.0 + max(
        track_heading_height(text, width, size, canvas.painter.device())
        for text, width, size in headings
    ))
    chart_height_budget = (
        canvas.content_rect.height()
        - CHART_HEADER_HEIGHT
        - header_height
        - CHART_LEGEND_HEIGHT
        - CHART_NOTE_HEIGHT
    )
    # Preserve a useful plot even on A4 landscape. Large catalogs belong on
    # dedicated legend pages; do not let them consume the depth-page budget.
    legend_budget = max(0.0, chart_height_budget - 4.0 * MIN_CHART_HEIGHT)
    chart_legend = (
        InterpretationGeologyLegend(())
        if legend_hidden
        else geology_legend
    )
    deferred_legend_pages: tuple[InterpretationGeologyLegend, ...] = ()
    if not legend_hidden and full_legend_height > legend_budget:
        legend_pages = paginate_geology_legend(
            canvas.content_rect.width(), geology_legend, canvas.content_rect.height(),
            compact=legend_compact, paint_device=canvas.painter.device(),
        )
        if legend_reference_pages_emitted:
            # The full report keeps methodology before charts. Preserve an
            # overflowing legend after the charts instead of silently dropping it.
            deferred_legend_pages = legend_pages
        else:
            _render_geology_legend_pages(canvas, legend_pages, language, compact=legend_compact)
        reference = {
            AppLanguage.RU: "Легенда: отдельные страницы",
            AppLanguage.KK: "Легенда: бөлек беттер",
            AppLanguage.EN: "Legend: separate pages",
        }[language]
        chart_legend = InterpretationGeologyLegend((
            GeologyLegendItem("reference", "legend-pages", "", reference),
        ))
        full_legend_height = geology_legend_height(
            canvas.content_rect.width(), chart_legend, compact=legend_compact,
            paint_device=canvas.painter.device(),
        )
    available_height = chart_height_budget - full_legend_height
    pages = plan_depth_pages(
        depth_min,
        depth_max,
        available_height,
    )
    for page_index, page in enumerate(pages, start=1):
        canvas.new_page()
        percentiles = base_chart._curve_percentiles(panels, dataset, page=page)
        geometry = chart_geometry(
            canvas.content_rect,
            page,
            len(panels),
            geology_track_count=len(geology_tracks),
            geology_legend_height=full_legend_height,
            track_header_height=header_height,
            context_track=bool(context),
        )
        if annotations:
            if legend_compact:
                _draw_chart_page(
                    canvas.painter,
                    geometry,
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
                    chart_legend,
                    None,
                    annotations=annotations,
                    geology_legend_compact=True,
                )
            else:
                _draw_chart_page(
                    canvas.painter,
                    geometry,
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
                    chart_legend,
                    None,
                    annotations=annotations,
                )
        elif legend_compact:
            _draw_chart_page(
                canvas.painter,
                geometry,
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
                chart_legend,
                None,
                geology_legend_compact=True,
            )
        else:
            # Preserve the historical positional call contract for test/profiling
            # hooks that wrap _draw_chart_page without RPT-ANN keywords.
            _draw_chart_page(
                canvas.painter,
                geometry,
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
                chart_legend,
                None,
            )
        canvas.y = canvas.content_rect.bottom()
    _render_geology_legend_pages(canvas, deferred_legend_pages, language, compact=legend_compact)
    render_context_legend_pages(canvas, context, language, report.depth_unit)


def _render_geology_legend_pages(
    canvas: PageCanvas, pages: tuple[InterpretationGeologyLegend, ...],
    language: AppLanguage, *, compact: bool,
) -> None:
    for legend_page in pages:
        canvas.new_page()
        height = geology_legend_height(
            canvas.content_rect.width(), legend_page, compact=compact,
            paint_device=canvas.painter.device(),
        )
        paint_geology_legend(
            canvas.painter,
            QRectF(canvas.content_rect.left(), canvas.content_rect.top(), canvas.content_rect.width(), height),
            legend_page, language, compact=compact,
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
    palette = modern_oilfield_report_profile().palette
    labels = _geology_track_labels(language)
    page_samples = tuple(
        sample
        for sample in (geology.samples if geology is not None else ())
        if sample.bottom_depth >= page.top_depth
        and sample.top_depth <= page.bottom_depth
    )
    lithotypes = geology.lithotype_map if geology is not None else {}
    for track, rect in zip(geology_tracks, geometry.geology_rects, strict=True):
        painter.fillRect(rect, QColor(palette.page))
        heading = labels[track]
        paint_track_heading(
            painter,
            QRectF(rect.left(), rect.top() - geometry.track_header_height + 2.0,
                   rect.width(), geometry.track_header_height - 20.0),
            heading, 6.2,
        )
        for tick in minor_depth_ticks(page):
            y = base_chart._depth_y(tick, page, rect)
            painter.setPen(QPen(QColor(palette.border), 0.45))
            painter.drawLine(QLineF(rect.left(), y, rect.right(), y))
        for tick in base_chart._depth_ticks(
            page,
            base_chart._nice_tick_step(page.span, target_ticks=_MAJOR_TARGET_TICKS),
        ):
            y = base_chart._depth_y(tick, page, rect)
            painter.setPen(QPen(QColor(palette.border), 0.65))
            painter.drawLine(QLineF(rect.left(), y, rect.right(), y))
        if track in empty_state_tracks:
            no_data = {
                AppLanguage.RU: "Нет данных",
                AppLanguage.KK: "Дерек жоқ",
                AppLanguage.EN: "No data",
            }[language]
            painter.setPen(QColor(palette.text_muted))
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
    continuation_legend: InterpretationGeologyLegend | None = None,
    *,
    annotations: tuple[ReportAnnotationRecord, ...] = (),
    geology_legend_compact: bool = False,
) -> None:
    palette = modern_oilfield_report_profile().palette
    labels = base_chart._labels(language)
    title_font = print_font(15.0, text=labels["title"])
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.setPen(QColor(palette.text))
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
    painter.setPen(QColor(palette.text_secondary))
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
            compact=geology_legend_compact,
        )
    if geometry.geology_repeat_legend_rect is not None:
        paint_geology_legend(
            painter,
            geometry.geology_repeat_legend_rect,
            continuation_legend if continuation_legend is not None else geology_legend,
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
        header_height=geometry.track_header_height,
    )
    _draw_depth_axis(
        painter,
        geometry.right_axis_rect,
        page,
        report.depth_unit,
        side="right",
        language=language,
        header_height=geometry.track_header_height,
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
    if geometry.context_rect is not None:
        paint_context_track(painter, geometry.context_rect, getattr(report, "gas_context_events", ()), page.top_depth, page.bottom_depth, language, header_height=geometry.track_header_height)
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
            header_height=geometry.track_header_height,
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
            point_series=False,
        )

    _draw_fluid_markers(
        painter,
        geometry,
        page,
        candidates,
    )
    if annotations:
        track_map = build_report_annotation_track_map(
            panels=panels,
            panel_rects=geometry.panel_rects,
            geology_tracks=geology_tracks,
            geology_rects=geometry.geology_rects,
            left_depth_rect=geometry.left_axis_rect,
            right_depth_rect=geometry.right_axis_rect,
        )
        paint_report_annotations(
            painter,
            annotations,
            language,
            page_top_depth=page.top_depth,
            page_bottom_depth=page.bottom_depth,
            plot_bounds=QRectF(
                geometry.left_axis_rect.left(),
                geometry.left_axis_rect.top(),
                geometry.right_axis_rect.right() - geometry.left_axis_rect.left(),
                geometry.left_axis_rect.height(),
            ),
            track_map=track_map,
            pixel_scale=REFERENCE_PIXEL_TO_POINT,
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
    header_height: float = CHART_TRACK_HEADER_HEIGHT,
) -> None:
    palette = modern_oilfield_report_profile().palette
    labels = base_chart._labels(language)
    painter.fillRect(rect, QColor(palette.page))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(palette.border_strong), 1.15))
    painter.drawRect(rect)
    title = labels["depth"] + (f", {unit}" if unit else "")
    paint_track_heading(
        painter,
        QRectF(rect.left(), rect.top() - header_height + 2.0,
               rect.width(), header_height - 20.0),
        title, 7.4,
    )

    for value in minor_depth_ticks(page):
        y = base_chart._depth_y(value, page, rect)
        painter.setPen(QPen(QColor(palette.border), 0.55))
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
        painter.setPen(QPen(QColor(palette.border_strong), 1.05))
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
        painter.setPen(QColor(palette.text))
        painter.drawText(
            text_rect,
            alignment,
            base_chart._depth_label(value, major_step),
        )
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(palette.border_strong), 1.15))
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
    *,
    header_height: float = CHART_TRACK_HEADER_HEIGHT,
) -> None:
    palette = modern_oilfield_report_profile().palette
    if panel_name == "ratios" and _draw_ratio_tracks(
        painter,
        rect,
        page,
        dataset,
        curves,
        candidates,
        language,
        header_height=header_height,
    ):
        return

    painter.fillRect(rect, QColor(palette.page))
    for tick in minor_depth_ticks(page):
        y = base_chart._depth_y(tick, page, rect)
        painter.setPen(QPen(QColor(palette.border), 0.55))
        painter.drawLine(QLineF(rect.left(), y, rect.right(), y))

    major_step = base_chart._nice_tick_step(
        page.span,
        target_ticks=_MAJOR_TARGET_TICKS,
    )
    for tick in base_chart._depth_ticks(page, major_step):
        y = base_chart._depth_y(tick, page, rect)
        painter.setPen(QPen(QColor(palette.border_strong), 0.92))
        painter.drawLine(QLineF(rect.left(), y, rect.right(), y))

    for index in range(5):
        x = rect.left() + index / 4.0 * rect.width()
        painter.setPen(QPen(QColor(palette.border), 0.58))
        painter.drawLine(QLineF(x, rect.top(), x, rect.bottom()))
        painter.setFont(print_font(6.2, text="100"))
        painter.setPen(QColor(palette.text_secondary))
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
    paint_track_heading(
        painter,
        QRectF(rect.left(), rect.top() - header_height + 2.0,
               rect.width(), header_height - 20.0),
        heading, 7.5,
    )
    if not any(curve.metadata.curve_id in ranges for curve in curves):
        painter.setPen(QColor(palette.text_muted))
        label = base_chart._labels(language)["no_data"]
        painter.setFont(print_font(8.0, text=label))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
    else:
        base_chart._draw_curves(
            painter,
            rect,
            page,
            dataset,
            curves,
            ranges,
            point_series=False,
        )
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(palette.border_strong), 1.1))
    painter.drawRect(rect)



def _draw_ratio_tracks(
    painter: QPainter,
    rect: QRectF,
    page: DepthPage,
    dataset: Dataset,
    curves: tuple[CurveData, ...],
    candidates: tuple[HydrocarbonCandidateInterval, ...],
    language: AppLanguage,
    *,
    header_height: float,
) -> bool:
    """Draw Wh/Bh on a shared axis and Ch on its own reference axis."""
    palette = modern_oilfield_report_profile().palette

    tracks = ratio_reference_tracks(curves)
    if not tracks:
        return False

    painter.fillRect(rect, QColor(palette.page))
    _draw_candidate_bands(painter, rect, page, candidates)

    heading = base_chart._labels(language)["ratios"]
    paint_track_heading(
        painter,
        QRectF(
            rect.left(),
            rect.top() - header_height + 1.0,
            rect.width(),
            max(10.0, header_height - 30.0),
        ),
        heading,
        6.8,
    )

    depth = np.asarray(dataset.depth, dtype=np.float64)
    finite_depth = np.isfinite(depth)
    indices = np.flatnonzero(
        finite_depth
        & (depth >= page.top_depth)
        & (depth <= page.bottom_depth)
    )
    indices = indices[np.argsort(depth[indices], kind="stable")]
    lane_count = max(group for _, _, group in tracks) + 1
    lane_width = rect.width() / lane_count
    for curve, scale, lane_index in tracks:
        lane = QRectF(
            rect.left() + lane_index * lane_width,
            rect.top(),
            lane_width,
            rect.height(),
        )
        for tick in minor_depth_ticks(page):
            y = base_chart._depth_y(tick, page, lane)
            painter.setPen(QPen(QColor(palette.border), 0.42))
            painter.drawLine(QLineF(lane.left(), y, lane.right(), y))
        for tick in base_chart._depth_ticks(
            page,
            base_chart._nice_tick_step(page.span, target_ticks=_MAJOR_TARGET_TICKS),
        ):
            y = base_chart._depth_y(tick, page, lane)
            painter.setPen(QPen(QColor(palette.border), 0.62))
            painter.drawLine(QLineF(lane.left(), y, lane.right(), y))

        scale_ticks = gas_ratio_scale_ticks(scale)
        for fraction, label in scale_ticks:
            x = lane.left() + fraction * lane.width()
            painter.setPen(QPen(QColor(palette.border), 0.45))
            painter.drawLine(QLineF(x, lane.top(), x, lane.bottom()))

        mnemonic = (
            curve.metadata.canonical_mnemonic
            or curve.metadata.original_mnemonic
            or "ratio"
        ).replace("PIXLER_", "").replace("_", "/")
        if ratio_identifier(curve) in {"WH", "BH"}:
            mnemonic = "Wh / Bh"
        painter.setFont(print_font(5.1, text=mnemonic))
        painter.setPen(QColor(palette.text))
        painter.drawText(
            QRectF(lane.left(), lane.top() - 28.0, lane.width(), 9.0),
            Qt.AlignmentFlag.AlignCenter,
            mnemonic,
        )

        labelled = (
            scale_ticks
            if len(scale_ticks) <= 3
            else (scale_ticks[0], scale_ticks[len(scale_ticks) // 2], scale_ticks[-1])
        )
        painter.setFont(print_font(4.4, text="1000"))
        painter.setPen(QColor(palette.text_secondary))
        for fraction, label in labelled:
            x = lane.left() + fraction * lane.width()
            text_width = min(25.0, max(12.0, lane.width() * 0.46))
            painter.drawText(
                QRectF(
                    min(max(x - text_width / 2.0, lane.left()), lane.right() - text_width),
                    lane.top() - 17.5,
                    text_width,
                    8.0,
                ),
                Qt.AlignmentFlag.AlignCenter,
                label,
            )

        values = np.asarray(curve.values, dtype=np.float64)
        if values.shape == depth.shape:
            usable = np.isfinite(values[indices])
            if scale.logarithmic:
                usable &= values[indices] > 0.0
            valid_runs = np.split(indices, np.flatnonzero(usable[1:] != usable[:-1]) + 1)
            curve_segments = tuple(
                segment
                for run in valid_runs
                if run.size and np.isfinite(values[run[0]])
                and (not scale.logarithmic or values[run[0]] > 0.0)
                for segment in base_chart.continuous_depth_segments(
                    depth, run, limit=max(2, int(run.size))
                )
            )
            color = ratio_reference_color(curve)
            pen = QPen(color, 0.7, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            painter.save()
            painter.setClipRect(lane.adjusted(0.6, 0.6, -0.6, -0.6))
            painter.setPen(pen)
            for segment in curve_segments:
                render_rows = base_chart._extrema_preserving_print_rows(
                    segment,
                    depth,
                    values,
                    page,
                    lane,
                )
                points: list[QPointF] = []
                for row_index in render_rows:
                    position = gas_ratio_position(float(values[row_index]), scale)
                    if position is None:
                        continue
                    points.append(
                        QPointF(
                            lane.left() + position * lane.width(),
                            base_chart._depth_y(float(depth[row_index]), page, lane),
                        )
                    )
                if len(points) == 1:
                    painter.setBrush(color)
                    painter.drawEllipse(points[0], 0.75, 0.75)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                else:
                    painter.drawPolyline(QPolygonF(points))
            painter.restore()

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(palette.text_secondary), 0.7))
        painter.drawRect(lane)

    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(palette.border_strong), 1.1))
    painter.drawRect(rect)
    return True


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
    palette = modern_oilfield_report_profile().palette
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
            fill = QColor(palette.page)
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
            painter.setPen(QColor(palette.text))
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
        halo = QColor(palette.page)
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
    palette = modern_oilfield_report_profile().palette
    visible = _visible_candidates(page, candidates)
    specs = fluid_marker_legend_specs(
        [item.fluid_hypothesis for item in visible]
    )
    if not specs:
        painter.setPen(QColor(palette.text_secondary))
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
        painter.setPen(QColor(palette.text))
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
    painter.setPen(QColor(palette.text_muted))
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
