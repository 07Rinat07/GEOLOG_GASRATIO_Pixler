from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import ceil, isfinite

from PySide6.QtGui import QFontMetricsF, QPaintDevice, QTextLayout, QTextOption

from geoworkbench.domain.models import CurveData
from geoworkbench.printing.hydrocarbon_interpretation_curve_labels import curve_legend_text
from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import (
    CHART_LEGEND_HEIGHT, MAX_AUTOMATIC_CHART_PAGES, DepthPage,
)
from geoworkbench.printing.report_painter_fonts import point_coordinate_font
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.services.localization import AppLanguage


@dataclass(frozen=True, slots=True)
class CurveLegendRow:
    curve_index: int
    text: str
    lines: tuple[str, ...]
    top: float
    line_height: float


@dataclass(frozen=True, slots=True)
class CurveLegendLayout:
    rows: tuple[CurveLegendRow, ...]
    line_height: float
    height: float


def curve_legend_layout(
    width: float, curves: tuple[CurveData, ...], ranges: dict[str, tuple[float, float]],
    language: AppLanguage, paint_device: QPaintDevice,
    display_hints: dict[str, str] | None = None,
) -> CurveLegendLayout:
    """Measure full labels, units and page-local ranges without shrinking captions."""
    if not isfinite(width) or width <= 21.0:
        raise ValueError('Curve legend width must be finite and greater than 21 points')
    hints = display_hints or {}
    rows: list[CurveLegendRow] = []
    top = 0.0
    line_height = 0.0
    for index, curve in enumerate(curves[:5]):
        value_range = ranges.get(curve.metadata.curve_id)
        if value_range is None:
            continue
        text = curve_legend_text(curve, *value_range, language,
                                 canonical_hint=hints.get(curve.metadata.original_mnemonic.strip().upper()))
        font = point_coordinate_font(modern_oilfield_report_profile().typography.caption_pt,
                                     text=text, paint_device=paint_device)
        metrics = QFontMetricsF(font, paint_device)
        pitch = float(ceil(max(metrics.height(), metrics.lineSpacing()) + 2.0))
        line_height = max(line_height, pitch)
        layout = QTextLayout(text, font, paint_device)
        option = QTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        layout.setTextOption(option)
        # Qt offsets are UTF-16 code units, including supplementary characters.
        encoded = text.encode('utf-16-le')
        lines: list[str] = []
        layout.beginLayout()
        try:
            while True:
                line = layout.createLine()
                if not line.isValid():
                    break
                line.setLineWidth(width - 21.0)
                start, end = line.textStart(), line.textStart() + line.textLength()
                lines.append(encoded[start * 2:end * 2].decode('utf-16-le').strip())
        finally:
            layout.endLayout()
        rows.append(CurveLegendRow(index, text, tuple(lines), top, pitch))
        top += len(lines) * pitch + 4.0
    return CurveLegendLayout(tuple(rows), line_height, top)


def fit_curve_legend_pages(
    depth_min: float, depth_max: float, height_budget: float,
    widths: tuple[float, ...], panels: tuple[tuple[str, tuple[CurveData, ...]], ...],
    language: AppLanguage, paint_device: QPaintDevice,
    display_hints: dict[str, str],
    planner: Callable[[float, float, float], tuple[DepthPage, ...]],
    page_ranges: Callable[[DepthPage], dict[str, tuple[float, float]]],
    *, minimum_height: float = CHART_LEGEND_HEIGHT,
) -> tuple[tuple[DepthPage, ...], float]:
    """Reserve the largest exact page-local legend, then replan until all fit.

    Height only grows. At most the planner's finite set of page counts can
    change the percentile text; once the count repeats, the layout is stable.
    """
    height = max(CHART_LEGEND_HEIGHT, minimum_height)
    for _ in range(MAX_AUTOMATIC_CHART_PAGES + 1):
        pages = planner(depth_min, depth_max, height_budget - height)
        measured = height
        for page in pages:
            ranges = page_ranges(page)
            for width, (_name, curves) in zip(widths, panels, strict=True):
                measured = max(measured, 7.0 + curve_legend_layout(
                    width, curves, ranges, language, paint_device, display_hints,
                ).height)
        if measured <= height:
            return pages, height
        height = measured
    raise ValueError('Curve legend pagination did not converge')
