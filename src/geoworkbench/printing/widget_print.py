from __future__ import annotations

from PySide6.QtCore import QPoint
from PySide6.QtGui import QPainter
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QWidget


class WidgetPrintError(RuntimeError):
    pass


def render_widget_to_printer(widget: QWidget, printer: QPrinter) -> None:
    width = widget.width()
    height = widget.height()
    if width <= 0 or height <= 0:
        raise WidgetPrintError("Визуализация не имеет допустимого размера")
    page = printer.pageRect(QPrinter.Unit.DevicePixel)
    if page.width() <= 0 or page.height() <= 0:
        raise WidgetPrintError("Принтер не предоставил допустимую область страницы")
    painter = QPainter()
    try:
        if not painter.begin(printer):
            raise WidgetPrintError("Не удалось запустить печатный renderer")
        scale = min(page.width() / width, page.height() / height)
        painter.translate(
            page.left() + (page.width() - width * scale) / 2.0,
            page.top() + (page.height() - height * scale) / 2.0,
        )
        painter.scale(scale, scale)
        widget.render(painter, QPoint())
        if not painter.end():
            raise WidgetPrintError("Не удалось завершить печатный renderer")
    except Exception as exc:
        if isinstance(exc, WidgetPrintError):
            raise
        raise WidgetPrintError("Не удалось отрисовать визуализацию для печати") from exc
    finally:
        if painter.isActive():
            painter.end()
