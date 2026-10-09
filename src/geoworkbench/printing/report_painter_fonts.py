from __future__ import annotations

from math import isfinite

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPaintDevice, QPagedPaintDevice, QPainter

from geoworkbench.printing.unicode_support import print_font


def point_coordinate_font(
    point_size: float,
    *,
    text: str,
    paint_device: QPaintDevice | None,
    bold: bool = False,
) -> QFont:
    """Size text for a paged painter whose coordinates are physical points.

    QPdfWriter/QPrinter fonts already include device DPI. Such painters also
    scale point coordinates to device pixels; compensate that second scaling.
    Pixel-coordinate previews retain the original font contract.
    """
    if not isfinite(point_size) or point_size <= 0.0:
        raise ValueError("Font point size must be finite and positive")
    font = print_font(point_size, text=text, bold=bold)
    if isinstance(paint_device, QPagedPaintDevice):
        dpi = paint_device.logicalDpiY()
        if dpi <= 0:
            raise ValueError("Paged paint device DPI must be positive")
        font.setPointSizeF(point_size * 72.0 / dpi)
    return font


def paint_fitted_point_text(
    painter: QPainter, rect: QRectF, text: str, point_size: float, color: str,
    flags: Qt.AlignmentFlag | Qt.TextFlag, *, bold: bool = False,
) -> None:
    """Fit complete report labels in point coordinates without changing their areas."""
    font = point_coordinate_font(point_size, text=text, paint_device=painter.device(), bold=bold)
    painter.save()
    try:
        for _ in range(8):
            bounds = QFontMetricsF(font, painter.device()).boundingRect(
                QRectF(0, 0, rect.width(), 10000), int(flags), text)
            factor = min(rect.width() / max(1.0, bounds.width()),
                         rect.height() / max(1.0, bounds.height()))
            if factor >= 1.0 or point_size <= 1.0:
                break
            point_size = max(1.0, point_size * factor * 0.98)
            font = point_coordinate_font(point_size, text=text, paint_device=painter.device(), bold=bold)
        painter.setFont(font)
        painter.setPen(QColor(color))
        painter.drawText(rect, int(flags), text)
    finally:
        painter.restore()
