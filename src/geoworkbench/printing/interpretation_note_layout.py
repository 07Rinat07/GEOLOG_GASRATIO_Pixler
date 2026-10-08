from __future__ import annotations

from math import ceil

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFontMetricsF, QPaintDevice

from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import CHART_NOTE_HEIGHT
from geoworkbench.printing.report_painter_fonts import point_coordinate_font
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile


def interpretation_note_height(text: str, width: float, paint_device: QPaintDevice) -> float:
    """Reserve complete wrapped caption text using the destination's point metrics."""
    size = modern_oilfield_report_profile().typography.caption_pt
    font = point_coordinate_font(size, text=text, paint_device=paint_device)
    metrics = QFontMetricsF(font, paint_device)
    bounds = metrics.boundingRect(QRectF(0, 0, max(1.0, width), 10000.0),
                                  int(Qt.TextFlag.TextWordWrap), text)
    return max(CHART_NOTE_HEIGHT, float(ceil(bounds.height() + 4.0)))
