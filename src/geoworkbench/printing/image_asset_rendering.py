from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from geoworkbench.printing.image_assets import ImageAsset, SVG_MEDIA_TYPE


def draw_image_asset(
    painter: QPainter,
    rect: QRectF,
    asset: ImageAsset,
    *,
    mode: str = "stretch",
    rotation: float = 0.0,
    opacity: float = 1.0,
) -> bool:
    painter.save()
    painter.setOpacity(max(0.0, min(1.0, float(opacity))))
    painter.setClipRect(rect)
    try:
        if asset.media_type == SVG_MEDIA_TYPE:
            renderer = QSvgRenderer(QByteArray(asset.payload))
            if not renderer.isValid():
                return False
            target = _target_rect(rect, renderer.defaultSize(), mode)
            if rotation:
                painter.translate(target.center())
                painter.rotate(float(rotation))
                painter.translate(-target.center())
            renderer.render(painter, target)
            return True
        image = QImage.fromData(asset.payload)
        if image.isNull():
            return False
        target = _target_rect(rect, image.size(), mode)
        if rotation:
            painter.translate(target.center())
            painter.rotate(float(rotation))
            painter.translate(-target.center())
        painter.drawImage(target, image)
        return True
    finally:
        painter.restore()


def _target_rect(rect: QRectF, size: QSize, mode: str) -> QRectF:
    if mode == "stretch" or not size.isValid() or size.isEmpty():
        return QRectF(rect)
    source_ratio = float(size.width()) / float(size.height())
    target_ratio = rect.width() / max(rect.height(), 1e-9)
    fit = mode != "fill"
    if (source_ratio > target_ratio) == fit:
        width = rect.width()
        height = width / source_ratio
    else:
        height = rect.height()
        width = height * source_ratio
    return QRectF(
        rect.center().x() - width / 2.0,
        rect.center().y() - height / 2.0,
        width,
        height,
    )


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
