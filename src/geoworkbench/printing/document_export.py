from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tempfile

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRect, QRectF, Qt
from PySide6.QtGui import QImage, QImageWriter, QPageLayout, QPainter, QPdfWriter
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtWidgets import QWidget

from geoworkbench.printing.document_renderer import (
    PrintDocumentContext,
    build_document_plan,
    paint_document_page,
    paint_document_pages,
)
from geoworkbench.printing.print_job import PrintJobSettings, PrintOutputFormat
from geoworkbench.printing.unicode_support import (
    UnicodePrintError,
    ensure_widget_printable_unicode,
    preflight_texts,
)


class DocumentExportError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PrintDocumentResult:
    paths: tuple[Path, ...]
    page_count: int

    @property
    def primary_path(self) -> Path | None:
        return self.paths[0] if self.paths else None


_MAX_RASTER_PAGE_PIXELS = 80_000_000


def render_document_to_printer(
    widget: QWidget,
    printer: QPrinter,
    job: PrintJobSettings,
    *,
    context: PrintDocumentContext,
) -> int:
    _unicode_preflight(widget, context, job)
    # Qt exposes font embedding on QPrinter. Enabling it before QPainter starts
    # prevents the spool/PDF backend from substituting Kazakh Cyrillic or
    # engineering glyphs on another computer.
    try:
        printer.setFontEmbeddingEnabled(True)
    except (AttributeError, RuntimeError):
        pass
    page = printer.pageRect(QPrinter.Unit.DevicePixel)
    if page.width() <= 0 or page.height() <= 0:
        raise DocumentExportError("Принтер не предоставил допустимую область страницы")
    painter = QPainter()
    try:
        if not painter.begin(printer):
            raise DocumentExportError("Не удалось запустить печатный renderer")
        first = printer.fromPage() if printer.fromPage() > 0 else None
        last = printer.toPage() if printer.toPage() > 0 else None
        plan = paint_document_pages(
            widget,
            painter,
            printer,
            QRectF(page),
            pagination=job.pagination,
            context=context,
            fit_form_columns=job.page.fit_form_columns,
            high_quality=True,
            first_page=first,
            last_page=last,
        )
        if not painter.end():
            raise DocumentExportError("Не удалось завершить печатный renderer")
        return plan.page_count
    except Exception as exc:
        if isinstance(exc, (DocumentExportError, UnicodePrintError, ValueError)):
            raise
        raise DocumentExportError("Не удалось отрисовать многостраничный документ") from exc
    finally:
        if painter.isActive():
            painter.end()


def export_document_pdf(
    widget: QWidget,
    target: str | Path,
    job: PrintJobSettings,
    *,
    context: PrintDocumentContext,
    overwrite: bool = False,
) -> PrintDocumentResult:
    destination = Path(target)
    _validate_destination(destination, (".pdf",), overwrite)
    _unicode_preflight(widget, context, job)
    temporary = _temporary_path(destination)
    painter = QPainter()
    try:
        writer = QPdfWriter(str(temporary))
        writer.setPageSize(job.page.page_size_for_content(widget.width(), widget.height()))
        writer.setPageOrientation(job.page.qt_orientation)
        writer.setPageMargins(job.page.qt_margins, QPageLayout.Unit.Millimeter)
        writer.setResolution(job.dpi)
        writer.setTitle(context.title)
        writer.setCreator("GEOLOG GASRATIO@Pixler")
        if not painter.begin(writer):
            raise DocumentExportError("Не удалось запустить PDF renderer")
        plan = paint_document_pages(
            widget,
            painter,
            writer,
            QRectF(0.0, 0.0, float(writer.width()), float(writer.height())),
            pagination=job.pagination,
            context=context,
            fit_form_columns=job.page.fit_form_columns,
            high_quality=True,
        )
        if not painter.end():
            raise DocumentExportError("Не удалось завершить PDF renderer")
        if not temporary.exists() or temporary.stat().st_size == 0:
            raise DocumentExportError("Не удалось сформировать PDF")
        os.replace(temporary, destination)
        return PrintDocumentResult((destination,), plan.page_count)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        if isinstance(exc, (DocumentExportError, UnicodePrintError, ValueError)):
            raise
        raise DocumentExportError(f"Не удалось экспортировать PDF: {destination}") from exc
    finally:
        if painter.isActive():
            painter.end()


def export_document_pages(
    widget: QWidget,
    target: str | Path,
    job: PrintJobSettings,
    *,
    context: PrintDocumentContext,
    overwrite: bool = False,
) -> PrintDocumentResult:
    if job.output_format not in {
        PrintOutputFormat.PNG,
        PrintOutputFormat.JPEG,
        PrintOutputFormat.TIFF,
        PrintOutputFormat.BMP,
        PrintOutputFormat.WEBP,
        PrintOutputFormat.SVG,
    }:
        raise DocumentExportError("Формат не поддерживает постраничный файловый экспорт")
    destination = Path(target)
    _validate_destination(destination, job.output_format.accepted_suffixes, overwrite)
    _unicode_preflight(widget, context, job)
    plan = build_document_plan(widget, job.pagination)
    paths = _page_paths(destination, plan.page_count)
    for path in paths:
        if path.exists() and not overwrite:
            raise FileExistsError(path)
        path.parent.mkdir(parents=True, exist_ok=True)

    original = getattr(widget, "visible_depth_range", None)
    produced: list[Path] = []
    try:
        for page, path in zip(plan.pages, paths, strict=True):
            if page.has_vertical_range and hasattr(widget, "set_visible_depth"):
                widget.set_visible_depth(page.start, page.end)
                from PySide6.QtWidgets import QApplication

                QApplication.processEvents()
            if job.output_format is PrintOutputFormat.SVG:
                _write_svg_page(widget, path, job, context, page, plan)
            else:
                _write_raster_page(widget, path, job, context, page, plan)
            produced.append(path)
    except Exception:
        for path in produced:
            path.unlink(missing_ok=True)
        raise
    finally:
        if (
            isinstance(original, tuple)
            and len(original) == 2
            and hasattr(widget, "set_visible_depth")
        ):
            widget.set_visible_depth(*original)
            from PySide6.QtWidgets import QApplication

            QApplication.processEvents()
    return PrintDocumentResult(tuple(produced), plan.page_count)


def _write_raster_page(widget, path, job, context, page, plan) -> None:
    size = job.page.page_pixel_size(widget.width(), widget.height(), job.dpi)
    if size.width() * size.height() > _MAX_RASTER_PAGE_PIXELS:
        raise DocumentExportError(
            "Выбранное разрешение создаёт слишком большое изображение. Уменьшите DPI."
        )
    image_format = (
        QImage.Format.Format_RGB32
        if job.output_format in {PrintOutputFormat.JPEG, PrintOutputFormat.BMP}
        else QImage.Format.Format_ARGB32_Premultiplied
    )
    image = QImage(size, image_format)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    try:
        paint_document_page(
            widget,
            painter,
            _content_rect_pixels(QRectF(image.rect()), job),
            page=page,
            plan=plan,
            pagination=job.pagination,
            context=context,
            fit_form_columns=job.page.fit_form_columns,
            high_quality=True,
        )
    finally:
        painter.end()
    payload = QByteArray()
    buffer = QBuffer(payload)
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise DocumentExportError("Не удалось открыть буфер изображения")
    writer = QImageWriter(buffer, job.output_format.qt_image_format)
    if job.output_format in {PrintOutputFormat.JPEG, PrintOutputFormat.WEBP}:
        writer.setQuality(job.image_quality)
    if job.output_format in {PrintOutputFormat.PNG, PrintOutputFormat.TIFF}:
        writer.setCompression(75)
    if not writer.write(image):
        raise DocumentExportError(writer.errorString())
    _atomic_write(path, payload.data())


def _write_svg_page(widget, path, job, context, page, plan) -> None:
    temporary = _temporary_path(path)
    painter = QPainter()
    try:
        size = job.page.page_pixel_size(widget.width(), widget.height(), 96)
        generator = QSvgGenerator()
        generator.setFileName(str(temporary))
        generator.setSize(size)
        generator.setViewBox(QRect(0, 0, size.width(), size.height()))
        generator.setTitle(context.title)
        if not painter.begin(generator):
            raise DocumentExportError("Не удалось запустить SVG renderer")
        paint_document_page(
            widget,
            painter,
            _content_rect_pixels(QRectF(0.0, 0.0, float(size.width()), float(size.height())), job),
            page=page,
            plan=plan,
            pagination=job.pagination,
            context=context,
            fit_form_columns=job.page.fit_form_columns,
            high_quality=False,
        )
        if not painter.end():
            raise DocumentExportError("Не удалось завершить SVG renderer")
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    finally:
        if painter.isActive():
            painter.end()


def _content_rect_pixels(full: QRectF, job: PrintJobSettings) -> QRectF:
    page_mm = job.page.oriented_page_size_mm(1, 1)
    x_scale = full.width() / page_mm.width()
    y_scale = full.height() / page_mm.height()
    rect = QRectF(
        full.left() + job.page.margin_left_mm * x_scale,
        full.top() + job.page.margin_top_mm * y_scale,
        full.width() - (job.page.margin_left_mm + job.page.margin_right_mm) * x_scale,
        full.height() - (job.page.margin_top_mm + job.page.margin_bottom_mm) * y_scale,
    )
    if rect.width() <= 0 or rect.height() <= 0:
        raise DocumentExportError("Поля полностью перекрывают полезную область страницы")
    return rect


def _unicode_preflight(
    widget: QWidget, context: PrintDocumentContext, job: PrintJobSettings
) -> None:
    if not job.strict_unicode:
        return
    ensure_widget_printable_unicode(widget)
    metadata = preflight_texts([context.title, "GEOLOG GASRATIO@Pixler"])
    if not metadata.ok:
        raise UnicodePrintError(metadata.error_message())


def _page_paths(destination: Path, count: int) -> tuple[Path, ...]:
    if count <= 1:
        return (destination,)
    return tuple(
        destination.with_name(f"{destination.stem}_page_{index:03d}{destination.suffix}")
        for index in range(1, count + 1)
    )


def _validate_destination(destination: Path, suffixes: tuple[str, ...], overwrite: bool) -> None:
    if destination.suffix.casefold() not in suffixes:
        raise DocumentExportError("Неподдерживаемое расширение: " + destination.suffix)
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)


def _temporary_path(destination: Path) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(descriptor)
    return Path(name)


def _atomic_write(destination: Path, payload: bytes | bytearray | memoryview[int]) -> None:
    temporary = _temporary_path(destination)
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
