"""Shared monochrome-readable line styles for interpretation report curves."""

from __future__ import annotations

from PySide6.QtCore import Qt


_CURVE_STROKES = (
    Qt.PenStyle.SolidLine,
    Qt.PenStyle.DashLine,
    Qt.PenStyle.DotLine,
    Qt.PenStyle.DashDotLine,
    Qt.PenStyle.DashDotDotLine,
)


def curve_line_pen_style(curve_index: int) -> Qt.PenStyle:
    """Use the same panel-local stroke for the curve and its legend in every renderer."""
    if isinstance(curve_index, bool) or not isinstance(curve_index, int) or curve_index < 0:
        raise ValueError("curve_index must be a non-negative integer")
    return _CURVE_STROKES[curve_index % len(_CURVE_STROKES)]


__all__ = ["curve_line_pen_style"]
