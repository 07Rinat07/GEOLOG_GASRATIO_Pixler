from __future__ import annotations

from math import ceil

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QPaintDevice, QPainter

from geoworkbench.printing.unicode_support import print_font


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
) -> float:
    """Reserve complete wrapped headings using the destination's font metrics."""
    font = print_font(font_size, text=text)
    font.setBold(True)
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
) -> None:
    painter.save()
    painter.setClipRect(rect)
    font = print_font(font_size, text=text)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor("#172033"))
    painter.drawText(rect.adjusted(2.0, 0.0, -2.0, 0.0), HEADING_FLAGS, text)
    painter.restore()
