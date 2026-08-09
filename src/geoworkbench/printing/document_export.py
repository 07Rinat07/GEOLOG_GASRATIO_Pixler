from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import os
from pathlib import Path
import stat
import tempfile
import time

import shiboken6
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
    printable_content_dimensions,
)
from geoworkbench.printing.print_job import PrintJobSettings, PrintOutputFormat
from geoworkbench.printing.unicode_support import (
    UnicodePrintError,
    collect_widget_text,
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
_PDF_REPLACE_RETRY_TIMEOUT_SECONDS = 2.0
_PDF_REPLACE_RETRY_INTERVAL_SECONDS = 0.05
_STALE_EXPORT_TEMP_SECONDS = 24 * 60 * 60
_EXPORT_TEMP_PREFIX = "geolog-export-"


def render_document_to_printer(
    widget: QWidget,
    printer: QPrinter,
    job: PrintJobSettings,
    *,
    context: PrintDocumentContext,
) -> int:
    detached = _detached_tablet_source(widget)
    if detached is not None:
        try:
            return render_document_to_printer(
                detached,
                printer,
                job,
                context=context,
            )
        finally:
            detached.close()
            detached.deleteLater()
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
            QRectF(0.0, 0.0, page.width(), page.height()),
            job=job,
            context=context,
            high_quality=True,
            first_page=first,
            last_page=last,
        )
        if not painter.end():
            raise DocumentExportError("Не удалось завершить печатный renderer")
        from geoworkbench.printing.printer_gate import selected_page_count

        return selected_page_count(plan.page_count, first, last)
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
    detached = _detached_tablet_source(widget)
    if detached is not None:
        try:
            return export_document_pdf(
                detached,
                target,
                job,
                context=context,
                overwrite=overwrite,
            )
        finally:
            detached.close()
            detached.deleteLater()
    destination = Path(target)
    _validate_destination(destination, (".pdf",), overwrite)
    _unicode_preflight(widget, context, job)
    _cleanup_stale_temporary_paths(destination)
    temporary = _temporary_path(destination)
    try:
        page_count = _render_document_pdf_file(
            widget,
            temporary,
            job,
            context=context,
        )
        if not temporary.exists() or temporary.stat().st_size == 0:
            raise DocumentExportError("Не удалось сформировать PDF")
        _replace_pdf_file(temporary, destination)
        return PrintDocumentResult((destination,), page_count)
    except Exception as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            # Preserve the original export failure. A still-open Windows handle
            # must not replace it with a cleanup exception.
            pass
        if isinstance(exc, (DocumentExportError, UnicodePrintError, ValueError)):
            raise
        raise DocumentExportError(
            f"Не удалось экспортировать PDF: {destination}: {exc}"
        ) from exc


def _render_document_pdf_file(
    widget: QWidget,
    temporary: Path,
    job: PrintJobSettings,
    *,
    context: PrintDocumentContext,
) -> int:
    """Render a PDF and release Qt file handles before the caller renames it."""

    writer = QPdfWriter(str(temporary))
    painter = QPainter()
    try:
        content_width, content_height = printable_content_dimensions(widget, job)
        writer.setPageSize(job.page.page_size_for_content(content_width, content_height))
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
            job=job,
            context=context,
            high_quality=True,
        )
        if not painter.end():
            raise DocumentExportError("Не удалось завершить PDF renderer")
        return plan.page_count
    finally:
        if painter.isActive():
            painter.end()
        # QPdfWriter owns the Windows file handle until its wrapped C++ instance
        # is destroyed. Dropping only the Python reference is not sufficient on
        # every PySide/Windows runtime.
        del painter
        try:
            if shiboken6.isValid(writer):
                shiboken6.delete(writer)
        except (TypeError, RuntimeError):
            # Test doubles are regular Python objects and are finalized by del.
            pass
        del writer


def _replace_pdf_file(temporary: Path, destination: Path) -> None:
    """Publish a PDF after a transient Windows sharing lock clears."""

    deadline = time.monotonic() + _PDF_REPLACE_RETRY_TIMEOUT_SECONDS
    while True:
        try:
            os.replace(temporary, destination)
            return
        except OSError as exc:
            if getattr(exc, "winerror", None) not in {5, 32}:
                raise
            if time.monotonic() >= deadline:
                raise
            time.sleep(_PDF_REPLACE_RETRY_INTERVAL_SECONDS)


def export_document_pages(
    widget: QWidget,
    target: str | Path,
    job: PrintJobSettings,
    *,
    context: PrintDocumentContext,
    overwrite: bool = False,
) -> PrintDocumentResult:
    detached = _detached_tablet_source(widget)
    if detached is not None:
        try:
            return export_document_pages(
                detached,
                target,
                job,
                context=context,
                overwrite=overwrite,
            )
        finally:
            detached.close()
            detached.deleteLater()
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
    plan = build_document_plan(widget, job, context=context)
    paths = _page_paths(destination, plan.page_count)
    _cleanup_stale_temporary_paths(paths)
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
    return PrintDocumentResult(tuple(produced), plan.page_count)


def _write_raster_page(widget, path, job, context, page, plan) -> None:
    content_width, content_height = printable_content_dimensions(widget, job)
    size = job.page.page_pixel_size(content_width, content_height, job.dpi)
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
            _content_rect_pixels(QRectF(image.rect()), job, content_width, content_height),
            page=page,
            plan=plan,
            job=job,
            context=context,
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
        content_width, content_height = printable_content_dimensions(widget, job)
        size = job.page.page_pixel_size(content_width, content_height, 96)
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
            _content_rect_pixels(
                QRectF(0.0, 0.0, float(size.width()), float(size.height())),
                job,
                content_width,
                content_height,
            ),
            page=page,
            plan=plan,
            job=job,
            context=context,
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


def _content_rect_pixels(
    full: QRectF,
    job: PrintJobSettings,
    content_width: int,
    content_height: int,
) -> QRectF:
    page_mm = job.page.oriented_page_size_mm(content_width, content_height)
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
    if job.included_track_ids is None or not hasattr(widget, "printable_tracks"):
        ensure_widget_printable_unicode(widget)
    else:
        included = frozenset(job.included_track_ids)
        selected_texts: list[str] = []
        printable_tracks = getattr(widget, "printable_tracks")
        for rendered in printable_tracks():
            if rendered.definition.track_id in included:
                selected_texts.extend(collect_widget_text(rendered.widget))
        selected_report = preflight_texts(selected_texts)
        if not selected_report.ok:
            raise UnicodePrintError(selected_report.error_message())
    metadata = preflight_texts([context.title, "GEOLOG GASRATIO@Pixler"])
    if not metadata.ok:
        raise UnicodePrintError(metadata.error_message())


def _detached_tablet_source(widget: QWidget) -> QWidget | None:
    """Return a hidden print clone so page rendering never mutates the live UI."""

    from geoworkbench.tablet.tablet_view import TabletView

    if not isinstance(widget, TabletView):
        return None
    if bool(widget.property("geoworkbench-print-clone")):
        return None
    return widget.create_print_clone()


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
        prefix=f".{destination.name}.{_EXPORT_TEMP_PREFIX}",
        suffix=".tmp",
        dir=destination.parent,
    )
    os.close(descriptor)
    return Path(name)


def _cleanup_stale_temporary_paths(
    destinations: Path | Iterable[Path],
    *,
    now: float | None = None,
) -> int:
    """Delete old atomic-write leftovers for the exact destinations only."""

    current_time = time.time() if now is None else float(now)
    paths = (destinations,) if isinstance(destinations, Path) else tuple(destinations)
    names_by_parent: dict[Path, set[str]] = {}
    for destination in paths:
        names_by_parent.setdefault(destination.parent, set()).add(destination.name)
    deleted = 0
    marker = f".{_EXPORT_TEMP_PREFIX}"
    for parent, destination_names in names_by_parent.items():
        for candidate in parent.iterdir():
            name = candidate.name
            marker_index = name.rfind(marker)
            if (
                not name.startswith(".")
                or not name.endswith(".tmp")
                or marker_index <= 1
                or name[1:marker_index] not in destination_names
                or not candidate.is_file()
                or _is_reparse_point(candidate)
            ):
                continue
            try:
                age = current_time - candidate.stat().st_mtime
                if age >= _STALE_EXPORT_TEMP_SECONDS:
                    candidate.unlink()
                    deleted += 1
            except OSError:
                # A locked/current export belongs to another process. Leave it alone.
                continue
    return deleted


def _is_reparse_point(path: Path) -> bool:
    try:
        details = path.lstat()
    except OSError:
        return True
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(details, "st_file_attributes", 0)
    return path.is_symlink() or bool(reparse_flag and attributes & reparse_flag)


def _atomic_write(destination: Path, payload: bytes | bytearray | memoryview[int]) -> None:
    temporary = _temporary_path(destination)
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
