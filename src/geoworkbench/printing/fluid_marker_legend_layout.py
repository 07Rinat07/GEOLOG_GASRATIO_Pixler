from __future__ import annotations

from dataclasses import dataclass
from math import ceil, isfinite

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontMetricsF, QPaintDevice, QTextLayout, QTextOption

from geoworkbench.printing.hydrocarbon_fluid_markers import FluidMarkerSpec
from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import CHART_NOTE_HEIGHT
from geoworkbench.printing.report_painter_fonts import point_coordinate_font
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.services.localization import AppLanguage


MARKER_LEGEND_TEXT_FLAGS = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop


@dataclass(frozen=True, slots=True)
class FluidMarkerLegendCell:
    spec: FluidMarkerSpec
    text: str
    lines: tuple[str, ...]
    left: float
    top: float
    width: float
    height: float


@dataclass(frozen=True, slots=True)
class FluidMarkerLegendLayout:
    cells: tuple[FluidMarkerLegendCell, ...]
    note: str
    note_lines: tuple[str, ...]
    line_height: float
    note_top: float
    height: float


def fluid_marker_note(language: AppLanguage) -> str:
    return {
        AppLanguage.RU: 'Маркеры показывают предварительный тип; полные глубины и формулировки — в таблице. Обычные дорожки — p5–p95; газовые отношения — фиксированные шкалы.',
        AppLanguage.KK: 'Маркерлер алдын ала түрді көрсетеді; толық тереңдік пен мәтін кестеде. Кәдімгі жолақтар — p5–p95; газ қатынастары — тұрақты шкалалар.',
        AppLanguage.EN: 'Markers show preliminary type; full depths and wording are in the table. Ordinary tracks use p5–p95; gas ratios use fixed scales.',
    }[language]


def fluid_marker_legend_layout(
    width: float,
    specs: tuple[FluidMarkerSpec, ...],
    language: AppLanguage,
    paint_device: QPaintDevice,
) -> FluidMarkerLegendLayout:
    """Measure complete caption cells and note before depth-page pagination."""
    if not isfinite(width) or width <= 14.0:
        raise ValueError('Fluid marker legend width must be finite and greater than 14 points')
    typography = modern_oilfield_report_profile().typography
    texts = tuple(f'{spec.code} {spec.label(language)}' for spec in specs)
    font = point_coordinate_font(typography.caption_pt, text=' '.join(texts), paint_device=paint_device)
    metrics = QFontMetricsF(font, paint_device)
    columns = min(3, max(1, len(specs)), max(1, int(width / 160.0)))
    cell_width = width / columns
    line_height = float(ceil(max(metrics.height(), metrics.lineSpacing()) + 2.0))
    wrapped = tuple(_wrapped_lines(text, cell_width - 12.0, font, paint_device) for text in texts)
    row_height = max((len(lines) * line_height + 4.0 for lines in wrapped), default=0.0)
    cells = tuple(FluidMarkerLegendCell(spec, text, lines, index % columns * cell_width,
                                       index // columns * row_height, cell_width, row_height)
                  for index, (spec, text, lines) in enumerate(zip(specs, texts, wrapped, strict=True)))
    rows = (len(specs) + columns - 1) // columns
    note_top = rows * row_height + (4.0 if specs else 0.0)
    note = fluid_marker_note(language)
    note_lines = _wrapped_lines(note, width, font, paint_device)
    note_height = max(CHART_NOTE_HEIGHT, len(note_lines) * line_height + 4.0)
    return FluidMarkerLegendLayout(cells, note, note_lines, line_height, note_top, note_top + note_height)


def _wrapped_lines(text: str, width: float, font: QFont, paint_device: QPaintDevice) -> tuple[str, ...]:
    layout = QTextLayout(text, font, paint_device)
    option = QTextOption()
    option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    layout.setTextOption(option)
    lines: list[str] = []
    layout.beginLayout()
    try:
        while True:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(width)
            lines.append(text[line.textStart():line.textStart() + line.textLength()].strip())
    finally:
        layout.endLayout()
    return tuple(lines)
