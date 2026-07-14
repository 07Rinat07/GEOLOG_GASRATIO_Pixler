from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor


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


def lithology_brush(color: str, pattern_key: str) -> QBrush:
    parsed_color = QColor(color)
    if not parsed_color.isValid():
        parsed_color = QColor("#b0b0b0")
    style = _PATTERN_STYLES.get(pattern_key, Qt.BrushStyle.SolidPattern)
    return QBrush(parsed_color, style)
