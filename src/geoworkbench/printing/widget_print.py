from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QWidget

from geoworkbench.printing.page_renderer import PageRenderError, paint_widget_page


class WidgetPrintError(RuntimeError):
    pass


def render_widget_to_printer(
    widget: QWidget,
    printer: QPrinter,
    *,
    fit_form_columns: bool = True,
) -> None:
    if widget.width() <= 0 or widget.height() <= 0:
        raise WidgetPrintError("Визуализация не имеет допустимого размера")
    page = printer.pageRect(QPrinter.Unit.DevicePixel)
    if page.width() <= 0 or page.height() <= 0:
        raise WidgetPrintError("Принтер не предоставил допустимую область страницы")

    painter = QPainter()
    try:
        if not painter.begin(printer):
            raise WidgetPrintError("Не удалось запустить печатный renderer")
        try:
            paint_widget_page(
                widget,
                painter,
                QRectF(page),
                fit_form_columns=fit_form_columns,
                high_quality=True,
            )
        except PageRenderError as exc:
            raise WidgetPrintError(str(exc)) from exc
        if not painter.end():
            raise WidgetPrintError("Не удалось завершить печатный renderer")
    except Exception as exc:
        if isinstance(exc, WidgetPrintError):
            raise
        raise WidgetPrintError("Не удалось отрисовать визуализацию для печати") from exc
    finally:
        if painter.isActive():
            painter.end()
