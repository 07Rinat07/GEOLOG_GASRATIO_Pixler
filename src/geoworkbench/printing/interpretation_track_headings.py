from __future__ import annotations

from math import ceil

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPaintDevice, QPainter

from geoworkbench.printing.unicode_support import print_font
from geoworkbench.printing.report_painter_fonts import point_coordinate_font
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile


HEADING_FLAGS = (
    Qt.AlignmentFlag.AlignCenter
    | Qt.TextFlag.TextWordWrap
    | Qt.TextFlag.TextWrapAnywhere
)


def track_heading_height(
    text: str,
    width: float,
    font_size: float,
    paint_device: QPaintDevice,
    *,
    point_coordinates: bool = False,
) -> float:
    """Reserve complete wrapped headings using the destination's font metrics."""
    font = _heading_font(font_size, text, paint_device, point_coordinates)
    metrics = QFontMetricsF(font, paint_device)
    bounds = metrics.boundingRect(
        QRectF(0.0, 0.0, max(1.0, width - 4.0), 10_000.0),
        int(HEADING_FLAGS),
        text,
    )
    return float(ceil(bounds.height() + 4.0))


def paint_track_heading(
    painter: QPainter,
    rect: QRectF,
    text: str,
    font_size: float,
    *,
    point_coordinates: bool = False,
) -> None:
    painter.save()
    painter.setClipRect(rect)
    font = _heading_font(font_size, text, painter.device(), point_coordinates)
    painter.setFont(font)
    painter.setPen(QColor(modern_oilfield_report_profile().palette.text))
    painter.drawText(rect.adjusted(2.0, 0.0, -2.0, 0.0), HEADING_FLAGS, text)
    painter.restore()


def _heading_font(
    font_size: float, text: str, paint_device: QPaintDevice, point_coordinates: bool,
) -> QFont:
    if point_coordinates:
        return point_coordinate_font(font_size, text=text, paint_device=paint_device, bold=True)
    return print_font(font_size, text=text, bold=True)
