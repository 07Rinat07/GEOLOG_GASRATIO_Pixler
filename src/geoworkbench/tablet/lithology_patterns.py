from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPixmap

from geoworkbench.tablet.lithology_pattern_catalog import (
    resolve_lithology_pattern,
    supported_pattern_keys,
)


_PATTERN_STYLES = {
    "solid": Qt.BrushStyle.SolidPattern,
    "dots": Qt.BrushStyle.Dense6Pattern,
    "dense_dots": Qt.BrushStyle.Dense4Pattern,
    "sand_dots": Qt.BrushStyle.Dense6Pattern,
    "sandstone_bricks": Qt.BrushStyle.BDiagPattern,
    "clay_dash": Qt.BrushStyle.HorPattern,
    "silt_dash": Qt.BrushStyle.Dense5Pattern,
    "gravel_circles": Qt.BrushStyle.Dense7Pattern,
    "conglomerate": Qt.BrushStyle.DiagCrossPattern,
    "carbonate": Qt.BrushStyle.CrossPattern,
    "evaporite": Qt.BrushStyle.FDiagPattern,
    "coal": Qt.BrushStyle.Dense1Pattern,
    "metamorphic": Qt.BrushStyle.DiagCrossPattern,
    "volcanic": Qt.BrushStyle.Dense3Pattern,
}


@lru_cache(maxsize=256)
def _constructor_pattern_pixmap(pattern_key: str) -> QPixmap:
    descriptor = resolve_lithology_pattern(pattern_key)
    if descriptor.kind != "bitmap" or descriptor.asset_path is None:
        return QPixmap()
    return QPixmap(str(descriptor.asset_path))


def lithology_brush(color: str, pattern_key: str) -> QBrush:
    descriptor = resolve_lithology_pattern(pattern_key)
    pattern_key = descriptor.resolved_key
    parsed_color = QColor(color)
    if not parsed_color.isValid():
        parsed_color = QColor("#b0b0b0")
    if pattern_key.startswith("constructor:"):
        pixmap = _constructor_pattern_pixmap(pattern_key)
        if not pixmap.isNull():
            # QBrush repeats the source bitmap. Smooth scaling is deliberately not
            # applied because geological legacy lithotypes are pixel patterns.
            return QBrush(pixmap)
    style = _PATTERN_STYLES.get(pattern_key, Qt.BrushStyle.SolidPattern)
    return QBrush(parsed_color, style)


def masterlog_lithology_brush(
    painter: QPainter,
    color: str,
    pattern_key: str,
    *,
    reference_dpi: float = 96.0,
) -> QBrush:
    """Return a print/preview brush with a stable physical bitmap tile size.

    Masterlog is painted in millimetres and then scaled to the output device.
    A normal bitmap brush inherits that scale, so a 14x14 legacy BMP would become
    a 14x14 *millimetre* block.  Cancel the active world transform for texture
    coordinates and then reapply a 96-DPI reference scale.  One source pixel is
    therefore always 1/96 inch on screen, image preview, PDF, and printer output,
    while interval geometry remains in millimetres.
    """

    brush = lithology_brush(color, pattern_key)
    if brush.textureImage().isNull():
        return brush

    inverse, invertible = painter.worldTransform().inverted()
    if not invertible:
        return brush

    device = painter.device()
    dpi_x = float(device.logicalDpiX()) if device is not None else reference_dpi
    dpi_y = float(device.logicalDpiY()) if device is not None else reference_dpi
    safe_reference = max(1.0, float(reference_dpi))
    if not (dpi_x > 0.0):
        dpi_x = safe_reference
    if not (dpi_y > 0.0):
        dpi_y = safe_reference

    inverse.scale(dpi_x / safe_reference, dpi_y / safe_reference)
    brush.setTransform(inverse)
    return brush
