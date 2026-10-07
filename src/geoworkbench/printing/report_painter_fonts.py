from __future__ import annotations

from math import isfinite

from PySide6.QtGui import QFont, QPaintDevice, QPagedPaintDevice

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
