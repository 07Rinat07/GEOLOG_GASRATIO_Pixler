from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from geoworkbench.printing.tablet_print import (
    TabletPrintError,
    capture_tablet_print_snapshot,
    paint_tablet_snapshot,
)
from geoworkbench.tablet.tablet_view import TabletView


class PageRenderError(RuntimeError):
    pass


def paint_widget_page(
    widget: QWidget,
    painter: QPainter,
    content_rect: QRectF,
    *,
    fit_form_columns: bool = True,
    high_quality: bool = True,
) -> None:
    """Render a chart/tablet into a paper content rectangle.

    This is the single renderer used by physical printing, PDF, print preview,
    SVG and page-sized raster exports.  Keeping one implementation prevents
    preview/output differences.
    """

    width = widget.width()
    height = widget.height()
    if width <= 0 or height <= 0:
        raise PageRenderError("Визуализация не имеет допустимого размера")
    if content_rect.width() <= 0 or content_rect.height() <= 0:
        raise PageRenderError("Устройство печати не предоставило допустимую область страницы")

    painter.save()
    try:
        painter.fillRect(content_rect, Qt.GlobalColor.white)
        if isinstance(widget, TabletView) and widget.printable_tracks():
            requested_scale = content_rect.height() / max(1, height)
            raster_scale = min(4.0, max(1.0, requested_scale)) if high_quality else 1.0
            try:
                snapshot = capture_tablet_print_snapshot(
                    widget,
                    page_aspect_ratio=content_rect.width() / content_rect.height(),
                    fit_columns=fit_form_columns,
                    raster_scale=raster_scale,
                )
                paint_tablet_snapshot(painter, content_rect, snapshot)
            except TabletPrintError as exc:
                raise PageRenderError(str(exc)) from exc
            return

        scale = min(content_rect.width() / width, content_rect.height() / height)
        painter.translate(
            content_rect.left() + (content_rect.width() - width * scale) / 2.0,
            content_rect.top() + (content_rect.height() - height * scale) / 2.0,
        )
        painter.scale(scale, scale)
        widget.render(painter, QPoint())
    except Exception as exc:
        if isinstance(exc, PageRenderError):
            raise
        raise PageRenderError("Не удалось отрисовать визуализацию") from exc
    finally:
        painter.restore()
