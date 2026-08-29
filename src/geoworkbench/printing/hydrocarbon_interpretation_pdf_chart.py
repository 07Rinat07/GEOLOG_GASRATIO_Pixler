from __future__ import annotations

from math import ceil, floor, log10

import numpy as np
from PySide6.QtCore import QLineF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from geoworkbench.domain.models import CurveData, Dataset
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
from geoworkbench.printing.unicode_support import print_font
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
)
from geoworkbench.services.localization import AppLanguage


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


def render_chart_pages(
    canvas: PageCanvas,
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

    available_height = (
        canvas.content_rect.height()
        - CHART_HEADER_HEIGHT
        - CHART_TRACK_HEADER_HEIGHT
        - CHART_LEGEND_HEIGHT
        - CHART_NOTE_HEIGHT
    )
    pages = plan_depth_pages(
        float(np.nanmin(depth[finite_depth])),
        float(np.nanmax(depth[finite_depth])),
        available_height,
    )
    ranges = _curve_ranges(panels, dataset)
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
        _draw_legend(
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
    intervals: tuple[tuple[float, float], ...],
    language: AppLanguage,
) -> None:
    painter.fillRect(rect, QColor("#ffffff"))
    step = _nice_tick_step(page.span, target_ticks=8)
    for tick in _depth_ticks(page, step):
        y = _depth_y(tick, page, rect)
        painter.setPen(QPen(QColor("#d8e0e8"), 0.45))
        painter.drawLine(QLineF(rect.left(), y, rect.right(), y))
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

    _draw_interval_bands(painter, rect, page, intervals)
    heading = _labels(language)[panel_name]
    heading_font = print_font(7.5, text=heading)
    heading_font.setBold(True)
    painter.setFont(heading_font)
    painter.setPen(QColor("#172033"))
    painter.drawText(
        QRectF(rect.left(), rect.top() - 32.0, rect.width(), 15.0),
        Qt.AlignmentFlag.AlignCenter,
        heading,
    )
    _draw_curves(painter, rect, page, dataset, curves, ranges)
    painter.setPen(QPen(QColor("#334155"), 1.0))
    painter.drawRect(rect)


def _draw_interval_bands(
    painter: QPainter,
    rect: QRectF,
    page: DepthPage,
    intervals: tuple[tuple[float, float], ...],
) -> None:
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
            QRectF(
                rect.left(),
                min(y1, y2),
                rect.width(),
                max(1.0, abs(y2 - y1)),
            ),
            color,
        )


def _draw_curves(
    painter: QPainter,
    rect: QRectF,
    page: DepthPage,
    dataset: Dataset,
    curves: tuple[CurveData, ...],
    ranges: dict[str, tuple[float, float]],
) -> None:
    depth = np.asarray(dataset.depth, dtype=np.float64)
    indices = np.flatnonzero(
        np.isfinite(depth)
        & (depth >= page.top_depth)
        & (depth <= page.bottom_depth)
    )
    indices = indices[np.argsort(depth[indices], kind="stable")]
    if indices.size > 2_500:
        positions = np.linspace(0, indices.size - 1, 2_500, dtype=np.int64)
        indices = indices[positions]

    painter.save()
    painter.setClipRect(rect.adjusted(0.8, 0.8, -0.8, -0.8))
    curve_rect = rect.adjusted(3.0, 0.0, -3.0, 0.0)
    for curve_index, curve in enumerate(curves):
        values = np.asarray(curve.values, dtype=np.float64)
        value_range = ranges.get(curve.metadata.curve_id)
        if values.shape != depth.shape or value_range is None:
            continue
        low, high = value_range
        painter.setPen(QPen(QColor(_COLORS[curve_index % len(_COLORS)]), 0.8))
        previous: tuple[float, float] | None = None
        for row_index in indices:
            value = values[row_index]
            if not np.isfinite(value):
                previous = None
                continue
            normalized = float(np.clip((value - low) / (high - low), 0.0, 1.0))
            current = (
                curve_rect.left() + normalized * curve_rect.width(),
                _depth_y(float(depth[row_index]), page, curve_rect),
            )
            if previous is not None:
                painter.drawLine(
                    QLineF(previous[0], previous[1], current[0], current[1])
                )
            previous = current
    painter.restore()


def _draw_legend(
    painter: QPainter,
    legend_rect: QRectF,
    panel_index: int,
    panel_count: int,
    curves: tuple[CurveData, ...],
    ranges: dict[str, tuple[float, float]],
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
        painter.setPen(QPen(color, 1.8))
        painter.drawLine(
            QLineF(column.left(), y + 5.0, column.left() + 17.0, y + 5.0)
        )
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
            if values.shape != dataset.depth.shape:
                continue
            finite = values[np.isfinite(values)]
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
    marker_groups = (
        _OPUS_PANEL_METHOD_MARKERS
        if report.report_profile == "opus"
        else _PANEL_METHOD_MARKERS
    )
    for panel_name, fallback_order in marker_groups:
        curves: list[CurveData] = []
        seen: set[str] = set()
        for mnemonic in (*preferred, *fallback_order):
            curve = dataset.curve_by_mnemonic(_strip_source_prefix(mnemonic))
            if curve is None or curve.metadata.curve_id in seen:
                continue
            if curve.metadata.original_mnemonic.upper() not in fallback_order:
                continue
            values = np.asarray(curve.values, dtype=np.float64)
            if (
                values.shape != dataset.depth.shape
                or np.count_nonzero(np.isfinite(values)) < 2
            ):
                continue
            curves.append(curve)
            seen.add(curve.metadata.curve_id)
            if len(curves) >= (3 if panel_name == "total" else 5):
                break
        result.append((panel_name, tuple(curves)))
    return tuple(result)


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
    minimum_depth_gap = (
        page.span
        * _MIN_AXIS_LABEL_GAP_POINTS
        / max(float(plot_height_points), 1.0)
    )
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


def _strip_source_prefix(value: str) -> str:
    stripped = value.strip()
    for prefix in ("server:", "local-calculation:"):
        if stripped.casefold().startswith(prefix):
            return stripped[len(prefix) :].strip()
    return stripped


def _labels(language: AppLanguage) -> dict[str, str]:
    return {
        AppLanguage.RU: {
            "title": "Графики интерпретационных кривых по глубине",
            "page": (
                "Лист графика {current} из {total}: {top:.2f}–{bottom:.2f} "
                "{unit}; вертикальный масштаб 1:{scale}"
            ),
            "depth": "Глубина",
            "total": "Общий и нормализованный газ",
            "opus": "Показатели ОПУС",
            "ratios": "Haworth и Pixler",
            "drilling": "Буровой контекст и DEXP",
            "note": (
                "Кривые нормированы внутри дорожек по p1–p99. Оранжевые полосы — "
                "перспективные интервалы. Каждый лист сохраняет физический масштаб "
                "глубины; шкалы и внешние границы повторяются слева и справа."
            ),
        },
        AppLanguage.KK: {
            "title": "Тереңдік бойынша интерпретациялық қисықтар графиктері",
            "page": (
                "График беті {current}/{total}: {top:.2f}–{bottom:.2f} {unit}; "
                "тік масштаб 1:{scale}"
            ),
            "depth": "Тереңдік",
            "total": "Жалпы және нормаланған газ",
            "opus": "ОПУС көрсеткіштері",
            "ratios": "Haworth және Pixler",
            "drilling": "Бұрғылау контексті және DEXP",
            "note": (
                "Қисықтар жол ішінде p1–p99 бойынша нормаланады. Қызғылт сары "
                "жолақтар — перспективалы аралықтар. Әр бет тереңдіктің физикалық "
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
            "total": "Total and normalized gas",
            "opus": "OPUS indicators",
            "ratios": "Haworth and Pixler",
            "drilling": "Drilling context and DEXP",
            "note": (
                "Curves are normalized within tracks to p1–p99. Orange bands mark "
                "prospective intervals. Every sheet preserves a physical depth scale; "
                "scales and outer borders repeat on both sides."
            ),
        },
    }[language]


__all__ = ["render_chart_pages"]
