from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from geoworkbench.printing.image_assets import ImageAsset, SVG_MEDIA_TYPE


def draw_image_asset(painter: QPainter, rect: QRectF, asset: ImageAsset) -> bool:
    if asset.media_type == SVG_MEDIA_TYPE:
        renderer = QSvgRenderer(QByteArray(asset.payload))
        if not renderer.isValid():
            return False
        renderer.render(painter, rect)
        return True
    image = QImage.fromData(asset.payload)
    if image.isNull():
        return False
    painter.drawImage(rect, image)
    return True


def image_asset_pixmap(asset: ImageAsset, size: QSize = QSize(1200, 600)) -> QPixmap:
    if asset.media_type != SVG_MEDIA_TYPE:
        pixmap = QPixmap()
        pixmap.loadFromData(asset.payload)
        return pixmap
    renderer = QSvgRenderer(QByteArray(asset.payload))
    if not renderer.isValid():
        return QPixmap()
    viewport = renderer.defaultSize()
    if not viewport.isValid() or viewport.isEmpty():
        viewport = QSize(size)
    viewport.scale(size, Qt.AspectRatioMode.KeepAspectRatio)
    image = QImage(viewport, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return QPixmap.fromImage(image)
