from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from PySide6.QtCore import QPoint, QRectF, QSize, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from geoworkbench.printing.form_column_layout import (
    AdaptiveColumnLayout,
    adaptive_column_layout,
    original_column_layout,
)
from geoworkbench.tablet.tablet_view import TabletView


class TabletPrintError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TabletPrintSnapshot:
    pixmaps: tuple[QPixmap, ...]
    layout: AdaptiveColumnLayout
    content_height: int
    raster_scale: float = 1.0

    def __post_init__(self) -> None:
        if not self.pixmaps or len(self.pixmaps) != len(self.layout.widths):
            raise ValueError("Некорректный снимок печатной формы")
        if self.content_height <= 0:
            raise ValueError("Высота печатной формы должна быть положительной")
        if not 1.0 <= self.raster_scale <= 8.0:
            raise ValueError("Некорректный масштаб печатного снимка")


def capture_tablet_print_snapshot(
    tablet: TabletView,
    *,
    page_aspect_ratio: float,
    fit_columns: bool = True,
    raster_scale: float = 1.0,
) -> TabletPrintSnapshot:
    """Capture every visible form column, including off-screen columns.

    ``raster_scale`` lets PDF and image exports render the Qt widgets into a
    larger intermediate surface.  This avoids enlarging a low-resolution screen
    screenshot when the destination is an A4 page at 300 or 600 DPI.
    """

    if (
        isinstance(raster_scale, bool)
        or not isinstance(raster_scale, (int, float))
        or not isfinite(raster_scale)
        or not 1.0 <= raster_scale <= 8.0
    ):
        raise TabletPrintError("Масштаб печатного renderer должен быть от 1 до 8")

    rendered = tablet.printable_tracks()
    if not rendered:
        raise TabletPrintError("На планшете нет видимых колонок для печати")
    content_height = max(item.widget.height() for item in rendered)
    if content_height <= 0:
        raise TabletPrintError("Печатная форма не имеет допустимой высоты")

    definitions = [item.definition for item in rendered]
    layout = (
        adaptive_column_layout(
            definitions,
            page_aspect_ratio=page_aspect_ratio,
            content_height=content_height,
        )
        if fit_columns
        else original_column_layout(definitions)
    )
    original_widths = [item.widget.width() for item in rendered]
    pixmaps: list[QPixmap] = []
    tablet.set_annotation_print_mode(True)
    try:
        for item, width in zip(rendered, layout.widths, strict=True):
            item.widget.set_track_width(width)
        QApplication.processEvents()
        for item, logical_width in zip(rendered, layout.widths, strict=True):
            logical_height = max(1, item.widget.height())
            pixel_size = QSize(
                max(1, round(logical_width * raster_scale)),
                max(1, round(logical_height * raster_scale)),
            )
            pixmap = QPixmap(pixel_size)
            pixmap.fill(Qt.GlobalColor.white)
            painter = QPainter(pixmap)
            try:
                painter.scale(raster_scale, raster_scale)
                item.widget.render(painter, QPoint())
                # The professional annotation layer is a tablet-wide overlay,
                # not a child of an individual PyQtGraph column. Paint the
                # corresponding clipped portion into every column snapshot so
                # screen, PDF and physical print keep the same geometry.
                tablet.paint_annotations_for_track(item.definition.track_id, painter)
            finally:
                painter.end()
            if pixmap.isNull():
                raise TabletPrintError(
                    f"Не удалось подготовить колонку к печати: {item.definition.title}"
                )
            pixmaps.append(pixmap)
    finally:
        tablet.set_annotation_print_mode(False)
        for item, width in zip(rendered, original_widths, strict=True):
            item.widget.set_track_width(width)
        QApplication.processEvents()

    return TabletPrintSnapshot(tuple(pixmaps), layout, content_height, float(raster_scale))


def paint_tablet_snapshot(
    painter: QPainter,
    page: QRectF,
    snapshot: TabletPrintSnapshot,
) -> None:
    if page.width() <= 0 or page.height() <= 0:
        raise TabletPrintError("Устройство печати не предоставило допустимую область страницы")

    scale = min(
        page.width() / snapshot.layout.total_width,
        page.height() / snapshot.content_height,
    )
    rendered_width = snapshot.layout.total_width * scale
    rendered_height = snapshot.content_height * scale
    x = page.left() + (page.width() - rendered_width) / 2.0
    y = page.top() + (page.height() - rendered_height) / 2.0

    painter.save()
    try:
        painter.fillRect(page, Qt.GlobalColor.white)
        for pixmap, logical_width in zip(snapshot.pixmaps, snapshot.layout.widths, strict=True):
            target = QRectF(
                x,
                y,
                logical_width * scale,
                (pixmap.height() / snapshot.raster_scale) * scale,
            )
            painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))
            x += (logical_width + snapshot.layout.spacing) * scale
    finally:
        painter.restore()
