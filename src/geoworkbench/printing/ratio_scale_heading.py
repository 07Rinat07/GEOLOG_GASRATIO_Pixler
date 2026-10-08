from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QPaintDevice, QPainter

from geoworkbench.printing.interpretation_track_headings import paint_track_heading
from geoworkbench.printing.report_painter_fonts import point_coordinate_font
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile


def ratio_scale_header_height(paint_device: QPaintDevice) -> float:
    """Reserve a wrapped identifier and two readable tick rows in point coordinates."""
    size = modern_oilfield_report_profile().typography.caption_pt
    metrics = QFontMetricsF(point_coordinate_font(size, text="1000", paint_device=paint_device), paint_device)
    return 4.0 * (metrics.height() + 2.0) + 4.0


def paint_ratio_scale_heading(
    painter: QPainter,
    lane: QRectF,
    mnemonic: str,
    ticks: tuple[tuple[float, str], ...],
) -> None:
    """Keep endpoint values; omit crowded interior labels rather than reducing font size."""
    if not ticks or lane.width() <= 0.0:
        return
    visual = modern_oilfield_report_profile()
    font = point_coordinate_font(visual.typography.caption_pt, text="1000", paint_device=painter.device())
    metrics = QFontMetricsF(font, painter.device())
    row_height = metrics.height() + 2.0
    height = ratio_scale_header_height(painter.device())
    paint_track_heading(
        painter, QRectF(lane.left(), lane.top() - height, lane.width(), 2.0 * row_height),
        mnemonic, visual.typography.caption_pt, point_coordinates=True,
    )
    painter.save()
    try:
        painter.setFont(font)
        painter.setPen(QColor(visual.palette.text_secondary))
        painter.setClipRect(QRectF(lane.left(), lane.top() - 2.0 * row_height - 2.0,
                                  lane.width(), 2.0 * row_height))
        rectangles: list[QRectF] = []
        selected = [ticks[0]]
        if len(ticks) > 1:
            selected.append(ticks[-1])
        if len(ticks) > 2:
            selected.append(ticks[len(ticks) // 2])
        for index, (fraction, label) in enumerate(selected):
            width = metrics.horizontalAdvance(label) + 2.0
            left = min(max(lane.left() + fraction * lane.width() - width / 2.0,
                           lane.left()), lane.right() - width)
            rectangle = QRectF(left, lane.top() - 2.0 * row_height - 2.0, width, row_height)
            if any(rectangle.adjusted(-1.0, 0.0, 1.0, 0.0).intersects(other) for other in rectangles):
                if index != 1:
                    continue
                rectangle.translate(0.0, row_height)
            painter.drawText(rectangle, Qt.AlignmentFlag.AlignCenter, label)
            rectangles.append(rectangle)
    finally:
        painter.restore()
