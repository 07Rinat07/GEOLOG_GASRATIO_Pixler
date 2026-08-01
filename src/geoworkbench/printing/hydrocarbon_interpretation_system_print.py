from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

import fitz
from PySide6.QtCore import QMarginsF, QRectF
from PySide6.QtGui import QImage, QPageLayout, QPageSize, QPainter
from PySide6.QtPrintSupport import QAbstractPrintDialog, QPrinter


CancelCheck = Callable[[], bool]
ProgressCallback = Callable[[int, int, int], None]


def configure_interpretation_printer(
    printer: QPrinter,
    orientation: QPageLayout.Orientation,
) -> None:
    """Apply the controlled A4 layout after the native driver dialog."""

    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageOrientation(orientation)
    printer.setPageMargins(
        QMarginsF(14.0, 14.0, 14.0, 14.0),
        QPageLayout.Unit.Millimeter,
    )
    printer.setFullPage(False)


def selected_report_pages(
    total_pages: int,
    print_range: QAbstractPrintDialog.PrintRange,
    from_page: int,
    to_page: int,
    *,
    reverse: bool = False,
) -> tuple[int, ...]:
    """Return one-based pages that the application must actually send."""

    if total_pages < 1:
        return ()
    if print_range is QAbstractPrintDialog.PrintRange.PageRange:
        start = max(1, min(total_pages, int(from_page or 1)))
        end = max(1, min(total_pages, int(to_page or total_pages)))
        if start > end:
            start, end = end, start
    else:
        start, end = 1, total_pages
    pages = tuple(range(start, end + 1))
    return tuple(reversed(pages)) if reverse else pages


def print_pdf_page_selection(
    pdf_path: str | Path,
    printer: QPrinter,
    page_numbers: Iterable[int],
    *,
    cancel_requested: CancelCheck | None = None,
    progress: ProgressCallback | None = None,
) -> bool:
    """Print only the requested PDF pages and stop before spooling the rest."""

    pages = tuple(int(page) for page in page_numbers)
    if not pages:
        return False

    with fitz.open(Path(pdf_path)) as document:
        if any(page < 1 or page > document.page_count for page in pages):
            raise ValueError("Диапазон печати выходит за пределы отчёта")

        painter = QPainter(printer)
        if not painter.isActive():
            raise RuntimeError("Не удалось запустить системную печать")
        try:
            total = len(pages)
            for output_index, page_number in enumerate(pages, start=1):
                if cancel_requested is not None and cancel_requested():
                    printer.abort()
                    return False
                if output_index > 1 and not printer.newPage():
                    raise RuntimeError("Не удалось создать следующую печатную страницу")

                page = document[page_number - 1]
                render_dpi = max(144, min(300, int(printer.resolution() or 300)))
                scale = render_dpi / 72.0
                pixmap = page.get_pixmap(
                    matrix=fitz.Matrix(scale, scale),
                    alpha=False,
                )
                image = QImage(
                    pixmap.samples,
                    pixmap.width,
                    pixmap.height,
                    pixmap.stride,
                    QImage.Format.Format_RGB888,
                ).copy()
                if image.isNull():
                    raise RuntimeError(
                        f"Не удалось подготовить страницу {page_number} для печати"
                    )

                paint_rect = printer.pageLayout().paintRectPixels(printer.resolution())
                target = _fit_rect(
                    float(paint_rect.width()),
                    float(paint_rect.height()),
                    float(image.width()),
                    float(image.height()),
                )
                painter.fillRect(
                    QRectF(0.0, 0.0, float(paint_rect.width()), float(paint_rect.height())),
                    0xFFFFFFFF,
                )
                painter.drawImage(target, image)
                if progress is not None:
                    progress(output_index, total, page_number)
        finally:
            painter.end()
    return True


def _fit_rect(
    target_width: float,
    target_height: float,
    source_width: float,
    source_height: float,
) -> QRectF:
    if min(target_width, target_height, source_width, source_height) <= 0.0:
        return QRectF()
    scale = min(target_width / source_width, target_height / source_height)
    width = source_width * scale
    height = source_height * scale
    return QRectF(
        (target_width - width) / 2.0,
        (target_height - height) / 2.0,
        width,
        height,
    )


__all__ = [
    "configure_interpretation_printer",
    "print_pdf_page_selection",
    "selected_report_pages",
]
