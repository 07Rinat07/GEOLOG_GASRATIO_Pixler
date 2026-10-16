from __future__ import annotations

import base64
from collections.abc import Sequence
from math import ceil

import numpy as np
from numpy.typing import NDArray
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QImage, QPainter, QPainterPath, QPen, QPolygonF

from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.services.hydrocarbon_interpretation import HydrocarbonCandidateInterval
from geoworkbench.printing.hydrocarbon_fluid_markers import (
    draw_fluid_marker, fluid_marker_at_depth,
)
from geoworkbench.printing.report_painter_fonts import point_coordinate_font
from geoworkbench.printing.pixler_profile_annotations import (
    pixler_profile_caption, pixler_profile_trend, pixler_visual_tendency,
)
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.services.gas_curve_presentation import GasRatioScale, gas_ratio_scale
from geoworkbench.services.localization import AppLanguage

_ALIASES = {
    "WH": {"WH", "WETNESS"},
    "BH": {"BH", "BALANCE"},
    "CH": {"CH", "CHARACTER"},
    **{f"C1_C{i}": {f"C1_C{i}", f"PIXLER_C1_C{i}"} for i in range(2, 6)},
}
RATIO_REFERENCE_WIDTH = 1000.0
RATIO_REFERENCE_HEIGHT = 840.0

_DEPTH_COLORS = ("#2563eb", "#16a34a", "#ea580c", "#db2777", "#9333ea", "#0891b2")


def ratio_identifier(curve: CurveData) -> str:
    tokens = {
        str(value or "").strip().upper()
        for value in (
            curve.metadata.original_mnemonic,
            curve.metadata.canonical_mnemonic,
        )
    }
    return next((name for name, aliases in _ALIASES.items() if tokens & aliases), "")


def ratio_reference_tracks(
    curves: Sequence[CurveData],
) -> tuple[tuple[CurveData, GasRatioScale, int], ...]:
    """Wh and Bh share an axis; Ch has its own linear axis, as in the reference."""
    recognized = [(curve, ratio_identifier(curve)) for curve in curves]
    haworth = [(curve, name) for curve, name in recognized if name in {"WH", "BH", "CH"}]
    if haworth:
        groups = {"WH": 0, "BH": 0, "CH": 1}
        used = sorted({groups[name] for _, name in haworth})
        return tuple(
            (
                curve,
                GasRatioScale(0.0, 5.0) if name == "CH" else GasRatioScale(0.1, 100.0, True),
                used.index(groups[name]),
            )
            for curve, name in haworth
        )
    # A dataset containing only Pixler ratios still retains a depth display.
    return tuple(
        (curve, scale, index)
        for index, curve in enumerate(curves)
        if (
            scale := gas_ratio_scale(
                (curve.metadata.original_mnemonic, curve.metadata.canonical_mnemonic)
            )
        )
        is not None
    )


def ratio_reference_color(curve: CurveData) -> QColor:
    return QColor(
        {"WH": "#ef4444", "BH": "#1d4ed8", "CH": "#15803d"}.get(ratio_identifier(curve), "#7c3aed")
    )


def reference_pairs(
    dataset: Dataset, name: str
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Pair values by source row; never join independently sampled arrays."""
    ratio = next(
        (curve for curve in dataset.curves.values() if ratio_identifier(curve) == name), None
    )
    methane = dataset.curve_by_mnemonic("C1")
    wetness = next(
        (curve for curve in dataset.curves.values() if ratio_identifier(curve) == "WH"), None
    )
    if ratio is None:
        return np.array([]), np.array([]), np.array([])
    if wetness is not None:
        # Wh = 100 * heavy / sumHC, hence C1/sumHC = 1 - Wh/100.
        fraction = 1.0 - np.asarray(wetness.values, dtype=float) / 100.0
    elif methane is not None:
        components = [methane, dataset.curve_by_mnemonic("C2"), dataset.curve_by_mnemonic("C3")]
        for number in (4, 5):
            iso, normal = (dataset.curve_by_mnemonic(f"{prefix}C{number}") for prefix in ("I", "N"))
            components.extend(
                [iso, normal]
                if iso is not None and normal is not None
                else [dataset.curve_by_mnemonic(f"C{number}")]
            )
        if any(component is None for component in components):
            return np.array([]), np.array([]), np.array([])
        total = np.sum(
            [component.values for component in components if component is not None], axis=0
        )
        fraction = np.divide(
            methane.values, total, out=np.full(total.shape, np.nan), where=total > 0
        )
    else:
        return np.array([]), np.array([]), np.array([])
    values, depth = np.asarray(ratio.values, dtype=float), np.asarray(dataset.depth, dtype=float)
    if values.shape != depth.shape or fraction.shape != depth.shape:
        return np.array([]), np.array([]), np.array([])
    valid = np.isfinite(values) & np.isfinite(fraction) & np.isfinite(depth)
    valid &= (fraction >= 0) & (fraction <= 1) & (values >= 0)
    return values[valid], fraction[valid], depth[valid]


def has_ratio_reference_summary(dataset: Dataset) -> bool:
    if any(reference_pairs(dataset, name)[0].size for name in ("BH", "CH")):
        return True
    ratios = {ratio_identifier(curve): curve for curve in dataset.curves.values()}
    keys = [f"C1_C{i}" for i in range(2, 6)]
    if not all(key in ratios for key in keys):
        return False
    matrix = np.column_stack([ratios[key].values for key in keys])
    return bool(np.any(np.all(np.isfinite(matrix) & (matrix > 0), axis=1)))


def _depth_pen(index: int, width: float) -> QPen:
    styles = (Qt.PenStyle.SolidLine, Qt.PenStyle.DashLine, Qt.PenStyle.DotLine,
              Qt.PenStyle.DashDotLine, Qt.PenStyle.DashDotDotLine, Qt.PenStyle.CustomDashLine)
    pen = QPen(QColor(_DEPTH_COLORS[index]), width, styles[index])
    if index == 5:
        pen.setDashPattern([6, 2, 1, 2, 1, 2, 1, 2])
    return pen


def _depth_marker(painter: QPainter, center: QPointF, index: int, radius: float = 2.0) -> None:
    path = QPainterPath()
    if index == 0:
        path.addEllipse(center, radius, radius)
    else:
        vertices = {
            1: ((-1, -1), (1, -1), (1, 1), (-1, 1)),
            2: ((0, -1), (1, 0), (0, 1), (-1, 0)),
            3: ((0, -1), (1, 1), (-1, 1)),
            4: ((-1, -1), (1, -1), (0, 1)),
            5: ((-1, 0), (-0.5, -1), (0.5, -1), (1, 0), (0.5, 1), (-0.5, 1)),
        }[index]
        path.addPolygon(QPolygonF([QPointF(center.x() + x * radius, center.y() + y * radius) for x, y in vertices]))
        path.closeSubpath()
    painter.save()
    try:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(_DEPTH_COLORS[index]))
        painter.drawPath(path)
    finally:
        painter.restore()


def _text(painter: QPainter, rect: QRectF, text: str, size: float | None = None,
          *, color: str | None = None) -> None:
    visual = modern_oilfield_report_profile()
    painter.setPen(QColor(color or visual.palette.text))
    fitted_size = visual.typography.body_pt if size is None else size
    # Ratio plots use a virtual 1000-unit canvas so a portrait PDF scales its
    # labels to half-size. Font sizes must remain readable in *physical* points
    # after that fit. Account for the printer's independent DPI transform.
    device = painter.device()
    printer_scale = max(1.0, float(device.logicalDpiX())) / 72.0
    canvas_scale = abs(painter.worldTransform().m11()) / printer_scale
    fitted_size = max(fitted_size, 7.2 / max(canvas_scale, 0.01))
    font = point_coordinate_font(fitted_size, text=text, paint_device=device)
    # Fit in virtual layout coordinates; the font adapter handles print DPI.
    for _ in range(8):
        metrics = QFontMetricsF(font, device)
        factor = min(rect.width() / max(1.0, metrics.horizontalAdvance(text)), rect.height() / max(1.0, metrics.height()))
        if factor >= 1.0 or fitted_size <= 1.0:
            break
        fitted_size = max(1.0, fitted_size * factor * 0.98)
        font = point_coordinate_font(fitted_size, text=text, paint_device=device)
    painter.setFont(font)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)


def _compact_tick(value: float) -> str:
    """Avoid 3.61-pt scientific notation in narrow ratio-axis tick slots."""
    if abs(value) >= 1_000:
        return f"{value / 1_000:.2g}k"
    if abs(value) >= 100:
        return f"{value:.0f}"
    return f"{value:.2g}"


def _paired_x_tick_rect(plot: QRectF, tick: int) -> QRectF:
    """Keep the first X tick clear of the Y=0 label at both plot origins."""
    x = plot.left() + tick / 5 * plot.width()
    if tick == 0:
        # Keep zero centred on its gridline without touching the Y-axis label.
        return QRectF(x - 6.0, plot.bottom() + 1.0, 12.0, 21.0)
    return QRectF(x - 23.0, plot.bottom() + 1.0, 46.0, 21.0)


def _pixler_log_tick_powers(minimum: float, maximum: float, plot_height: float) -> tuple[int, ...]:
    """Bound label density: neighbouring 24-unit tick boxes never intersect."""
    start, end = int(minimum), int(maximum)
    if end <= start or plot_height < 24.0:
        return (start,)
    label_slots = max(2, int(plot_height // 32.0) + 1)
    span = end - start
    # Check spacing after choosing integer powers, not before rounding.
    spacing_step = ceil(24.0 * span / plot_height)
    budget_step = ceil(span / (label_slots - 1))
    step = max(1, spacing_step, budget_step)
    powers = list(range(start, end, step))
    if len(powers) > 1 and end - powers[-1] < step:
        powers.pop()
    powers.append(end)
    return tuple(powers)


def _axes(painter: QPainter, rect: QRectF) -> None:
    palette = modern_oilfield_report_profile().palette
    painter.setPen(QPen(QColor(palette.border), 0.6))
    for index in range(6):
        fraction = index / 5
        painter.drawLine(
            QLineF(
                rect.left() + fraction * rect.width(),
                rect.top(),
                rect.left() + fraction * rect.width(),
                rect.bottom(),
            )
        )
        painter.drawLine(
            QLineF(
                rect.left(),
                rect.top() + fraction * rect.height(),
                rect.right(),
                rect.top() + fraction * rect.height(),
            )
        )
    painter.setPen(QPen(QColor(palette.border_strong), 1))
    painter.drawRect(rect)


def paint_ratio_reference_summary(
    painter: QPainter,
    target: QRectF,
    dataset: Dataset,
    language: AppLanguage,
    *,
    candidates: Sequence[HydrocarbonCandidateInterval] = (),
) -> bool:
    ratios = {
        ratio_identifier(curve): curve
        for curve in dataset.curves.values()
        if ratio_identifier(curve)
    }
    if not ratios or not has_ratio_reference_summary(dataset):
        return False
    painter.save()
    try:
        painter.translate(target.topLeft())
        scale = min(target.width() / RATIO_REFERENCE_WIDTH, target.height() / RATIO_REFERENCE_HEIGHT)
        painter.scale(scale, scale)
        visual = modern_oilfield_report_profile()
        palette, typography = visual.palette, visual.typography
        painter.fillRect(QRectF(0, 0, RATIO_REFERENCE_WIDTH, RATIO_REFERENCE_HEIGHT), QColor(palette.page))
        title = {
            AppLanguage.RU: "Газовые отношения: корреляция и профиль Пикслера",
            AppLanguage.KK: "Газ қатынастары: корреляция және Pixler профилі",
            AppLanguage.EN: "Gas ratios: correlation and Pixler profile",
        }[language]
        _text(painter, QRectF(0, 0, 1000, 35), title, typography.title_pt)
        all_depth = np.asarray(dataset.depth, dtype=float)
        finite_depth = all_depth[np.isfinite(all_depth)]
        low_depth = float(finite_depth.min()) if finite_depth.size else 0.0
        high_depth = float(finite_depth.max()) if finite_depth.size else 1.0
        for index, name in enumerate(("BH", "CH")):
            plot = QRectF(65 + index * 490, 80, 395, 205)
            _axes(painter, plot)
            x, y, depth = reference_pairs(dataset, name)
            maximum = max(1.0, float(np.max(x)) * 1.05) if x.size else 1.0
            if not x.size:
                _text(
                    painter,
                    plot,
                    {
                        AppLanguage.RU: "Нет парных измерений",
                        AppLanguage.KK: "Жұп өлшемдер жоқ",
                        AppLanguage.EN: "Paired observations unavailable",
                    }[language],
                )
            _text(
                painter,
                QRectF(plot.left(), 309, plot.width(), 21),
                "Balance (Bh)" if name == "BH" else "Character (Ch)",
            )
            _text(painter, QRectF(plot.left(), 46, plot.width(), 28), "C1 / ΣHC")
            for tick in range(6):
                _text(
                    painter,
                    _paired_x_tick_rect(plot, tick),
                    _compact_tick(maximum * tick / 5),
                    typography.caption_pt,
                )
                _text(
                    painter,
                    QRectF(plot.left() - 43, plot.bottom() - tick / 5 * plot.height() - 12, 37, 24),
                    f"{tick / 5:.1f}",
                    typography.caption_pt,
                )
            selection = (
                np.arange(x.size) if x.size <= 1200 else np.linspace(0, x.size - 1, 1200, dtype=int)
            )
            painter.save()
            painter.setClipRect(plot)
            painter.setPen(Qt.PenStyle.NoPen)
            for row in selection:
                bin_index = min(
                    5, int((depth[row] - low_depth) / max(1e-9, high_depth - low_depth) * 6)
                )
                _depth_marker(
                    painter,
                    QPointF(
                        plot.left() + x[row] / maximum * plot.width(),
                        plot.bottom() - y[row] * plot.height(),
                    ),
                    max(0, bin_index),
                )
            painter.restore()
        bin_width = abs(high_depth - low_depth) / 6.0
        depth_decimals = 0 if bin_width >= 1.0 else min(
            6, max(1, int(np.ceil(-np.log10(max(bin_width, 1e-6)))) + 1),
        )
        for index in range(len(_DEPTH_COLORS)):
            start = low_depth + (high_depth - low_depth) * index / 6
            end = low_depth + (high_depth - low_depth) * (index + 1) / 6
            painter.setPen(_depth_pen(index, 1.5))
            painter.drawLine(QLineF(65 + index * 150, 346, 100 + index * 150, 346))
            _depth_marker(painter, QPointF(82.5 + index * 150, 346), index, 3)
            _text(painter, QRectF(101 + index * 150, 335, 113, 24), f"{start:.{depth_decimals}f}–{end:.{depth_decimals}f} m", typography.caption_pt)
        plot = QRectF(65, 385, 610, 295)
        _axes(painter, plot)
        _text(painter, QRectF(65, 362, 610, 20), "Pixler · C1/C2 – C1/C5", typography.section_pt)
        keys = [f"C1_C{i}" for i in range(2, 6)]
        if all(key in ratios for key in keys):
            matrix = np.column_stack([ratios[key].values for key in keys])
            valid = np.flatnonzero(
                np.all(np.isfinite(matrix) & (matrix > 0), axis=1) & np.isfinite(all_depth)
            )
            valid = valid[np.argsort(all_depth[valid], kind="stable")]
            selected = (
                valid[np.linspace(0, valid.size - 1, min(6, valid.size), dtype=int)]
                if valid.size
                else np.array([], dtype=int)
            )
            maximum = (
                max(3.0, float(np.ceil(np.log10(np.max(matrix[valid]))))) if valid.size else 3.0
            )
            minimum = (
                min(0.0, float(np.floor(np.log10(np.min(matrix[valid]))))) if valid.size else 0.0
            )
            # These decade bands orient the logarithmic scale only. They are not
            # universal phase boundaries; phase labels use interval evidence.
            for lower, upper, shade in (
                (minimum, min(1.0, maximum), "#e7f6ea"),
                (max(1.0, minimum), min(2.0, maximum), "#e8f1ff"),
                (max(2.0, minimum), maximum, "#fff0ed"),
            ):
                if upper <= lower:
                    continue
                top = plot.bottom() - (upper - minimum) / (maximum - minimum) * plot.height()
                bottom = plot.bottom() - (lower - minimum) / (maximum - minimum) * plot.height()
                painter.fillRect(QRectF(plot.left(), top, plot.width(), bottom - top), QColor(shade))
            for power in _pixler_log_tick_powers(minimum, maximum, plot.height()):
                tick_y = plot.bottom() - (power - minimum) / (maximum - minimum) * plot.height()
                painter.setPen(QPen(QColor(palette.border), 0.7))
                painter.drawLine(QLineF(plot.left(), tick_y, plot.right(), tick_y))
                _text(painter, QRectF(12, tick_y - 12, 45, 24), f"{10.0**power:g}", typography.caption_pt)
            # Order callouts by endpoint height so neighbouring leader lines do not cross.
            label_order = sorted((int(row) for row in selected), key=lambda row: -matrix[row, -1])
            label_slots = {row: index for index, row in enumerate(label_order)}
            for profile_index, row in enumerate(selected):
                depth_bin = min(
                    5,
                    max(
                        0, int((all_depth[row] - low_depth) / max(1e-9, high_depth - low_depth) * 6)
                    ),
                )
                painter.setPen(_depth_pen(depth_bin, 1.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                points = [
                    QPointF(
                        plot.left() + index / 3 * plot.width(),
                        plot.bottom()
                        - (np.log10(value) - minimum) / (maximum - minimum) * plot.height(),
                    )
                    for index, value in enumerate(matrix[row])
                ]
                path = QPainterPath(points[0])
                for point in points[1:]:
                    path.lineTo(point)
                painter.drawPath(path)
                phase = fluid_marker_at_depth(float(all_depth[row]), candidates)
                for point in points:
                    _depth_marker(painter, point, depth_bin)
                    # Keep the source coordinate and monochrome depth key intact.
                    # A separate adjacent symbol encodes interval phase evidence.
                    draw_fluid_marker(
                        painter, QPointF(point.x() + 9.0, point.y()), phase, size=7.0,
                    )
                trend = pixler_profile_trend(matrix[row].tolist())
                phase_caption, _trend_caption = pixler_profile_caption(phase.phase, trend, language)
                label_y = 386 + label_slots[int(row)] * 49
                label_rect = QRectF(704, label_y, 282, 47)
                color = _DEPTH_COLORS[depth_bin]
                cue_fill = QColor(color)
                cue_fill.setAlpha(22)
                painter.setPen(QPen(QColor(color), 0.9))
                painter.setBrush(cue_fill)
                painter.drawRoundedRect(label_rect, 3, 3)
                painter.setPen(_depth_pen(depth_bin, 1.5))
                painter.drawLine(QLineF(712, label_y + 8, 744, label_y + 8))
                _depth_marker(painter, QPointF(728, label_y + 8), depth_bin, 3)
                _text(painter, QRectF(749, label_y + 1, 232, 15),
                      f"{all_depth[row]:.2f} m · {phase.code}", typography.body_pt, color=color)
                _text(painter, QRectF(709, label_y + 16, 272, 15),
                      pixler_visual_tendency(trend, language), typography.caption_pt, color=color)
                _text(painter, QRectF(709, label_y + 31, 272, 15),
                      phase_caption, typography.caption_pt, color=color)
                painter.setPen(QPen(QColor(color), 1.1))
                endpoint = points[-1]
                elbow = QPointF(695, label_rect.center().y())
                painter.drawLine(QLineF(endpoint, elbow))
                painter.drawLine(QLineF(elbow, QPointF(label_rect.left(), elbow.y())))
                direction = elbow - endpoint
                length = max(1.0, (direction.x() ** 2 + direction.y() ** 2) ** 0.5)
                unit = direction / length
                normal = QPointF(-unit.y(), unit.x())
                painter.drawLine(QLineF(endpoint, endpoint + unit * 7.0 + normal * 3.0))
                painter.drawLine(QLineF(endpoint, endpoint + unit * 7.0 - normal * 3.0))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(endpoint, 4.0, 4.0)

        else:
            _text(
                painter,
                plot,
                {
                    AppLanguage.RU: "Нет полного набора C1/C2–C1/C5",
                    AppLanguage.KK: "C1/C2–C1/C5 толық жиыны жоқ",
                    AppLanguage.EN: "Complete C1/C2–C1/C5 profiles unavailable",
                }[language],
                typography.body_pt,
            )
        for index, key in enumerate(keys):
            _text(
                painter,
                QRectF(
                    plot.left() + index / 3 * plot.width() - 35,
                    690, 70, 19,
                ),
                key.replace("_", "/"),
                typography.caption_pt,
            )
        for index, (trend, color) in enumerate((
            ("rising", "#c62828"), ("mixed", "#2563eb"), ("falling", "#15803d"),
        )):
            card = QRectF(65 + index * 307, 720, 298, 30)
            cue_fill = QColor(color)
            cue_fill.setAlpha(18)
            painter.setPen(QPen(QColor(color), 0.8))
            painter.setBrush(cue_fill)
            painter.drawRoundedRect(card, 3, 3)
            _text(painter, card.adjusted(5, 2, -5, -2),
                  pixler_visual_tendency(trend, language), typography.caption_pt, color=color)
        _text(
            painter, QRectF(65, 760, 920, 28),
            {
                AppLanguage.RU: "Предварительно по форме профиля; не доказательство фазы или притока. Фон — порядок отношений, не границы фаз. ? — фаза не определена.",
                AppLanguage.KK: "Профиль пішіні бойынша алдын ала; фаза не ағын дәлелі емес. Фон — қатынастар реті, фаза шекарасы емес. ? — фаза анықталмаған.",
                AppLanguage.EN: "Preliminary shape cues, not proof of phase or flow. Background: ratio decades, not phase boundaries. ? — phase undetermined.",
            }[language], typography.footer_pt,
        )
        if all(key in ratios for key in keys) and valid.size:
            coverage = {
                AppLanguage.RU: "Полные профили: {start:.2f}–{end:.2f} м; данные проекта: {low:.2f}–{high:.2f} м. Показано {count} глубин.",
                AppLanguage.KK: "Толық профильдер: {start:.2f}–{end:.2f} м; жоба: {low:.2f}–{high:.2f} м. {count} тереңдік көрсетілген.",
                AppLanguage.EN: "Complete profiles: {start:.2f}–{end:.2f} m; project data: {low:.2f}–{high:.2f} m. {count} depths shown.",
            }[language].format(start=all_depth[valid[0]], end=all_depth[valid[-1]],
                               low=low_depth, high=high_depth, count=len(selected))
            _text(painter, QRectF(65, 798, 920, 24), coverage, typography.caption_pt)

    finally:
        painter.restore()
    return True


def ratio_reference_summary_uri(
    dataset: Dataset, language: AppLanguage,
    *, candidates: Sequence[HydrocarbonCandidateInterval] = (),
) -> str:
    image = QImage(1600, 1344, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(modern_oilfield_report_profile().palette.page))
    painter = QPainter(image)
    try:
        if not paint_ratio_reference_summary(painter, QRectF(image.rect()), dataset, language, candidates=candidates):
            return ""
    finally:
        painter.end()
    buffer_data = QByteArray()
    buffer = QBuffer(buffer_data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):  # type: ignore[call-overload]
        raise RuntimeError("Не удалось создать диаграммы газовых отношений")
    return "data:image/png;base64," + base64.b64encode(buffer_data.data()).decode("ascii")
