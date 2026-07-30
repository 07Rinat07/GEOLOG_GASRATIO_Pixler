from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QPointF


def eraser_stroke_rectangles(
    points: Iterable[QPointF],
    brush_size_px: int,
    render_scale: float,
) -> list[tuple[float, float, float, float]]:
    """Convert canvas-local square-brush points to PDF page coordinates."""
    scale = max(float(render_scale), 0.1)
    brush = max(8, min(180, int(brush_size_px)))
    half = brush / (2.0 * scale)
    rectangles: list[tuple[float, float, float, float]] = []
    for point in points:
        x = point.x() / scale
        y = point.y() / scale
        rectangles.append((x - half, y - half, x + half, y + half))
    return rectangles
