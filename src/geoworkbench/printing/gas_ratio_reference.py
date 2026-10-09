from __future__ import annotations

import base64
from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QImage, QPainter, QPen

from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.printing.report_painter_fonts import point_coordinate_font
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.services.gas_curve_presentation import GasRatioScale, gas_ratio_scale
from geoworkbench.services.localization import AppLanguage

_ALIASES = {
    "WH": {"WH", "WETNESS"},
    "BH": {"BH", "BALANCE"},
    "CH": {"CH", "CHARACTER"},
    **{f"C1_C{i}": {f"C1_C{i}", f"PIXLER_C1_C{i}"} for i in range(2, 6)},
}
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


def _text(painter: QPainter, rect: QRectF, text: str, size: float | None = None) -> None:
    visual = modern_oilfield_report_profile()
    painter.setPen(QColor(visual.palette.text))
    fitted_size = visual.typography.body_pt if size is None else size
    font = point_coordinate_font(fitted_size, text=text, paint_device=painter.device())
    # Fit in virtual layout coordinates; the font adapter handles print DPI.
    for _ in range(8):
        metrics = QFontMetricsF(font, painter.device())
        factor = min(rect.width() / max(1.0, metrics.horizontalAdvance(text)), rect.height() / max(1.0, metrics.height()))
        if factor >= 1.0 or fitted_size <= 1.0:
            break
        fitted_size = max(1.0, fitted_size * factor * 0.98)
        font = point_coordinate_font(fitted_size, text=text, paint_device=painter.device())
    painter.setFont(font)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)


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
        scale = min(target.width() / 1000, target.height() / 650)
        painter.scale(scale, scale)
        visual = modern_oilfield_report_profile()
        palette, typography = visual.palette, visual.typography
        painter.fillRect(QRectF(0, 0, 1000, 650), QColor(palette.page))
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
                QRectF(plot.left(), 295, plot.width(), 22),
                "Balance (Bh)" if name == "BH" else "Character (Ch)",
            )
            _text(painter, QRectF(plot.left(), 45, plot.width(), 22), "C1 / ΣHC")
            for tick in range(6):
                _text(
                    painter,
                    QRectF(plot.left() + tick / 5 * plot.width() - 25, 283, 50, 15),
                    f"{maximum * tick / 5:.2g}",
                    typography.caption_pt,
                )
                _text(
                    painter,
                    QRectF(plot.left() - 38, plot.bottom() - tick / 5 * plot.height() - 8, 32, 16),
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
                painter.setBrush(QColor(_DEPTH_COLORS[max(0, bin_index)]))
                painter.drawEllipse(
                    QPointF(
                        plot.left() + x[row] / maximum * plot.width(),
                        plot.bottom() - y[row] * plot.height(),
                    ),
                    2,
                    2,
                )
            painter.restore()
        for index, depth_color in enumerate(_DEPTH_COLORS):
            start = low_depth + (high_depth - low_depth) * index / 6
            end = low_depth + (high_depth - low_depth) * (index + 1) / 6
            painter.setPen(QPen(QColor(depth_color), 2))
            painter.drawLine(QLineF(65 + index * 150, 327, 82 + index * 150, 327))
            _text(painter, QRectF(84 + index * 150, 317, 130, 20), f"{start:.1f}–{end:.1f} m", typography.caption_pt)
        plot = QRectF(65, 385, 610, 205)
        _axes(painter, plot)
        _text(painter, QRectF(65, 340, 610, 30), "Pixler · C1/C2 – C1/C5", typography.section_pt)
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
            for power in range(int(minimum), int(maximum) + 1):
                tick_y = plot.bottom() - (power - minimum) / (maximum - minimum) * plot.height()
                painter.setPen(QPen(QColor(palette.border), 0.7))
                painter.drawLine(QLineF(plot.left(), tick_y, plot.right(), tick_y))
                _text(painter, QRectF(12, tick_y - 8, 45, 16), f"{10.0**power:g}", typography.caption_pt)
            for profile_index, row in enumerate(selected):
                depth_bin = min(
                    5,
                    max(
                        0, int((all_depth[row] - low_depth) / max(1e-9, high_depth - low_depth) * 6)
                    ),
                )
                profile_color = QColor(_DEPTH_COLORS[depth_bin])
                painter.setPen(QPen(profile_color, 1.5))
                points = [
                    QPointF(
                        plot.left() + index / 3 * plot.width(),
                        plot.bottom()
                        - (np.log10(value) - minimum) / (maximum - minimum) * plot.height(),
                    )
                    for index, value in enumerate(matrix[row])
                ]
                for previous_point, current_point in zip(points, points[1:]):
                    painter.drawLine(QLineF(previous_point, current_point))
                _text(
                    painter,
                    QRectF(710, 390 + profile_index * 25, 260, 20),
                    f"{all_depth[row]:.2f} m",
                    typography.body_pt,
                )
                painter.setPen(QPen(profile_color, 2))
                painter.drawLine(
                    QLineF(700, 400 + profile_index * 25, 720, 400 + profile_index * 25)
                )
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
                QRectF(plot.left() + index / 3 * plot.width() - 35, 595, 70, 22),
                key.replace("_", "/"),
                typography.caption_pt,
            )
        _text(
            painter,
            QRectF(65, 625, 900, 20),
            {
                AppLanguage.RU: "Точки — парные измерения; профили — отдельные глубины. Цвет: от меньшей глубины к большей.",
                AppLanguage.KK: "Нүктелер — жұп өлшемдер; профильдер — жеке тереңдіктер. Түс: тереңдік өсуі.",
                AppLanguage.EN: "Points are paired observations; profiles are individual depths. Color: shallow to deep.",
            }[language],
            typography.footer_pt,
        )
    finally:
        painter.restore()
    return True


def ratio_reference_summary_uri(dataset: Dataset, language: AppLanguage) -> str:
    image = QImage(1600, 1040, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(modern_oilfield_report_profile().palette.page))
    painter = QPainter(image)
    try:
        if not paint_ratio_reference_summary(painter, QRectF(image.rect()), dataset, language):
            return ""
    finally:
        painter.end()
    buffer_data = QByteArray()
    buffer = QBuffer(buffer_data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):  # type: ignore[call-overload]
        raise RuntimeError("Не удалось создать диаграммы газовых отношений")
    return "data:image/png;base64," + base64.b64encode(buffer_data.data()).decode("ascii")
