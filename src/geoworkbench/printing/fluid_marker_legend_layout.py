from __future__ import annotations

from dataclasses import dataclass
from math import ceil, isfinite

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFontMetricsF, QPaintDevice

from geoworkbench.printing.hydrocarbon_fluid_markers import FluidMarkerSpec
from geoworkbench.printing.interpretation_note_layout import interpretation_note_height
from geoworkbench.printing.report_painter_fonts import point_coordinate_font
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.services.localization import AppLanguage


MARKER_LEGEND_TEXT_FLAGS = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap


@dataclass(frozen=True, slots=True)
class FluidMarkerLegendCell:
    spec: FluidMarkerSpec
    text: str
    left: float
    top: float
    width: float
    height: float


@dataclass(frozen=True, slots=True)
class FluidMarkerLegendLayout:
    cells: tuple[FluidMarkerLegendCell, ...]
    note: str
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
    row_height = max((float(ceil(metrics.boundingRect(
        QRectF(0, 0, cell_width - 12.0, 10000.0), int(MARKER_LEGEND_TEXT_FLAGS), text,
    ).height() + 4.0)) for text in texts), default=0.0)
    cells = tuple(FluidMarkerLegendCell(spec, text, index % columns * cell_width,
                                       index // columns * row_height, cell_width, row_height)
                  for index, (spec, text) in enumerate(zip(specs, texts, strict=True)))
    rows = (len(specs) + columns - 1) // columns
    note_top = rows * row_height + (4.0 if specs else 0.0)
    note = fluid_marker_note(language)
    return FluidMarkerLegendLayout(cells, note, note_top,
                                   note_top + interpretation_note_height(note, width, paint_device))
