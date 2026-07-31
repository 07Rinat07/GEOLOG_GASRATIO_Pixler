from __future__ import annotations

from html import escape

import numpy as np
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QLineF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen

from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.printing.unicode_support import print_font
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
    hydrocarbon_interpretation_html,
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

    base = inject_interval_gas_statistics_html(base, report, dataset, language)
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
) -> str:
    """Render available interpretation curves against depth as a PNG data URI."""

    depth = np.asarray(dataset.depth, dtype=np.float64)
    finite_depth = np.isfinite(depth)
    if depth.ndim != 1 or np.count_nonzero(finite_depth) < 2:
        return ""

    panels = _panel_curves(report, dataset)
    panels = tuple((panel, curves) for panel, curves in panels if curves)
    if not panels:
        return ""

    image = QImage(2_000, 1_280, QImage.Format.Format_ARGB32_Premultiplied)
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

        depth_min = float(np.nanmin(depth[finite_depth]))
        depth_max = float(np.nanmax(depth[finite_depth]))
        if depth_max <= depth_min:
            depth_max = depth_min + 1.0

        plot_top = 130.0
        plot_bottom = 1_015.0
        plot_height = plot_bottom - plot_top
        outer_margin = 35.0
        depth_width = 128.0
        axis_gap = 16.0
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
        panel_left = left_depth_rect.right() + axis_gap
        panel_right = right_depth_rect.left() - axis_gap
        panel_gap = 20.0
        panel_area_width = panel_right - panel_left
        panel_width = (
            panel_area_width - panel_gap * (len(panels) - 1)
        ) / len(panels)

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

        intervals = tuple(
            (candidate.top_depth, candidate.bottom_depth)
            for candidate in report.candidates
        )
        for panel_index, (panel_name, curves) in enumerate(panels):
            left = panel_left + panel_index * (panel_width + panel_gap)
            rect = QRectF(left, plot_top, panel_width, plot_height)
            _draw_panel(
                painter,
                rect,
                depth,
                finite_depth,
                depth_min,
                depth_max,
                panel_name,
                curves,
                intervals,
                language,
            )

        painter.setFont(print_font(9.0, text=labels["footer"]))
        painter.setPen(QColor("#475569"))
        painter.drawText(
            QRectF(90.0, 1_170.0, 1_820.0, 84.0),
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
        candidates = [*preferred, *fallback_order]
        curves: list[CurveData] = []
        seen: set[str] = set()
        for mnemonic in candidates:
            curve = dataset.curve_by_mnemonic(_strip_source_prefix(mnemonic))
            if curve is None or curve.metadata.curve_id in seen:
                continue
            canonical = curve.metadata.original_mnemonic.upper()
            if canonical not in fallback_order:
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


def _draw_panel(
    painter: QPainter,
    rect: QRectF,
    depth: np.ndarray,
    finite_depth: np.ndarray,
    depth_min: float,
    depth_max: float,
    panel_name: str,
    curves: tuple[CurveData, ...],
    intervals: tuple[tuple[float, float], ...],
    language: AppLanguage,
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

    for top_depth, bottom_depth in intervals:
        top = _depth_y(top_depth, depth_min, depth_max, rect.top(), rect.height())
        bottom = _depth_y(
            bottom_depth,
            depth_min,
            depth_max,
            rect.top(),
            rect.height(),
        )
        band_top = min(top, bottom)
        band_height = max(2.0, abs(bottom - top))
        color = QColor("#f59e0b")
        color.setAlpha(34)
        painter.fillRect(
            QRectF(rect.left(), band_top, rect.width(), band_height),
            color,
        )

    title_font = print_font(11.0, text=labels[panel_name])
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.setPen(QColor("#172033"))
    painter.drawText(
        QRectF(rect.left(), rect.top() - 58.0, rect.width(), 27.0),
        Qt.AlignmentFlag.AlignCenter,
        labels[panel_name],
    )

    sampled = _sample_indices(depth.size, limit=1_800)
    curve_rect = rect.adjusted(7.0, 1.0, -7.0, -1.0)
    painter.save()
    painter.setClipRect(rect.adjusted(1.0, 1.0, -1.0, -1.0))
    legend_rows: list[tuple[QColor, str]] = []
    for curve_index, curve in enumerate(curves):
        values = np.asarray(curve.values, dtype=np.float64)
        usable = finite_depth & np.isfinite(values)
        if np.count_nonzero(usable) < 2:
            continue
        finite_values = values[usable]
        low = float(np.nanpercentile(finite_values, 1.0))
        high = float(np.nanpercentile(finite_values, 99.0))
        if not np.isfinite(low) or not np.isfinite(high):
            continue
        if high <= low:
            high = low + max(1.0, abs(low) * 0.01)
        color = QColor(_COLORS[curve_index % len(_COLORS)])
        painter.setPen(QPen(color, 2.2))
        previous: tuple[float, float] | None = None
        for index in sampled:
            if not usable[index]:
                previous = None
                continue
            normalized = float(
                np.clip((values[index] - low) / (high - low), 0.0, 1.0)
            )
            x = curve_rect.left() + normalized * curve_rect.width()
            y = _depth_y(
                depth[index],
                depth_min,
                depth_max,
                curve_rect.top(),
                curve_rect.height(),
            )
            current = (float(x), float(y))
            if previous is not None:
                painter.drawLine(
                    QLineF(previous[0], previous[1], current[0], current[1])
                )
            previous = current

        legend = curve.metadata.original_mnemonic
        if curve.metadata.unit:
            legend += f" [{curve.metadata.unit}]"
        legend += f"  p1={low:.4g}; p99={high:.4g}"
        legend_rows.append((color, legend))
    painter.restore()

    legend_top = rect.bottom() + 12.0
    for row_index, (color, legend) in enumerate(legend_rows):
        legend_y = legend_top + row_index * 21.0
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
            "note": (
                "Каждая кривая масштабирована внутри своей дорожки по диапазону "
                "p1–p99; масштаб служит для сопоставления формы, а не абсолютных "
                "значений разных методов."
            ),
            "depth": "Глубина",
            "total": "Общий и нормализованный газ",
            "ratios": "Haworth и Pixler",
            "drilling": "Буровой контекст и DEXP",
            "footer": (
                "Оранжевые полосы показывают перспективные интервалы выше выбранного "
                "порога robust z. Шкалы глубины продублированы слева и справа; числа "
                "0–100 над дорожками показывают положение внутри диапазона p1–p99. "
                "Отсутствующая дорожка означает, что соответствующие кривые не найдены "
                "или имеют недостаточно корректных отсчётов."
            ),
        },
        AppLanguage.KK: {
            "title": "Тереңдік бойынша интерпретациялық қисықтар графиктері",
            "note": (
                "Әр қисық өз жолында p1–p99 ауқымы бойынша масштабталған; масштаб "
                "әртүрлі әдістердің абсолют мәндерін емес, пішінін салыстыруға арналған."
            ),
            "depth": "Тереңдік",
            "total": "Жалпы және нормаланған газ",
            "ratios": "Haworth және Pixler",
            "drilling": "Бұрғылау контексті және DEXP",
            "footer": (
                "Қызғылт сары жолақтар таңдалған robust z шегінен жоғары "
                "перспективалы аралықтарды көрсетеді. Тереңдік шкаласы сол және оң "
                "жақта қайталанады; жолдардың үстіндегі 0–100 мәндері p1–p99 "
                "ауқымындағы орынды көрсетеді."
            ),
        },
        AppLanguage.EN: {
            "title": "Depth plots of interpretation curves",
            "note": (
                "Each curve is scaled within its track to the p1–p99 range; this "
                "scale compares shape and does not imply that absolute values from "
                "different methods are equivalent."
            ),
            "depth": "Depth",
            "total": "Total and normalized gas",
            "ratios": "Haworth and Pixler",
            "drilling": "Drilling context and DEXP",
            "footer": (
                "Orange bands mark prospective intervals above the selected robust-z "
                "threshold. Depth scales are shown on both sides; the 0–100 labels "
                "above each track indicate position within its p1–p99 range. A missing "
                "track means that the curves are unavailable or contain too few valid "
                "samples."
            ),
        },
    }[language]


__all__ = [
    "hydrocarbon_interpretation_chart_data_uri",
    "hydrocarbon_interpretation_html_with_chart",
]
