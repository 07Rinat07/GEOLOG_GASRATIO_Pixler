from __future__ import annotations

from math import floor, isclose

import numpy as np
from PySide6.QtCore import QLineF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart as base_chart
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

    available_height = (
        canvas.content_rect.height()
        - CHART_HEADER_HEIGHT
        - CHART_TRACK_HEADER_HEIGHT
        - CHART_LEGEND_HEIGHT
        - CHART_NOTE_HEIGHT
    )
    depth_min = float(np.nanmin(depth[finite_depth]))
    depth_max = float(np.nanmax(depth[finite_depth]))
    if depth_range is not None:
        depth_min = depth_range.top_depth
        depth_max = depth_range.bottom_depth
    pages = plan_depth_pages(
        depth_min,
        depth_max,
        available_height,
    )
    ranges = base_chart._curve_ranges(panels, dataset)
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
    language: AppLanguage,
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
    candidates = tuple(report.candidates)
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
            ranges,
        )

    _draw_fluid_callouts(
        painter,
        geometry,
        page,
        candidates,
        report.depth_unit,
        language,
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
    labels = base_chart._labels(language)
    painter.fillRect(rect, QColor("#ffffff"))
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
        painter.setPen(QPen(QColor("#e0e7ee"), 0.42))
        painter.drawLine(QLineF(rect.left(), y, rect.right(), y))

    major_step = base_chart._nice_tick_step(
        page.span,
        target_ticks=_MAJOR_TARGET_TICKS,
    )
    for tick in base_chart._depth_ticks(page, major_step):
        y = base_chart._depth_y(tick, page, rect)
        painter.setPen(QPen(QColor("#aebdca"), 0.78))
        painter.drawLine(QLineF(rect.left(), y, rect.right(), y))

    for index in range(5):
        x = rect.left() + index / 4.0 * rect.width()
        painter.setPen(QPen(QColor("#d6dee7"), 0.5))
        painter.drawLine(QLineF(x, rect.top(), x, rect.bottom()))
        painter.setFont(print_font(6.2, text="100"))
        painter.setPen(QColor("#475569"))
        painter.drawText(
            QRectF(x - 14.0, rect.top() - 19.0, 28.0, 12.0),
            Qt.AlignmentFlag.AlignCenter,
            str(index * 25),
        )

    _draw_candidate_bands(painter, rect, page, candidates, language)
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
    base_chart._draw_curves(painter, rect, page, dataset, curves, ranges)
    painter.setPen(QPen(QColor("#263746"), 1.1))
    painter.drawRect(rect)



def _draw_candidate_bands(
    painter: QPainter,
    rect: QRectF,
    page: DepthPage,
    candidates: tuple[HydrocarbonCandidateInterval, ...],
    language: AppLanguage,
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
        _label, color = _fluid_callout_spec(candidate, language)
        band_color = QColor(color)
        band_color.setAlpha(34)
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
        painter.setPen(QPen(QColor(color), 0.65))
        painter.drawLine(QLineF(rect.left(), y1, rect.right(), y1))
        painter.drawLine(QLineF(rect.left(), y2, rect.right(), y2))


def _draw_fluid_callouts(
    painter: QPainter,
    geometry: ChartGeometry,
    page: DepthPage,
    candidates: tuple[HydrocarbonCandidateInterval, ...],
    depth_unit: str,
    language: AppLanguage,
) -> None:
    if not geometry.panel_rects:
        return
    visible = tuple(
        candidate
        for candidate in candidates
        if min(candidate.top_depth, candidate.bottom_depth) < page.bottom_depth
        and max(candidate.top_depth, candidate.bottom_depth) > page.top_depth
    )
    if not visible:
        return

    target = geometry.panel_rects[-1]
    box_width = min(122.0, max(82.0, target.width() * 0.52))
    box_height = 31.0
    box_left = target.right() - box_width - 4.0
    min_center = target.top() + box_height / 2.0 + 3.0
    max_center = target.bottom() - box_height / 2.0 - 3.0
    preferred = tuple(
        base_chart._depth_y(
            (max(page.top_depth, min(item.top_depth, item.bottom_depth))
             + min(page.bottom_depth, max(item.top_depth, item.bottom_depth)))
            / 2.0,
            page,
            target,
        )
        for item in visible
    )
    centers = _stagger_callout_centers(
        preferred,
        min_center=min_center,
        max_center=max_center,
        minimum_gap=box_height + 3.0,
    )

    for candidate, actual_y, center_y in zip(
        visible,
        preferred,
        centers,
        strict=True,
    ):
        label, color = _fluid_callout_spec(candidate, language)
        box = QRectF(
            box_left,
            center_y - box_height / 2.0,
            box_width,
            box_height,
        )
        marker_x = box.left() - 7.0

        painter.setPen(QPen(QColor(color), 0.9))
        painter.drawLine(QLineF(marker_x, actual_y, box.left(), center_y))
        painter.setBrush(QColor(color))
        painter.drawEllipse(QRectF(marker_x - 2.2, actual_y - 2.2, 4.4, 4.4))

        fill = QColor("#ffffff")
        fill.setAlpha(236)
        painter.fillRect(box, fill)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(color), 1.0))
        painter.drawRoundedRect(box, 3.0, 3.0)

        heading_font = print_font(6.6, text=label)
        heading_font.setBold(True)
        painter.setFont(heading_font)
        painter.setPen(QColor("#172033"))
        painter.drawText(
            box.adjusted(5.0, 2.0, -5.0, -13.0),
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
            | Qt.TextFlag.TextWordWrap,
            label,
        )

        interval_text = _fluid_callout_interval_text(
            candidate,
            depth_unit,
            language,
        )
        painter.setFont(print_font(5.5, text=interval_text))
        painter.setPen(QColor("#526579"))
        painter.drawText(
            QRectF(
                box.left() + 5.0,
                box.bottom() - 12.0,
                box.width() - 10.0,
                9.0,
            ),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            interval_text,
        )


def _fluid_callout_spec(
    candidate: HydrocarbonCandidateInterval,
    language: AppLanguage,
) -> tuple[str, str]:
    key = candidate.fluid_hypothesis.casefold()
    if key.startswith("opus_fallback__"):
        key = key[len("opus_fallback__") :]

    category = "indeterminate"
    if "gas_condensate_or_gassy_oil" in key:
        category = "gas_condensate_or_gassy_oil"
    elif "gas_condensate_or_high_api_oil" in key:
        category = "gas_condensate_or_light_oil"
    elif "water_dissolved_gas" in key:
        category = "dissolved_gas"
    elif "gas_condensate" in key or "wet_gas" in key:
        category = "gas_condensate"
    elif "gassy_oil" in key:
        category = "gassy_oil"
    elif "light_oil" in key:
        category = "light_oil"
    elif any(token in key for token in ("heavy", "residual", "oxidized", "low_gravity_oil")):
        category = "heavy_oil"
    elif "liquid_hydrocarbons" in key:
        category = "liquid_hydrocarbons"
    elif "oil" in key:
        category = "oil"
    elif (
        "gas" in key
        and not any(
            token in key
            for token in ("insufficient", "indeterminate", "no_consensus", "ambiguous")
        )
    ):
        category = "gas"

    labels = {
        AppLanguage.RU: {
            "gas": "ГАЗ",
            "gas_condensate": "ГАЗ-КОНДЕНСАТ",
            "gas_condensate_or_light_oil": "ГК / ЛЁГКАЯ НЕФТЬ",
            "gas_condensate_or_gassy_oil": "ГК / ГАЗИРОВАННАЯ НЕФТЬ",
            "dissolved_gas": "ГАЗ В ВОДЕ",
            "gassy_oil": "ГАЗИРОВАННАЯ НЕФТЬ",
            "light_oil": "ЛЁГКАЯ НЕФТЬ",
            "oil": "НЕФТЬ",
            "heavy_oil": "ТЯЖЁЛАЯ / ОСТАТОЧНАЯ НЕФТЬ",
            "liquid_hydrocarbons": "ЖИДКИЕ УВ",
            "indeterminate": "СМЕШАННЫЙ / НЕОПРЕДЕЛЁННЫЙ ТИП",
        },
        AppLanguage.KK: {
            "gas": "ГАЗ",
            "gas_condensate": "ГАЗ-КОНДЕНСАТ",
            "gas_condensate_or_light_oil": "ГК / ЖЕҢІЛ МҰНАЙ",
            "gas_condensate_or_gassy_oil": "ГК / ГАЗДАЛҒАН МҰНАЙ",
            "dissolved_gas": "СУДАҒЫ ГАЗ",
            "gassy_oil": "ГАЗДАЛҒАН МҰНАЙ",
            "light_oil": "ЖЕҢІЛ МҰНАЙ",
            "oil": "МҰНАЙ",
            "heavy_oil": "АУЫР / ҚАЛДЫҚ МҰНАЙ",
            "liquid_hydrocarbons": "СҰЙЫҚ КС",
            "indeterminate": "АРАЛАС / АНЫҚТАЛМАҒАН ТҮР",
        },
        AppLanguage.EN: {
            "gas": "GAS",
            "gas_condensate": "GAS CONDENSATE",
            "gas_condensate_or_light_oil": "GC / LIGHT OIL",
            "gas_condensate_or_gassy_oil": "GC / GASSY OIL",
            "dissolved_gas": "DISSOLVED GAS",
            "gassy_oil": "GASSY OIL",
            "light_oil": "LIGHT OIL",
            "oil": "OIL",
            "heavy_oil": "HEAVY / RESIDUAL OIL",
            "liquid_hydrocarbons": "LIQUID HC",
            "indeterminate": "MIXED / INDETERMINATE",
        },
    }
    colors = {
        "gas": "#2563eb",
        "gas_condensate": "#0f766e",
        "gas_condensate_or_light_oil": "#0f766e",
        "gas_condensate_or_gassy_oil": "#0f766e",
        "dissolved_gas": "#0891b2",
        "gassy_oil": "#b45309",
        "light_oil": "#d97706",
        "oil": "#a16207",
        "heavy_oil": "#78350f",
        "liquid_hydrocarbons": "#c47f00",
        "indeterminate": "#64748b",
    }
    return labels[language][category], colors[category]


def _fluid_callout_interval_text(
    candidate: HydrocarbonCandidateInterval,
    depth_unit: str,
    language: AppLanguage,
) -> str:
    prefix = {
        AppLanguage.RU: "предв.",
        AppLanguage.KK: "алдын ала",
        AppLanguage.EN: "prelim.",
    }[language]
    unit = f" {depth_unit}" if depth_unit else ""
    return (
        f"{prefix} · {candidate.top_depth:.1f}–"
        f"{candidate.bottom_depth:.1f}{unit}"
    )


def _stagger_callout_centers(
    preferred: tuple[float, ...],
    *,
    min_center: float,
    max_center: float,
    minimum_gap: float,
) -> tuple[float, ...]:
    if not preferred:
        return ()
    if max_center <= min_center:
        midpoint = (min_center + max_center) / 2.0
        return tuple(midpoint for _ in preferred)

    indexed = sorted(enumerate(preferred), key=lambda item: item[1])
    placed: list[tuple[int, float]] = []
    previous = min_center - minimum_gap
    for index, value in indexed:
        center = min(max(float(value), min_center), max_center)
        center = max(center, previous + minimum_gap)
        placed.append((index, center))
        previous = center

    overflow = placed[-1][1] - max_center
    if overflow > 0.0:
        placed = [(index, center - overflow) for index, center in placed]
        for position in range(len(placed) - 2, -1, -1):
            next_center = placed[position + 1][1]
            index, center = placed[position]
            placed[position] = (
                index,
                min(center, next_center - minimum_gap),
            )
        underflow = min_center - placed[0][1]
        if underflow > 0.0:
            placed = [(index, center + underflow) for index, center in placed]

    result = [0.0] * len(preferred)
    for index, center in placed:
        result[index] = min(max(center, min_center), max_center)
    return tuple(result)


__all__ = [
    "major_depth_ticks",
    "minor_depth_ticks",
    "render_chart_pages",
]
