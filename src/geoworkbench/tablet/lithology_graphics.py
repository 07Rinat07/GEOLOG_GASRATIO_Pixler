from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QBrush, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem, QStyleOptionGraphicsItem, QWidget


class DeviceTiledRectItem(QGraphicsRectItem):
    """Rectangle whose bitmap brush is tiled in device pixels.

    A pyqtgraph ``ViewBox`` applies a strongly non-uniform transform: the X axis
    represents track percentage while Y represents depth.  A normal texture
    brush inherits that transform and stretches a 14x14 legacy lithotype into
    thick lines.  Cancelling the active world transform only for the brush keeps
    the rectangle tied to data coordinates while the supplied BMP repeats at its
    original sharp pixel size, including after zooming or panning.
    """

    def __init__(self, rect: QRectF, brush: QBrush, pen: QPen) -> None:
        super().__init__(rect)
        self.setBrush(brush)
        self.setPen(pen)
        self.setCacheMode(QGraphicsItem.CacheMode.NoCache)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        del option, widget
        painter.save()
        try:
            brush = QBrush(self.brush())
            inverse, invertible = painter.worldTransform().inverted()
            if invertible and not brush.textureImage().isNull():
                brush.setTransform(inverse)
            painter.setBrush(brush)
            painter.setPen(self.pen())
            painter.drawRect(self.rect())
        finally:
            painter.restore()
