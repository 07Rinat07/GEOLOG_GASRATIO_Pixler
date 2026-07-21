from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPixmap


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


def supported_pattern_keys() -> tuple[str, ...]:
    return tuple(_PATTERN_STYLES)


@lru_cache(maxsize=256)
def _constructor_pattern_pixmap(pattern_key: str) -> QPixmap:
    from geoworkbench.form_constructor.asset_install import resolve_constructor_pattern_asset

    asset = resolve_constructor_pattern_asset(pattern_key)
    if asset is None:
        return QPixmap()
    return QPixmap(str(asset.asset_path))


def lithology_brush(color: str, pattern_key: str) -> QBrush:
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
