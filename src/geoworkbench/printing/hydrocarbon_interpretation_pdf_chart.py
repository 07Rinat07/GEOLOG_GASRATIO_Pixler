from __future__ import annotations

from geoworkbench.printing.hydrocarbon_interpretation_curve_selection import chart_panel_render_options

from geoworkbench.printing.gas_context_track import (
    context_segments, context_heading, paint_context_track, render_context_legend_pages,
)

from math import ceil, floor, log10

import numpy as np
from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from geoworkbench.domain.report_composition import (
    DEFAULT_REPORT_CHART_PANELS,
    ReportChartPanelSettings,
)
from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.printing.hydrocarbon_interpretation_curve_labels import (
    curve_legend_text,
    report_curve_label_hints,
)
from geoworkbench.printing.hydrocarbon_fluid_markers import (
    draw_fluid_marker,
    fluid_marker_spec,
)
from geoworkbench.printing.hydrocarbon_interpretation_curve_selection import report_curve_panels
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
from geoworkbench.printing.depth_curve_segments import continuous_depth_segments
from geoworkbench.printing.unicode_support import print_font
from geoworkbench.printing.interpretation_track_headings import (
    paint_track_heading,
    track_heading_height,
)
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonCandidateInterval,
    HydrocarbonInterpretationReport,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.gas_curve_presentation import (
    GAS_PRINT_POINT_RADIUS_PT,
    gas_scatter_point_budget,
    select_gas_scatter_samples,
    uses_gas_point_presentation,
)


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
_OPUS_PANEL_METHOD_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "total",
        (
            "OPUS_TG_PCT",
            "TG_CALC",
            "TG",
            "TGAS",
            "TOTALGAS",
            "TOTAL_GAS",
        ),
    ),
    (
        "opus",
        ("OPUS3", "OPUS4", "OPUS_K1_3", "OPUS_1_5"),
    ),
    (
        "ratios",
        ("WH", "BH", "CH", "C1_C2", "C1_C3", "C1_C4", "C1_C5"),
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
_MIN_AXIS_LABEL_GAP_POINTS = 14.0
_PRINT_CURVE_WIDTH = 1.25
_PRINT_GRID_MINOR = "#d1d9e2"
_PRINT_GRID_MAJOR = "#9eafbf"


def render_chart_pages(
    canvas: PageCanvas,
    report: HydrocarbonInterpretationReport,
    dataset: Dataset,
    language: AppLanguage,
    *,
    chart_panels: ReportChartPanelSettings = DEFAULT_REPORT_CHART_PANELS,
) -> None:
    depth = np.asarray(dataset.depth, dtype=np.float64)
    finite_depth = np.isfinite(depth)
    if depth.ndim != 1 or np.count_nonzero(finite_depth) < 2:
        return
    panels = tuple(
        (name, curves)
        for name, curves in _panel_curves(report, dataset, **chart_panel_render_options(chart_panels))
        if curves
    )
    if not panels:
        return

    context = context_segments(getattr(report, "gas_context_events", ()), float(np.nanmin(depth[finite_depth])), float(np.nanmax(depth[finite_depth])))
    provisional = chart_geometry(
        canvas.content_rect, DepthPage(0.0, 1.0, 1000, 28.0), len(panels), context_track=bool(context),
    )
    header_height = max(CHART_TRACK_HEADER_HEIGHT, 20.0 + max(
        track_heading_height(_labels(language)[name], rect.width(), 7.5,
                             canvas.painter.device())
        for (name, _curves), rect in zip(panels, provisional.panel_rects, strict=True)
    ))
    if provisional.context_rect is not None:
        header_height = max(header_height, 20.0 + track_heading_height(context_heading(language), provisional.context_rect.width(), 7.0 * 72.0 / canvas.painter.device().logicalDpiY(), canvas.painter.device()))
    available_height = (
        canvas.content_rect.height()
        - CHART_HEADER_HEIGHT
        - header_height
        - CHART_LEGEND_HEIGHT
        - CHART_NOTE_HEIGHT
    )
    pages = plan_depth_pages(
        float(np.nanmin(depth[finite_depth])),
        float(np.nanmax(depth[finite_depth])),
        available_height,
    )
    for page_index, page in enumerate(pages, start=1):
        canvas.new_page()
        percentiles = _curve_percentiles(panels, dataset, page=page)
        _draw_chart_page(
            canvas.painter,
            chart_geometry(canvas.content_rect, page, len(panels),
                           track_header_height=header_height, context_track=bool(context)),
            page,
            page_index,
            len(pages),
            report,
            dataset,
            panels,
            _display_curve_ranges(percentiles),
            percentiles,
            language,
        )
        canvas.y = canvas.content_rect.bottom()
    render_context_legend_pages(canvas, context, language, report.depth_unit)


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
) -> None:
    labels = _labels(language)
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
    if geometry.context_rect is not None:
        paint_context_track(painter, geometry.context_rect, getattr(report, "gas_context_events", ()), page.top_depth, page.bottom_depth, language, header_height=geometry.track_header_height)
    candidates = report.candidates
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
            show_candidate_codes=panel_index == len(panels) - 1,
        )
        _draw_legend(
            painter,
            geometry.legend_rect,
            panel_index,
            len(panels),
            curves,
            percentiles,
            language=language,
            display_hints=display_hints,
            point_series=panel_name in {"ratios", "opus"},
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
    labels = _labels(language)
    painter.fillRect(rect, QColor("#f8fafc"))
    painter.setPen(QPen(QColor("#334155"), 0.9))
    painter.drawRect(rect)
    title = labels["depth"] + (f", {unit}" if unit else "")
    title_font = print_font(7.0, text=title)
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.setPen(QColor("#172033"))
    painter.drawText(
        QRectF(rect.left() - 2.0, rect.top() - 28.0, rect.width() + 4.0, 18.0),
        Qt.AlignmentFlag.AlignCenter,
        title,
    )

    step = _nice_tick_step(page.span, target_ticks=8)
    ticks = _readable_depth_ticks(page, step, rect.height())
    painter.setFont(print_font(6.7, text=f"{page.bottom_depth:.1f}"))
    for value in ticks:
        y = _depth_y(value, page, rect)
        painter.setPen(QPen(QColor("#64748b"), 0.6))
        if side == "left":
            painter.drawLine(QLineF(rect.right() - 8.0, y, rect.right(), y))
            text_rect = QRectF(
                rect.left() + 1.0,
                y - 7.0,
                rect.width() - 11.0,
                14.0,
            )
            alignment = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        else:
            painter.drawLine(QLineF(rect.left(), y, rect.left() + 8.0, y))
            text_rect = QRectF(
                rect.left() + 10.0,
                y - 7.0,
                rect.width() - 11.0,
                14.0,
            )
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
    ranges: dict[str, tuple[float, float]],
    candidates: tuple[HydrocarbonCandidateInterval, ...],
    language: AppLanguage,
    *,
    header_height: float = CHART_TRACK_HEADER_HEIGHT,
    show_candidate_codes: bool = False,
) -> None:
    painter.fillRect(rect, QColor("#ffffff"))
    step = _nice_tick_step(page.span, target_ticks=8)
    for tick in _depth_ticks(page, step):
        y = _depth_y(tick, page, rect)
        painter.setPen(QPen(QColor(_PRINT_GRID_MINOR), 0.55))
        painter.drawLine(QLineF(rect.left(), y, rect.right(), y))
    for index in range(5):
        x = rect.left() + index / 4.0 * rect.width()
        painter.setPen(QPen(QColor("#d8e0e8"), 0.5))
        painter.drawLine(QLineF(x, rect.top(), x, rect.bottom()))
        painter.setFont(print_font(5.8, text="100"))
        painter.setPen(QColor("#64748b"))
        label_left = (
            rect.left() + 2.0 if index == 0 else rect.right() - 30.0 if index == 4 else x - 14.0
        )
        painter.drawText(
            QRectF(label_left, rect.top() - 19.0, 28.0, 12.0),
            Qt.AlignmentFlag.AlignCenter,
            str(index * 25),
        )

    _draw_candidate_bands(
        painter,
        rect,
        page,
        candidates,
        show_codes=show_candidate_codes,
    )
    heading = _labels(language)[panel_name]
    paint_track_heading(
        painter,
        QRectF(rect.left(), rect.top() - header_height + 2.0,
               rect.width(), header_height - 20.0),
        heading, 7.5,
    )
    if not any(curve.metadata.curve_id in ranges for curve in curves):
        painter.setPen(QColor("#64748b"))
        label = _labels(language)["no_data"]
        painter.setFont(print_font(8.0, text=label))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
    else:
        _draw_curves(
            painter,
            rect,
            page,
            dataset,
            curves,
            ranges,
            point_series=panel_name in {"ratios", "opus"},
        )
    painter.setPen(QPen(QColor("#334155"), 1.0))
    painter.drawRect(rect)


def _draw_candidate_bands(
    painter: QPainter,
    rect: QRectF,
    page: DepthPage,
    candidates: tuple[HydrocarbonCandidateInterval, ...],
    *,
    show_codes: bool = False,
) -> None:
    """Draw prospect bands with a non-colour marker/code cue for grayscale output."""

    for candidate in candidates:
        top_depth = candidate.top_depth
        bottom_depth = candidate.bottom_depth
        overlap_top = max(page.top_depth, min(top_depth, bottom_depth))
        overlap_bottom = min(page.bottom_depth, max(top_depth, bottom_depth))
        if overlap_bottom <= overlap_top:
            continue
        y1 = _depth_y(overlap_top, page, rect)
        y2 = _depth_y(overlap_bottom, page, rect)
        spec = fluid_marker_spec(candidate.fluid_hypothesis)
        color = QColor(spec.color)
        color.setAlpha(36)
        band = QRectF(
            rect.left(),
            min(y1, y2),
            rect.width(),
            max(1.0, abs(y2 - y1)),
        )
        painter.fillRect(band, color)
        if not show_codes:
            continue

        center_y = band.center().y()
        marker_x = rect.right() - 25.0
        draw_fluid_marker(
            painter,
            QPointF(marker_x, center_y),
            spec,
            size=5.0,
        )
        code_rect = QRectF(marker_x + 4.5, center_y - 5.5, 19.0, 11.0)
        painter.setPen(QColor("#172033"))
        font = print_font(5.2, text=spec.code)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            code_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            spec.code,
        )


def _extrema_preserving_print_rows(
    segment: np.ndarray,
    depth: np.ndarray,
    values: np.ndarray,
    page: DepthPage,
    rect: QRectF,
) -> np.ndarray:
    """Reduce dense print rows without losing local extrema.

    Uniform linspace downsampling can miss narrow gas peaks or connect sparse
    retained points into long diagonal spikes. Bucket rows by their final
    vertical print position and retain first/min/max/last samples plus
    missing-value sentinels in stable order. This preserves extrema and real
    acquisition breaks while bounding visual density.
    """

    if segment.size <= 4:
        return segment
    # About one bucket per two typographic points keeps vector output readable
    # while preserving substantially more detail than the printed raster can
    # resolve at normal viewing distance.
    bucket_count = max(8, min(int(rect.height() / 2.0), 900))
    if segment.size <= bucket_count * 4:
        return segment

    y = (
        rect.top()
        + (depth[segment] - page.top_depth)
        / page.span
        * rect.height()
    )
    normalized = np.clip(
        (y - rect.top()) / max(rect.height(), 1.0),
        0.0,
        1.0,
    )
    buckets = np.minimum(
        bucket_count - 1,
        np.floor(normalized * bucket_count).astype(np.int64),
    )

    keep: list[int] = []
    for bucket in np.unique(buckets):
        positions = np.flatnonzero(buckets == bucket)
        if positions.size == 0:
            continue
        rows = segment[positions]
        finite_mask = np.isfinite(values[rows])
        finite_positions = positions[finite_mask]
        nonfinite_mask = ~finite_mask
        selected_positions = {int(positions[0]), int(positions[-1])}
        if np.any(nonfinite_mask):
            run_starts = np.flatnonzero(
                nonfinite_mask
                & np.concatenate(
                    (np.asarray([True]), finite_mask[:-1]),
                )
            )
            run_ends = np.flatnonzero(
                nonfinite_mask
                & np.concatenate(
                    (finite_mask[1:], np.asarray([True])),
                )
            )
            selected_positions.update(int(positions[item]) for item in run_starts)
            selected_positions.update(int(positions[item]) for item in run_ends)
        if finite_positions.size:
            finite_rows = segment[finite_positions]
            local_values = values[finite_rows]
            selected_positions.add(
                int(finite_positions[int(np.argmin(local_values))])
            )
            selected_positions.add(
                int(finite_positions[int(np.argmax(local_values))])
            )
        keep.extend(sorted(selected_positions))
    if not keep:
        return segment
    unique_positions = np.asarray(sorted(set(keep)), dtype=np.int64)
    return segment[unique_positions]


def _draw_curves(
    painter: QPainter,
    rect: QRectF,
    page: DepthPage,
    dataset: Dataset,
    curves: tuple[CurveData, ...],
    ranges: dict[str, tuple[float, float]],
    *,
    point_series: bool | None = None,
) -> None:
    depth = np.asarray(dataset.depth, dtype=np.float64)
    indices = np.flatnonzero(
        np.isfinite(depth)
        & (depth >= page.top_depth)
        & (depth <= page.bottom_depth)
    )
    indices = indices[np.argsort(depth[indices], kind="stable")]
    # Preserve every source row while detecting real acquisition gaps.
    # Print-density reduction is value-aware below; uniform pre-downsampling
    # here could remove a narrow OPUS/GasRatio peak before extrema selection.
    segments = continuous_depth_segments(
        depth,
        indices,
        limit=max(2, int(indices.size)),
    )

    painter.save()
    painter.setClipRect(rect.adjusted(0.8, 0.8, -0.8, -0.8))
    curve_rect = rect.adjusted(3.0, 0.0, -3.0, 0.0)
    for curve_index, curve in enumerate(curves):
        values = np.asarray(curve.values, dtype=np.float64)
        value_range = ranges.get(curve.metadata.curve_id)
        if values.shape != depth.shape or value_range is None:
            continue
        low, high = value_range
        color = QColor(_COLORS[curve_index % len(_COLORS)])
        draw_as_points = (
            point_series
            if point_series is not None
            else uses_gas_point_presentation(
                (
                    curve.metadata.original_mnemonic,
                    curve.metadata.canonical_mnemonic,
                )
            )
        )
        if draw_as_points:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            point_values, point_depth = select_gas_scatter_samples(
                depth,
                values,
                page.top_depth,
                page.bottom_depth,
                max_points=gas_scatter_point_budget(curve_rect.height()),
            )
            radius = GAS_PRINT_POINT_RADIUS_PT
            for value, depth_value in zip(point_values, point_depth, strict=True):
                if high <= low:
                    normalized = 0.5 if value == low else 1.0 if value > low else 0.0
                else:
                    normalized = float(np.clip((value - low) / (high - low), 0.0, 1.0))
                current = (
                    curve_rect.left() + normalized * curve_rect.width(),
                    _depth_y(float(depth_value), page, curve_rect),
                )
                painter.drawEllipse(
                    QRectF(
                        current[0] - radius,
                        current[1] - radius,
                        radius * 2.0,
                        radius * 2.0,
                    )
                )
            painter.setBrush(Qt.BrushStyle.NoBrush)
            continue

        pen = QPen(color, _PRINT_CURVE_WIDTH)
        pen.setCosmetic(True)
        painter.setPen(pen)
        for segment in segments:
            render_rows = _extrema_preserving_print_rows(
                segment,
                depth,
                values,
                page,
                curve_rect,
            )
            previous: tuple[float, float] | None = None
            previous_normalized: float | None = None
            previous_clipped = False
            for row_index in render_rows:
                value = values[row_index]
                if not np.isfinite(value):
                    previous = None
                    previous_normalized = None
                    previous_clipped = False
                    continue
                if high <= low:
                    normalized = 0.5 if value == low else 1.0 if value > low else 0.0
                    clipped = value != low
                else:
                    raw_normalized = float((value - low) / (high - low))
                    normalized = float(np.clip(raw_normalized, 0.0, 1.0))
                    clipped = raw_normalized < 0.0 or raw_normalized > 1.0
                current = (
                    curve_rect.left() + normalized * curve_rect.width(),
                    _depth_y(float(depth[row_index]), page, curve_rect),
                )
                break_clipped_spike = (
                    previous_normalized is not None
                    and (clipped or previous_clipped)
                    and abs(normalized - previous_normalized) >= 0.72
                )
                if previous is not None and not break_clipped_spike:
                    painter.drawLine(
                        QLineF(previous[0], previous[1], current[0], current[1])
                    )
                previous = current
                previous_normalized = normalized
                previous_clipped = clipped
    painter.restore()


def _draw_legend(
    painter: QPainter,
    legend_rect: QRectF,
    panel_index: int,
    panel_count: int,
    curves: tuple[CurveData, ...],
    ranges: dict[str, tuple[float, float]],
    *,
    language: AppLanguage,
    display_hints: dict[str, str] | None = None,
    point_series: bool | None = None,
) -> None:
    gap = 8.0
    width = (legend_rect.width() - gap * (panel_count - 1)) / panel_count
    column = QRectF(
        legend_rect.left() + panel_index * (width + gap),
        legend_rect.top(),
        width,
        legend_rect.height(),
    )
    for row_index, curve in enumerate(curves[:5]):
        value_range = ranges.get(curve.metadata.curve_id)
        if value_range is None:
            continue
        low, high = value_range
        y = column.top() + row_index * 14.5
        color = QColor(_COLORS[row_index % len(_COLORS)])
        draw_as_points = (
            point_series
            if point_series is not None
            else uses_gas_point_presentation(
                (
                    curve.metadata.original_mnemonic,
                    curve.metadata.canonical_mnemonic,
                )
            )
        )
        painter.setPen(QPen(color, 0.8))
        if draw_as_points:
            painter.setBrush(color)
            for offset in (2.5, 8.5, 14.5):
                painter.drawEllipse(
                    QRectF(
                        column.left() + offset - 1.35,
                        y + 3.65,
                        2.7,
                        2.7,
                    )
                )
            painter.setBrush(Qt.BrushStyle.NoBrush)
        else:
            painter.setPen(QPen(color, 2.2))
            painter.drawLine(
                QLineF(column.left(), y + 5.0, column.left() + 17.0, y + 5.0)
            )
        hints = display_hints or {}
        canonical_hint = hints.get(curve.metadata.original_mnemonic.strip().upper())
        text = curve_legend_text(
            curve,
            low,
            high,
            language,
            canonical_hint=canonical_hint,
        )
        painter.setPen(QColor("#172033"))
        painter.setFont(print_font(5.9, text=text))
        painter.drawText(
            QRectF(column.left() + 21.0, y, column.width() - 21.0, 12.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            text,
        )


def _curve_percentiles(
    panels: tuple[tuple[str, tuple[CurveData, ...]], ...],
    dataset: Dataset,
    *,
    page: DepthPage | None = None,
) -> dict[str, tuple[float, float]]:
    """Return factual p5/p95 values used by the printed legend."""

    result: dict[str, tuple[float, float]] = {}
    depth = np.asarray(dataset.depth, dtype=np.float64)
    selected = (
        np.isfinite(depth) & (depth >= page.top_depth) & (depth <= page.bottom_depth)
        if page is not None
        else np.isfinite(depth)
    )
    for panel_name, curves in panels:
        minimum_samples = 1 if panel_name in {"ratios", "opus"} else 2
        for curve in curves:
            values = np.asarray(curve.values, dtype=np.float64)
            if values.shape != dataset.depth.shape:
                continue
            finite = values[selected & np.isfinite(values)]
            if finite.size < minimum_samples:
                continue
            low = float(np.percentile(finite, 5.0))
            high = float(np.percentile(finite, 95.0))
            if np.isfinite(low) and np.isfinite(high):
                result[curve.metadata.curve_id] = (low, high)
    return result


def _display_curve_ranges(
    percentiles: dict[str, tuple[float, float]],
) -> dict[str, tuple[float, float]]:
    """Expand only degenerate ranges for visibility without falsifying p5/p95."""

    result: dict[str, tuple[float, float]] = {}
    for curve_id, (low, high) in percentiles.items():
        display_low = low
        display_high = high
        if high <= low or np.isclose(high, low, rtol=1e-9, atol=1e-12):
            center = (low + high) / 2.0
            spread = max(abs(center) * 0.05, 1e-6)
            display_low, display_high = center - spread, center + spread
        result[curve_id] = (display_low, display_high)
    return result


def _curve_ranges(
    panels: tuple[tuple[str, tuple[CurveData, ...]], ...],
    dataset: Dataset,
    *,
    page: DepthPage | None = None,
) -> dict[str, tuple[float, float]]:
    """Return display ranges; factual percentiles remain available separately."""

    return _display_curve_ranges(_curve_percentiles(panels, dataset, page=page))


def _panel_curves(
    report: HydrocarbonInterpretationReport,
    dataset: Dataset,
    chart_panels: ReportChartPanelSettings = DEFAULT_REPORT_CHART_PANELS,
) -> tuple[tuple[str, tuple[CurveData, ...]], ...]:
    marker_groups = (
        _OPUS_PANEL_METHOD_MARKERS
        if report.report_profile == "opus"
        else _PANEL_METHOD_MARKERS
    )
    return report_curve_panels(report, dataset, marker_groups, chart_panels)


def _nice_tick_step(span: float, *, target_ticks: int) -> float:
    epsilon = float(np.finfo(np.float64).eps)
    raw = max(float(span) / max(1, target_ticks), epsilon)
    magnitude = 10.0 ** floor(log10(raw))
    normalized = raw / magnitude
    if normalized <= 1.0:
        factor = 1.0
    elif normalized <= 2.0:
        factor = 2.0
    elif normalized <= 5.0:
        factor = 5.0
    else:
        factor = 10.0
    return factor * magnitude


def _depth_ticks(page: DepthPage, step: float) -> tuple[float, ...]:
    tolerance = step * 1e-7
    value = floor(page.top_depth / step) * step
    ticks: list[float] = []
    while value <= page.bottom_depth + tolerance:
        if value >= page.top_depth - tolerance:
            ticks.append(float(value))
        value += step
    for endpoint in (page.top_depth, page.bottom_depth):
        if not any(abs(endpoint - tick) <= tolerance for tick in ticks):
            ticks.append(endpoint)
    return tuple(sorted(ticks))


def _readable_depth_ticks(
    page: DepthPage,
    step: float,
    plot_height_points: float,
) -> tuple[float, ...]:
    """Keep exact page limits while removing neighbouring labels that overlap."""

    ticks = _depth_ticks(page, step)
    tolerance = step * 1e-7
    minimum_depth_gap = page.span * _MIN_AXIS_LABEL_GAP_POINTS / max(float(plot_height_points), 1.0)
    endpoints = (page.top_depth, page.bottom_depth)
    readable: list[float] = []
    for tick in ticks:
        is_endpoint = any(abs(tick - endpoint) <= tolerance for endpoint in endpoints)
        if is_endpoint or all(
            abs(tick - endpoint) >= minimum_depth_gap
            for endpoint in endpoints
        ):
            readable.append(tick)
    return tuple(readable)


def _depth_y(depth: float, page: DepthPage, rect: QRectF) -> float:
    return rect.top() + (float(depth) - page.top_depth) / page.span * rect.height()


def _depth_label(value: float, step: float) -> str:
    if step >= 1.0:
        return f"{value:.0f}" if abs(value - round(value)) < 1e-6 else f"{value:.1f}"
    decimals = max(1, int(ceil(-log10(step))) + 1)
    return f"{value:.{decimals}f}"


def _labels(language: AppLanguage) -> dict[str, str]:
    return {
        AppLanguage.RU: {
            "title": "Графики интерпретационных кривых по глубине",
            "page": (
                "Лист графика {current} из {total}: {top:.2f}–{bottom:.2f} "
                "{unit}; вертикальный масштаб 1:{scale}"
            ),
            "depth": "Глубина",
            "no_data": "Нет измерений на этом интервале",
            "total": "Общий и нормализованный газ",
            "opus": "Показатели ОПУС",
            "ratios": "Haworth и Pixler",
            "drilling": "Буровой контекст и DEXP",
            "note": (
                "Обычные многокривые дорожки нормированы по p5–p95. Газовые отношения "
                "выведены отдельными непрерывными трассами на стабильных фактических "
                "линейных/логарифмических шкалах. Цветные полосы и маркеры отмечают "
                "перспективные интервалы и предварительный "
                "тип флюида; полная формулировка остаётся в таблице. Каждый лист сохраняет "
                "физический масштаб глубины; шкалы и границы повторяются с обеих сторон."
            ),
        },
        AppLanguage.KK: {
            "title": "Тереңдік бойынша интерпретациялық қисықтар графиктері",
            "page": (
                "График беті {current}/{total}: {top:.2f}–{bottom:.2f} {unit}; "
                "тік масштаб 1:{scale}"
            ),
            "depth": "Тереңдік",
            "no_data": "Бұл аралықта өлшемдер жоқ",
            "total": "Жалпы және нормаланған газ",
            "opus": "ОПУС көрсеткіштері",
            "ratios": "Haworth және Pixler",
            "drilling": "Бұрғылау контексті және DEXP",
            "note": (
                "Кәдімгі көп қисықты жолдар p5–p95 бойынша нормаланады. Газ қатынастары "
                "тұрақты нақты сызықтық/логарифмдік шкалаларда бөлек үздіксіз трассалармен "
                "көрсетіледі. Түсті жолақтар мен маркерлер перспективалы аралықты және "
                "алдын ала флюид түрін "
                "көрсетеді; толық мәтін кестеде қалады. Әр бет тереңдіктің физикалық "
                "масштабын сақтайды; шкалалар мен шекаралар екі жақта қайталанады."
            ),
        },
        AppLanguage.EN: {
            "title": "Depth plots of interpretation curves",
            "page": (
                "Chart sheet {current} of {total}: {top:.2f}–{bottom:.2f} "
                "{unit}; vertical scale 1:{scale}"
            ),
            "depth": "Depth",
            "no_data": "No measurements in this interval",
            "total": "Total and normalized gas",
            "opus": "OPUS indicators",
            "ratios": "Haworth and Pixler",
            "drilling": "Drilling context and DEXP",
            "note": (
                "Ordinary multi-curve tracks use p5–p95 normalization. Gas ratios are "
                "separate continuous traces on stable factual linear/logarithmic scales. "
                "Colored bands and markers show prospective intervals and preliminary fluid "
                "type; full wording remains in the table. Every sheet preserves a physical "
                "depth scale; scales and outer borders repeat on both sides."
            ),
        },
    }[language]


__all__ = ["render_chart_pages"]
