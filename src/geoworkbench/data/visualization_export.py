from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPoint, QRect, QRectF, Qt
from PySide6.QtGui import (
    QImage,
    QImageWriter,
    QPageLayout,
    QPainter,
    QPdfWriter,
)
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtWidgets import QWidget

from geoworkbench.printing.document_renderer import build_document_plan
from geoworkbench.printing.page_renderer import PageRenderError, paint_widget_page
from geoworkbench.printing.page_settings import PrintPageSettings
from geoworkbench.printing.pagination import PrintPaginationSettings, PrintRangeMode
from geoworkbench.printing.print_job import PrintJobSettings, PrintOutputFormat


class VisualizationExportError(RuntimeError):
    pass


_MAX_RASTER_PAGE_PIXELS = 80_000_000


def export_widget_png(widget: QWidget, target: str | Path, *, overwrite: bool = False) -> Path:
    """Backward-compatible screen-sized PNG export."""

    destination = Path(target)
    _validate_destination(destination, (".png",), overwrite)
    pixmap = widget.grab()
    if pixmap.isNull():
        raise VisualizationExportError("Не удалось получить изображение визуализации")
    payload = QByteArray()
    buffer = QBuffer(payload)
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly) or not pixmap.save(buffer, "PNG"):
        raise VisualizationExportError("Не удалось сформировать PNG")
    return _atomic_write(destination, payload.data(), "PNG")


def export_widget_page_image(
    widget: QWidget,
    target: str | Path,
    *,
    output_format: PrintOutputFormat,
    page_settings: PrintPageSettings | None = None,
    dpi: int = 300,
    quality: int = 92,
    overwrite: bool = False,
) -> Path:
    if not output_format.is_raster:
        raise VisualizationExportError("Выбранный формат не является растровым")
    destination = Path(target)
    _validate_destination(destination, output_format.accepted_suffixes, overwrite)
    if isinstance(dpi, bool) or not isinstance(dpi, int) or not 72 <= dpi <= 600:
        raise VisualizationExportError("Разрешение должно быть от 72 до 600 DPI")
    if isinstance(quality, bool) or not isinstance(quality, int) or not 1 <= quality <= 100:
        raise VisualizationExportError("Качество изображения должно быть от 1 до 100")

    width = widget.width()
    height = widget.height()
    if width <= 0 or height <= 0:
        raise VisualizationExportError("Визуализация не имеет допустимого размера")
    settings = page_settings or PrintPageSettings()
    plan, _job = _single_output_plan(
        widget, destination, output_format, settings, dpi=dpi, quality=quality
    )
    page = _require_single_output_page(plan, output_format.value.upper())
    pixel_size = settings.page_pixel_size(plan.source_width_px, plan.source_height_px, dpi)
    if pixel_size.width() * pixel_size.height() > _MAX_RASTER_PAGE_PIXELS:
        raise VisualizationExportError(
            "Выбранное разрешение создаёт слишком большое изображение. "
            "Уменьшите DPI или формат страницы."
        )

    image_format = (
        QImage.Format.Format_RGB32
        if output_format in {PrintOutputFormat.JPEG, PrintOutputFormat.BMP}
        else QImage.Format.Format_ARGB32_Premultiplied
    )
    image = QImage(pixel_size, image_format)
    image.fill(Qt.GlobalColor.white)
    full = QRectF(0.0, 0.0, float(pixel_size.width()), float(pixel_size.height()))
    content = _content_rect_pixels(
        full, settings, plan.source_width_px, plan.source_height_px
    )
    painter = QPainter(image)
    try:
        paint_widget_page(
            widget,
            painter,
            content,
            fit_form_columns=settings.effective_fit_form_columns,
            scale_mode=settings.scale_mode,
            continuation=page.continuation,
            high_quality=True,
        )
    except PageRenderError as exc:
        raise VisualizationExportError(str(exc)) from exc
    finally:
        painter.end()

    payload = QByteArray()
    buffer = QBuffer(payload)
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise VisualizationExportError("Не удалось открыть буфер изображения")
    writer = QImageWriter(buffer, output_format.qt_image_format)
    if output_format in {PrintOutputFormat.JPEG, PrintOutputFormat.WEBP}:
        writer.setQuality(quality)
    if output_format in {PrintOutputFormat.PNG, PrintOutputFormat.TIFF}:
        # Lossless formats use balanced compression instead of pretending that
        # the JPEG quality percentage changes image fidelity.
        writer.setCompression(75)
    if not writer.write(image):
        raise VisualizationExportError(
            f"Не удалось сформировать {output_format.value.upper()}: {writer.errorString()}"
        )
    return _atomic_write(destination, payload.data(), output_format.value.upper())


def export_widget_svg(
    widget: QWidget,
    target: str | Path,
    *,
    overwrite: bool = False,
    page_settings: PrintPageSettings | None = None,
) -> Path:
    destination = Path(target)
    _validate_destination(destination, (".svg",), overwrite)
    width = widget.width()
    height = widget.height()
    if width <= 0 or height <= 0:
        raise VisualizationExportError("Визуализация не имеет допустимого размера")
    settings = page_settings
    plan = None
    page = None
    if settings is not None:
        plan, _job = _single_output_plan(
            widget, destination, PrintOutputFormat.SVG, settings, dpi=96, quality=92
        )
        page = _require_single_output_page(plan, "SVG")
    temporary = _temporary_path(destination)
    painter: QPainter | None = None
    generator: QSvgGenerator | None = None
    try:
        generator = QSvgGenerator()
        generator.setFileName(str(temporary))
        if settings is None:
            size = widget.size()
            content = QRectF(0.0, 0.0, float(width), float(height))
        else:
            assert plan is not None
            size = settings.page_pixel_size(
                plan.source_width_px, plan.source_height_px, 96
            )
            content = _content_rect_pixels(
                QRectF(0.0, 0.0, float(size.width()), float(size.height())),
                settings,
                plan.source_width_px,
                plan.source_height_px,
            )
        generator.setSize(size)
        generator.setViewBox(QRect(0, 0, size.width(), size.height()))
        generator.setTitle("GEOLOG GASRATIO@Pixler visualization")
        painter = QPainter()
        if not painter.begin(generator):
            raise VisualizationExportError("Не удалось запустить SVG renderer")
        if settings is None:
            widget.render(painter, QPoint())
        else:
            paint_widget_page(
                widget,
                painter,
                content,
                fit_form_columns=settings.effective_fit_form_columns,
                scale_mode=settings.scale_mode,
                continuation=page.continuation if page is not None else None,
                high_quality=False,
            )
        if not painter.end():
            raise VisualizationExportError("Не удалось завершить SVG renderer")
        # On Windows QSvgGenerator keeps its output handle open until both the
        # painter wrapper and generator are destroyed. Release them before the
        # atomic replace, otherwise os.replace fails with WinError 32.
        painter = None
        generator = None
        if not temporary.exists() or temporary.stat().st_size == 0:
            raise VisualizationExportError("Не удалось сформировать SVG")
        os.replace(temporary, destination)
    except Exception as exc:
        if painter is not None and painter.isActive():
            painter.end()
        painter = None
        generator = None
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        if isinstance(exc, VisualizationExportError):
            raise
        if isinstance(exc, PageRenderError):
            raise VisualizationExportError(str(exc)) from exc
        raise VisualizationExportError(f"Не удалось экспортировать SVG: {destination}") from exc
    finally:
        if painter is not None and painter.isActive():
            painter.end()
    return destination


def export_widget_pdf(
    widget: QWidget,
    target: str | Path,
    *,
    overwrite: bool = False,
    page_settings: PrintPageSettings | None = None,
    dpi: int = 300,
) -> Path:
    """Export the current view through the unified media/continuation plan."""

    destination = Path(target)
    _validate_destination(destination, (".pdf",), overwrite)
    width = widget.width()
    height = widget.height()
    if width <= 0 or height <= 0:
        raise VisualizationExportError("Визуализация не имеет допустимого размера")
    settings = page_settings or PrintPageSettings()
    plan, _job = _single_output_plan(
        widget, destination, PrintOutputFormat.PDF, settings, dpi=dpi, quality=92
    )
    temporary = _temporary_path(destination)
    painter: QPainter | None = None
    try:
        writer = QPdfWriter(str(temporary))
        writer.setPageSize(
            settings.page_size_for_content(plan.source_width_px, plan.source_height_px)
        )
        writer.setPageOrientation(settings.qt_orientation)
        writer.setPageMargins(settings.qt_margins, QPageLayout.Unit.Millimeter)
        writer.setResolution(dpi)
        writer.setTitle("GEOLOG GASRATIO@Pixler visualization")
        writer.setCreator("GEOLOG GASRATIO@Pixler")
        painter = QPainter()
        if not painter.begin(writer):
            raise VisualizationExportError("Не удалось запустить PDF renderer")
        content = _content_rect_pixels(
            QRectF(0.0, 0.0, float(writer.width()), float(writer.height())),
            settings,
            plan.source_width_px,
            plan.source_height_px,
        )
        for page_index, page in enumerate(plan.pages):
            if page_index > 0 and not writer.newPage():
                raise VisualizationExportError(
                    "PDF renderer не смог создать страницу продолжения"
                )
            paint_widget_page(
                widget,
                painter,
                content,
                fit_form_columns=settings.effective_fit_form_columns,
                scale_mode=settings.scale_mode,
                continuation=page.continuation,
                high_quality=True,
            )
        if not painter.end():
            raise VisualizationExportError("Не удалось завершить PDF renderer")
        if not temporary.exists() or temporary.stat().st_size == 0:
            raise VisualizationExportError("Не удалось сформировать PDF")
        os.replace(temporary, destination)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        if isinstance(exc, VisualizationExportError):
            raise
        if isinstance(exc, PageRenderError):
            raise VisualizationExportError(str(exc)) from exc
        raise VisualizationExportError(
            f"Не удалось экспортировать PDF: {destination}"
        ) from exc
    finally:
        if painter is not None and painter.isActive():
            painter.end()
    return destination


def _single_output_plan(
    widget: QWidget,
    destination: Path,
    output_format: PrintOutputFormat,
    settings: PrintPageSettings,
    *,
    dpi: int,
    quality: int,
):
    job = PrintJobSettings(
        output_format=output_format,
        page=settings,
        dpi=dpi,
        image_quality=quality,
        target=destination,
        pagination=PrintPaginationSettings(
            range_mode=PrintRangeMode.CURRENT,
            show_page_numbers=False,
            show_page_range=False,
        ),
    )
    return build_document_plan(widget, job), job


def _require_single_output_page(plan, format_name: str):
    if plan.page_count != 1:
        raise VisualizationExportError(
            f"Режим 100% требует {plan.page_count} страниц продолжения для {format_name}. "
            "Используйте Центр печати для постраничного экспорта."
        )
    return plan.pages[0]


def _content_rect_pixels(
    full_rect: QRectF,
    settings: PrintPageSettings,
    source_width: int,
    source_height: int,
) -> QRectF:
    page_mm = settings.oriented_page_size_mm(source_width, source_height)
    x_scale = full_rect.width() / page_mm.width()
    y_scale = full_rect.height() / page_mm.height()
    content = QRectF(
        full_rect.left() + settings.margin_left_mm * x_scale,
        full_rect.top() + settings.margin_top_mm * y_scale,
        full_rect.width() - (settings.margin_left_mm + settings.margin_right_mm) * x_scale,
        full_rect.height() - (settings.margin_top_mm + settings.margin_bottom_mm) * y_scale,
    )
    if content.width() <= 0 or content.height() <= 0:
        raise VisualizationExportError("Поля полностью перекрывают полезную область страницы")
    return content


def _validate_destination(
    destination: Path,
    suffixes: tuple[str, ...],
    overwrite: bool,
) -> None:
    if destination.suffix.casefold() not in suffixes:
        raise VisualizationExportError(
            "Неподдерживаемое расширение экспорта: " + destination.suffix
        )
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)


def _atomic_write(
    destination: Path,
    payload: bytes | bytearray | memoryview[int],
    format_name: str,
) -> Path:
    temporary = _temporary_path(destination)
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, destination)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise VisualizationExportError(
            f"Не удалось экспортировать {format_name}: {destination}"
        ) from exc
    return destination


def _temporary_path(destination: Path) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(descriptor)
    return Path(name)
