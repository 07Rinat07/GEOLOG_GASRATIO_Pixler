from __future__ import annotations

from math import ceil
import re

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPaintDevice, QPainter

from geoworkbench.printing.unicode_support import print_font
from geoworkbench.printing.report_painter_fonts import point_coordinate_font
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile


HEADING_FLAGS = (
    Qt.AlignmentFlag.AlignCenter
    | Qt.TextFlag.TextWordWrap
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
    font = _heading_font(font_size, text, paint_device, point_coordinates, width)
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
    font = _heading_font(font_size, text, painter.device(), point_coordinates, rect.width())
    painter.setFont(font)
    painter.setPen(QColor(modern_oilfield_report_profile().palette.text))
    painter.drawText(rect.adjusted(2.0, 0.0, -2.0, 0.0), HEADING_FLAGS, text)
    painter.restore()


def _heading_font(
    font_size: float, text: str, paint_device: QPaintDevice, point_coordinates: bool,
    width: float,
) -> QFont:
    """Keep each word intact, fitting the longest token before word wrapping."""
    available_width = max(1.0, width - 4.0)
    # Non-breaking spaces remain within a token, matching Qt's wrapping rules.
    tokens = re.split(r"[ \t\r\n]+", text)
    for _ in range(8):
        font = (
            point_coordinate_font(font_size, text=text, paint_device=paint_device, bold=True)
            if point_coordinates else print_font(font_size, text=text, bold=True)
        )
        metrics = QFontMetricsF(font, paint_device)
        longest = max((metrics.horizontalAdvance(token) for token in tokens), default=0.0)
        if longest <= available_width:
            return font
        font_size *= available_width / longest * 0.98
    return font
