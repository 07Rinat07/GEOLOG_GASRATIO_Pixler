from __future__ import annotations

from html import escape

import numpy as np
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen

from geoworkbench.domain.depth_interval import scope_dataset
from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.printing.geology_track_rendering import (
    paint_cuttings_track,
    paint_lba_track,
)
from geoworkbench.printing.hydrocarbon_interpretation_curve_labels import (
    curve_legend_text,
    report_curve_label_hints,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology import (
    InterpretationGeologySnapshot,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology_legend import (
    build_interpretation_geology_legend,
    geology_legend_height,
    paint_geology_legend,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology_settings import (
    DEFAULT_INTERPRETATION_GEOLOGY_TRACK_SETTINGS,
    InterpretationGeologyTrackSettings,
    forced_empty_geology_tracks,
    resolve_geology_track_kinds,
)
from geoworkbench.printing.hydrocarbon_interpretation_report_range import (
    ReportDepthRange,
)
from geoworkbench.printing.hydrocarbon_interpretation_curve_selection import report_curve_panels
from geoworkbench.printing.hydrocarbon_fluid_markers import (
    draw_fluid_marker,
    fluid_marker_legend_specs,
    fluid_marker_spec,
    marker_lane_offsets,
    marker_lanes,
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
    hydrocarbon_interpretation_html,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.gas_curve_presentation import (
    GAS_PREVIEW_POINT_RADIUS_PX,
    gas_scatter_point_budget,
    select_gas_scatter_samples,
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
        (
            "WH",
            "BH",
            "CH",
            "C1_C2",
            "C1_C3",
            "C1_C4",
            "C1_C5",
        ),
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


def hydrocarbon_interpretation_html_with_chart(
    report: HydrocarbonInterpretationReport,
    dataset: Dataset,
    language: AppLanguage = AppLanguage.RU,
) -> str:
    """Return the standard report HTML with a whole-well curve chart appended."""

    base = hydrocarbon_interpretation_html(report, language)
    from geoworkbench.services.hydrocarbon_interpretation_gas_html import (
        inject_interval_gas_statistics_html,
    )

    base = inject_interval_gas_statistics_html(
        base, report, scope_dataset(dataset, report.analysis_depth_interval), language,
    )
    uri = hydrocarbon_interpretation_chart_data_uri(report, dataset, language)
    if not uri:
        return base
    labels = _labels(language)
    block = (
        "<section class='interpretation-curves'>"
        f"<h2>{escape(labels['title'])}</h2>"
        f"<p><small>{escape(labels['note'])}</small></p>"
        "<div style='width:100%; text-align:center;'>"
        f'<img alt="{escape(labels["title"])}" '
        "style='display:block; width:100%; max-width:1050px; height:auto; "
        "margin:0 auto;' "
        f'src="{uri}" />'
        "</div></section>"
    )
    return base.replace("</body>", block + "</body>")


def hydrocarbon_interpretation_chart_data_uri(
    report: HydrocarbonInterpretationReport,
    dataset: Dataset,
    language: AppLanguage = AppLanguage.RU,
    *,
    geology: InterpretationGeologySnapshot | None = None,
    geology_track_settings: InterpretationGeologyTrackSettings = (
        DEFAULT_INTERPRETATION_GEOLOGY_TRACK_SETTINGS
    ),
    depth_range: ReportDepthRange | None = None,
) -> str:
    """Render available interpretation curves against depth as a PNG data URI."""

    interval = getattr(report, "analysis_depth_interval", None)
    depth_range = interval or depth_range
    dataset = scope_dataset(dataset, interval)
    depth = np.asarray(dataset.depth, dtype=np.float64)
    finite_depth = np.isfinite(depth)
    if depth.ndim != 1 or np.count_nonzero(finite_depth) < 2:
        return ""

    panels = _panel_curves(report, dataset)
    panels = tuple((panel, curves) for panel, curves in panels if curves)
    display_hints = report_curve_label_hints(report)
    if not panels:
        return ""

    legend_device = QImage(1, 1, QImage.Format.Format_ARGB32_Premultiplied)
    depth_min = float(np.nanmin(depth[finite_depth]))
    depth_max = float(np.nanmax(depth[finite_depth]))
    if depth_range is not None:
        depth_min = depth_range.top_depth
        depth_max = depth_range.bottom_depth
    if depth_max <= depth_min:
        depth_max = depth_min + 1.0
    visible_depth = (
        finite_depth
        & (depth >= depth_min)
        & (depth <= depth_max)
    )
    geology_tracks = resolve_geology_track_kinds(
        geology,
        depth_min,
        depth_max,
        geology_track_settings,
    )
    empty_state_tracks = forced_empty_geology_tracks(
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
    preview_legend_height = geology_legend_height(
        1_820.0,
        geology_legend,
        paint_device=legend_device,
    )
    outer_margin, depth_width, axis_gap = 35.0, 128.0, 16.0
    geology_track_width, geology_track_gap, panel_gap = 94.0, 10.0, 20.0
    geology_reserved_width = (
        len(geology_tracks) * geology_track_width
        + max(0, len(geology_tracks) - 1) * geology_track_gap
    )
    panel_left = outer_margin + depth_width + axis_gap + geology_reserved_width
    if geology_tracks:
        panel_left += axis_gap
    panel_right = 2_000.0 - outer_margin - depth_width - axis_gap
    panel_width = (panel_right - panel_left - panel_gap * (len(panels) - 1)) / len(panels)
    header_height = max(62.0, 30.0 + max(
        track_heading_height(_labels(language)[name], panel_width, 11.0, legend_device)
        for name, _curves in panels
    ))
    legend_offset = max(0.0, preview_legend_height) + header_height - 62.0
    image = QImage(
        2_000, 1_280 + int(np.ceil(legend_offset)),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        labels = _labels(language)
        title_font = print_font(17.0, text=labels["title"])
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor("#172033"))
        painter.drawText(
            QRectF(90.0, 18.0, 1_820.0, 45.0),
            Qt.AlignmentFlag.AlignCenter,
            labels["title"],
        )

        if preview_legend_height > 0.0:
            paint_geology_legend(
                painter,
                QRectF(90.0, 72.0, 1_820.0, preview_legend_height),
                geology_legend,
                language,
            )

        # Grow the canvas with the legend, keeping the depth plot height stable.
        plot_top = 134.0 + legend_offset
        plot_bottom = 1_015.0 + legend_offset
        plot_height = plot_bottom - plot_top
        left_depth_rect = QRectF(
            outer_margin,
            plot_top,
            depth_width,
            plot_height,
        )
        right_depth_rect = QRectF(
            image.width() - outer_margin - depth_width,
            plot_top,
            depth_width,
            plot_height,
        )
        geology_left = left_depth_rect.right() + axis_gap
        geology_rects = tuple(
            QRectF(
                geology_left + index * (geology_track_width + geology_track_gap),
                plot_top,
                geology_track_width,
                plot_height,
            )
            for index in range(len(geology_tracks))
        )

        _draw_depth_axis(
            painter,
            left_depth_rect,
            depth_min,
            depth_max,
            report.depth_unit,
            side="left",
            language=language,
        )
        _draw_depth_axis(
            painter,
            right_depth_rect,
            depth_min,
            depth_max,
            report.depth_unit,
            side="right",
            language=language,
        )
        if geology_tracks:
            _draw_geology_preview_tracks(
                painter,
                geology_rects,
                geology,
                geology_tracks,
                empty_state_tracks,
                depth_min,
                depth_max,
                language,
                header_height,
            )

        candidates = tuple(
            candidate
            for candidate in report.candidates
            if candidate.bottom_depth >= depth_min
            and candidate.top_depth <= depth_max
        )
        panel_rects = tuple(
            QRectF(
                panel_left + panel_index * (panel_width + panel_gap),
                plot_top,
                panel_width,
                plot_height,
            )
            for panel_index in range(len(panels))
        )
        for (panel_name, curves), rect in zip(panels, panel_rects, strict=True):
            _draw_panel(
                painter,
                rect,
                depth,
                visible_depth,
                depth_min,
                depth_max,
                panel_name,
                curves,
                candidates,
                language,
                display_hints,
                header_height,
            )

        if panel_rects and candidates:
            _draw_whole_well_fluid_markers(
                painter,
                panel_rects[-1],
                depth_min,
                depth_max,
                candidates,
            )
            _draw_whole_well_fluid_legend(
                painter,
                QRectF(90.0, 1_136.0 + legend_offset, 1_820.0, 30.0),
                candidates,
                language,
            )

        painter.setFont(print_font(9.0, text=labels["footer"]))
        painter.setPen(QColor("#475569"))
        painter.drawText(
            QRectF(90.0, 1_170.0 + legend_offset, 1_820.0, 84.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            labels["footer"],
        )
    finally:
        painter.end()

    payload = QByteArray()
    buffer = QBuffer(payload)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")  # type: ignore[call-overload]
    return "data:image/png;base64," + bytes(payload.toBase64().data()).decode(
        "ascii"
    )


def _panel_curves(
    report: HydrocarbonInterpretationReport,
    dataset: Dataset,
) -> tuple[tuple[str, tuple[CurveData, ...]], ...]:
    marker_groups = (
        _OPUS_PANEL_METHOD_MARKERS
        if report.report_profile == "opus"
        else _PANEL_METHOD_MARKERS
    )
    return report_curve_panels(report, dataset, marker_groups)


def _draw_depth_axis(
    painter: QPainter,
    rect: QRectF,
    depth_min: float,
    depth_max: float,
    unit: str,
    *,
    side: str,
    language: AppLanguage,
) -> None:
    labels = _labels(language)
    painter.fillRect(rect, QColor("#f8fafc"))
    painter.setPen(QPen(QColor("#334155"), 2.4))
    painter.drawRect(rect)

    title = labels["depth"] + (f", {unit}" if unit else "")
    title_font = print_font(10.0, text=title)
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.setPen(QColor("#172033"))
    painter.drawText(
        QRectF(rect.left() - 4.0, rect.top() - 38.0, rect.width() + 8.0, 28.0),
        Qt.AlignmentFlag.AlignCenter,
        title,
    )

    painter.setFont(print_font(9.0, text=f"{depth_max:.1f}"))
    for major in range(11):
        fraction = major / 10.0
        y = rect.top() + fraction * rect.height()
        depth_value = depth_min + fraction * (depth_max - depth_min)
        painter.setPen(QPen(QColor("#64748b"), 1.2))
        if side == "left":
            painter.drawLine(QLineF(rect.right() - 12.0, y, rect.right(), y))
            text_rect = QRectF(
                rect.left() + 3.0,
                y - 10.0,
                rect.width() - 19.0,
                20.0,
            )
            alignment = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        else:
            painter.drawLine(QLineF(rect.left(), y, rect.left() + 12.0, y))
            text_rect = QRectF(
                rect.left() + 17.0,
                y - 10.0,
                rect.width() - 20.0,
                20.0,
            )
            alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        painter.setPen(QColor("#334155"))
        painter.drawText(text_rect, alignment, f"{depth_value:.1f}")

        if major == 10:
            continue
        for minor in range(1, 5):
            minor_y = y + minor / 5.0 * rect.height() / 10.0
            painter.setPen(QPen(QColor("#94a3b8"), 0.8))
            if side == "left":
                painter.drawLine(
                    QLineF(rect.right() - 6.0, minor_y, rect.right(), minor_y)
                )
            else:
                painter.drawLine(
                    QLineF(rect.left(), minor_y, rect.left() + 6.0, minor_y)
                )

    painter.setPen(QPen(QColor("#334155"), 2.4))
    painter.drawRect(rect)


def _draw_geology_preview_tracks(
    painter: QPainter,
    rects: tuple[QRectF, ...],
    geology: InterpretationGeologySnapshot | None,
    geology_tracks: tuple[str, ...],
    empty_state_tracks: tuple[str, ...],
    depth_min: float,
    depth_max: float,
    language: AppLanguage,
    header_height: float = 62.0,
) -> None:
    labels = {
        AppLanguage.RU: {"cuttings": "Шламограмма", "lba": "ЛБА", "empty": "Нет данных"},
        AppLanguage.KK: {"cuttings": "Шламограмма", "lba": "ЛБА", "empty": "Дерек жоқ"},
        AppLanguage.EN: {"cuttings": "Cuttings", "lba": "LBA", "empty": "No data"},
    }[language]
    samples = tuple(geology.samples) if geology is not None else ()
    lithotypes = geology.lithotype_map if geology is not None else {}
    for track, rect in zip(geology_tracks, rects, strict=True):
        painter.fillRect(rect, QColor("#ffffff"))
        painter.setPen(QPen(QColor("#334155"), 2.0))
        painter.drawRect(rect)
        heading = labels[track]
        paint_track_heading(
            painter,
            QRectF(rect.left(), rect.top() - header_height + 4.0,
                   rect.width(), header_height - 30.0),
            heading, 8.5,
        )
        for major in range(11):
            y = rect.top() + major / 10.0 * rect.height()
            painter.setPen(QPen(QColor("#dbe3ec"), 0.9))
            painter.drawLine(QLineF(rect.left(), y, rect.right(), y))
        if track in empty_state_tracks:
            painter.setPen(QColor("#64748b"))
            painter.setFont(print_font(8.0, text=labels["empty"]))
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                labels["empty"],
            )
        elif track == "cuttings":
            paint_cuttings_track(
                painter,
                rect,
                samples,
                (depth_min, depth_max),
                lithotypes,
            )
        else:
            paint_lba_track(
                painter,
                rect,
                samples,
                (depth_min, depth_max),
            )


def _draw_panel(
    painter: QPainter,
    rect: QRectF,
    depth: np.ndarray,
    finite_depth: np.ndarray,
    depth_min: float,
    depth_max: float,
    panel_name: str,
    curves: tuple[CurveData, ...],
    candidates: tuple[HydrocarbonCandidateInterval, ...],
    language: AppLanguage,
    display_hints: dict[str, str],
    header_height: float = 62.0,
) -> None:
    labels = _labels(language)
    painter.fillRect(rect, QColor("#ffffff"))

    for major in range(11):
        y = rect.top() + major / 10.0 * rect.height()
        painter.setPen(QPen(QColor("#cbd5e1"), 1.0))
        painter.drawLine(QLineF(rect.left(), y, rect.right(), y))
        if major == 10:
            continue
        for minor in range(1, 5):
            minor_y = y + minor / 5.0 * rect.height() / 10.0
            painter.setPen(QPen(QColor("#eef2f7"), 0.7))
            painter.drawLine(
                QLineF(rect.left(), minor_y, rect.right(), minor_y)
            )

    for tick in range(5):
        x = rect.left() + tick / 4.0 * rect.width()
        painter.setPen(QPen(QColor("#dbe3ec"), 0.9))
        painter.drawLine(QLineF(x, rect.top(), x, rect.bottom()))
        painter.setFont(print_font(7.5, text="100"))
        painter.setPen(QColor("#64748b"))
        painter.drawText(
            QRectF(x - 22.0, rect.top() - 24.0, 44.0, 18.0),
            Qt.AlignmentFlag.AlignCenter,
            str(tick * 25),
        )

    for candidate in candidates:
        top = _depth_y(
            candidate.top_depth,
            depth_min,
            depth_max,
            rect.top(),
            rect.height(),
        )
        bottom = _depth_y(
            candidate.bottom_depth,
            depth_min,
            depth_max,
            rect.top(),
            rect.height(),
        )
        band_top = min(top, bottom)
        band_height = max(2.0, abs(bottom - top))
        spec = fluid_marker_spec(candidate.fluid_hypothesis)
        band_color = QColor(spec.color)
        band_color.setAlpha(34)
        painter.fillRect(
            QRectF(rect.left(), band_top, rect.width(), band_height),
            band_color,
        )
        painter.setPen(QPen(QColor(spec.color), 0.9))
        painter.drawLine(QLineF(rect.left(), top, rect.right(), top))
        painter.drawLine(QLineF(rect.left(), bottom, rect.right(), bottom))

    paint_track_heading(
        painter,
        QRectF(rect.left(), rect.top() - header_height + 4.0,
               rect.width(), header_height - 30.0),
        labels[panel_name], 11.0,
    )

    depth_indices = np.flatnonzero(finite_depth)
    depth_indices = depth_indices[np.argsort(depth[depth_indices], kind="stable")]
    segments = continuous_depth_segments(depth, depth_indices, limit=1_800)
    curve_rect = rect.adjusted(7.0, 1.0, -7.0, -1.0)
    painter.save()
    painter.setClipRect(rect.adjusted(1.0, 1.0, -1.0, -1.0))
    point_series = panel_name in {"ratios", "opus"}
    minimum_samples = 1 if point_series else 2
    legend_rows: list[tuple[QColor, str, bool]] = []
    for curve_index, curve in enumerate(curves):
        values = np.asarray(curve.values, dtype=np.float64)
        usable = finite_depth & np.isfinite(values)
        if np.count_nonzero(usable) < minimum_samples:
            continue
        finite_values = values[usable]
        low = float(np.percentile(finite_values, 5.0))
        high = float(np.percentile(finite_values, 95.0))
        if not np.isfinite(low) or not np.isfinite(high):
            continue
        color = QColor(_COLORS[curve_index % len(_COLORS)])
        if point_series:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            point_values, point_depth = select_gas_scatter_samples(
                depth,
                values,
                depth_min,
                depth_max,
                max_points=gas_scatter_point_budget(curve_rect.height()),
            )
            radius = GAS_PREVIEW_POINT_RADIUS_PX
            for value, depth_value in zip(point_values, point_depth, strict=True):
                if high <= low:
                    normalized = 0.5 if value == low else 1.0 if value > low else 0.0
                else:
                    normalized = float(np.clip((value - low) / (high - low), 0.0, 1.0))
                x = curve_rect.left() + normalized * curve_rect.width()
                y = _depth_y(
                    float(depth_value),
                    depth_min,
                    depth_max,
                    curve_rect.top(),
                    curve_rect.height(),
                )
                painter.drawEllipse(
                    QRectF(
                        float(x) - radius,
                        float(y) - radius,
                        radius * 2.0,
                        radius * 2.0,
                    )
                )
            painter.setBrush(Qt.BrushStyle.NoBrush)
        else:
            painter.setPen(QPen(color, 2.2))
            for segment in segments:
                previous: tuple[float, float] | None = None
                previous_normalized: float | None = None
                previous_clipped = False
                for index in segment:
                    if not usable[index]:
                        previous = None
                        previous_normalized = None
                        previous_clipped = False
                        continue
                    if high <= low:
                        normalized = (
                            0.5
                            if values[index] == low
                            else 1.0
                            if values[index] > low
                            else 0.0
                        )
                        clipped = values[index] != low
                    else:
                        raw_normalized = float((values[index] - low) / (high - low))
                        normalized = float(np.clip(raw_normalized, 0.0, 1.0))
                        clipped = raw_normalized < 0.0 or raw_normalized > 1.0
                    current = (
                        float(curve_rect.left() + normalized * curve_rect.width()),
                        float(
                            _depth_y(
                                depth[index],
                                depth_min,
                                depth_max,
                                curve_rect.top(),
                                curve_rect.height(),
                            )
                        ),
                    )
                    spike = (
                        previous_normalized is not None
                        and (clipped or previous_clipped)
                        and abs(normalized - previous_normalized) >= 0.72
                    )
                    if previous is not None and not spike:
                        painter.drawLine(
                            QLineF(previous[0], previous[1], current[0], current[1])
                        )
                    previous = current
                    previous_normalized = normalized
                    previous_clipped = clipped

        canonical_hint = display_hints.get(
            curve.metadata.original_mnemonic.strip().upper()
        )
        legend = curve_legend_text(
            curve,
            low,
            high,
            language,
            canonical_hint=canonical_hint,
        )
        legend_rows.append((color, legend, point_series))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.restore()

    legend_top = rect.bottom() + 12.0
    for row_index, (color, legend, point_marker) in enumerate(legend_rows):
        legend_y = legend_top + row_index * 21.0
        painter.setPen(QPen(color, 1.0))
        if point_marker:
            painter.setBrush(color)
            for offset in (12.0, 21.0, 30.0):
                painter.drawEllipse(
                    QRectF(
                        rect.left() + offset - 2.0,
                        legend_y + 6.0,
                        4.0,
                        4.0,
                    )
                )
            painter.setBrush(Qt.BrushStyle.NoBrush)
        else:
            painter.setPen(QPen(color, 3.5))
            painter.drawLine(
                QLineF(
                    rect.left() + 8.0,
                    legend_y + 8.0,
                    rect.left() + 34.0,
                    legend_y + 8.0,
                )
            )
        painter.setPen(QColor("#172033"))
        painter.setFont(print_font(7.6, text=legend))
        painter.drawText(
            QRectF(rect.left() + 40.0, legend_y, rect.width() - 46.0, 18.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            legend,
        )

    painter.setPen(QPen(QColor("#334155"), 2.6))
    painter.drawRect(rect)



def _draw_whole_well_fluid_markers(
    painter: QPainter,
    target: QRectF,
    depth_min: float,
    depth_max: float,
    candidates: tuple[HydrocarbonCandidateInterval, ...],
) -> None:
    """Draw marker shapes at true whole-well depth; dense collisions use horizontal lanes."""

    y_positions = tuple(
        _depth_y(
            (candidate.top_depth + candidate.bottom_depth) / 2.0,
            depth_min,
            depth_max,
            target.top(),
            target.height(),
        )
        for candidate in candidates
    )
    zone_width = min(420.0, max(140.0, target.width() * 0.48))
    badge_width = 58.0
    badge_height = 18.0
    badge_gap = 6.0
    badge_centers = tuple(
        min(
            max(y, target.top() + badge_height / 2.0 + 2.0),
            target.bottom() - badge_height / 2.0 - 2.0,
        )
        for y in y_positions
    )
    coded_lanes = marker_lanes(
        badge_centers,
        minimum_gap=badge_height + 2.0,
    )
    coded_lane_count = max(coded_lanes, default=0) + 1
    show_codes = (
        coded_lane_count * (badge_width + badge_gap) <= zone_width
    )

    if show_codes:
        for candidate, center_y, lane in zip(
            candidates,
            badge_centers,
            coded_lanes,
            strict=True,
        ):
            spec = fluid_marker_spec(candidate.fluid_hypothesis)
            box_right = target.right() - 7.0 - lane * (badge_width + badge_gap)
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
            painter.setPen(QPen(QColor(spec.color), 1.2))
            painter.drawRoundedRect(box, 3.0, 3.0)
            draw_fluid_marker(
                painter,
                QPointF(box.left() + 10.0, box.center().y()),
                spec,
                size=9.0,
            )
            font = print_font(7.2, text=spec.code)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor("#172033"))
            painter.drawText(
                QRectF(
                    box.left() + 18.0,
                    box.top(),
                    box.width() - 21.0,
                    box.height(),
                ),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                spec.code,
            )
        return

    marker_centers = tuple(
        min(max(y, target.top() + 6.0), target.bottom() - 6.0)
        for y in y_positions
    )
    marker_lanes_by_y = marker_lanes(marker_centers, minimum_gap=10.0)
    marker_lane_count = max(marker_lanes_by_y, default=0) + 1
    offsets = marker_lane_offsets(
        marker_lane_count,
        zone_width=zone_width,
        max_spacing=22.0,
    )
    lane_spacing = (
        offsets[1] - offsets[0]
        if len(offsets) > 1
        else min(22.0, zone_width)
    )
    marker_size = max(4.0, min(10.0, lane_spacing * 0.58))
    for candidate, y, lane in zip(
        candidates,
        marker_centers,
        marker_lanes_by_y,
        strict=True,
    ):
        spec = fluid_marker_spec(candidate.fluid_hypothesis)
        x = target.right() - 7.0 - offsets[lane]
        halo = QColor("#ffffff")
        halo.setAlpha(225)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(
            QRectF(
                x - marker_size / 2.0 - 2.0,
                y - marker_size / 2.0 - 2.0,
                marker_size + 4.0,
                marker_size + 4.0,
            )
        )
        draw_fluid_marker(
            painter,
            QPointF(x, y),
            spec,
            size=marker_size,
        )


def _draw_whole_well_fluid_legend(
    painter: QPainter,
    rect: QRectF,
    candidates: tuple[HydrocarbonCandidateInterval, ...],
    language: AppLanguage,
) -> None:
    specs = fluid_marker_legend_specs(
        [item.fluid_hypothesis for item in candidates]
    )
    if not specs:
        return
    columns = min(6, len(specs))
    rows = (len(specs) + columns - 1) // columns
    cell_width = rect.width() / columns
    row_height = rect.height() / rows
    painter.setFont(print_font(7.0, text="GC/GO heavy/residual oil"))
    for index, spec in enumerate(specs):
        row = index // columns
        column = index % columns
        left = rect.left() + column * cell_width
        center_y = rect.top() + row * row_height + row_height / 2.0
        draw_fluid_marker(
            painter,
            QPointF(left + 7.0, center_y),
            spec,
            size=7.0,
        )
        painter.setPen(QColor("#172033"))
        painter.drawText(
            QRectF(left + 14.0, center_y - 7.0, cell_width - 16.0, 14.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"{spec.code} {spec.label(language)}",
        )

def _depth_y(
    depth: float,
    depth_min: float,
    depth_max: float,
    top: float,
    height: float,
) -> float:
    return top + (float(depth) - depth_min) / (depth_max - depth_min) * height


def _sample_indices(size: int, *, limit: int) -> np.ndarray:
    if size <= limit:
        return np.arange(size, dtype=np.int64)
    return np.linspace(0, size - 1, limit, dtype=np.int64)


def _labels(language: AppLanguage) -> dict[str, str]:
    return {
        AppLanguage.RU: {
            "title": "Графики интерпретационных кривых по глубине",
            "note": (
                "Каждая кривая масштабирована внутри своей дорожки по диапазону "
                "p5–p95; масштаб служит для сопоставления формы, а не абсолютных "
                "значений разных методов."
            ),
            "depth": "Глубина",
            "total": "Общий и нормализованный газ",
            "opus": "Показатели ОПУС",
            "ratios": "Haworth и Pixler",
            "drilling": "Буровой контекст и DEXP",
            "footer": (
                "Цветные полосы и маркеры формы/цвета показывают перспективные интервалы "
                "и предварительный тип флюида; расшифровка приведена в легенде, а полная "
                "формулировка — в таблице. Шкалы глубины продублированы слева и справа; "
                "0–100 над дорожками показывает положение внутри диапазона p5–p95."
            ),
        },
        AppLanguage.KK: {
            "title": "Тереңдік бойынша интерпретациялық қисықтар графиктері",
            "note": (
                "Әр қисық өз жолында p5–p95 ауқымы бойынша масштабталған; масштаб "
                "әртүрлі әдістердің абсолют мәндерін емес, пішінін салыстыруға арналған."
            ),
            "depth": "Тереңдік",
            "total": "Жалпы және нормаланған газ",
            "opus": "ОПУС көрсеткіштері",
            "ratios": "Haworth және Pixler",
            "drilling": "Бұрғылау контексті және DEXP",
            "footer": (
                "Түсті жолақтар мен пішін/түс маркерлері перспективалы аралықтарды және "
                "флюидтің алдын ала түрін көрсетеді; түсіндірме легендада, толық мәтін "
                "кестеде беріледі. Тереңдік шкаласы екі жақта қайталанады; 0–100 мәндері "
                "p5–p95 ауқымындағы орынды көрсетеді."
            ),
        },
        AppLanguage.EN: {
            "title": "Depth plots of interpretation curves",
            "note": (
                "Each curve is scaled within its track to the p5–p95 range; this "
                "scale compares shape and does not imply that absolute values from "
                "different methods are equivalent."
            ),
            "depth": "Depth",
            "total": "Total and normalized gas",
            "opus": "OPUS indicators",
            "ratios": "Haworth and Pixler",
            "drilling": "Drilling context and DEXP",
            "footer": (
                "Colored bands plus shape/colour markers show prospective intervals and "
                "preliminary fluid type; the legend decodes markers and the table keeps "
                "the full wording. Depth scales are shown on both sides; 0–100 labels "
                "show position within each p5–p95 range."
            ),
        },
    }[language]


__all__ = [
    "hydrocarbon_interpretation_chart_data_uri",
    "hydrocarbon_interpretation_html_with_chart",
]
