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

from geoworkbench.printing.page_renderer import PageRenderError, paint_widget_page
from geoworkbench.printing.page_settings import PrintPageSettings
from geoworkbench.printing.print_job import PrintOutputFormat


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
    pixel_size = settings.page_pixel_size(width, height, dpi)
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
    content = _content_rect_pixels(full, settings, width, height)
    painter = QPainter(image)
    try:
        paint_widget_page(
            widget,
            painter,
            content,
            fit_form_columns=settings.fit_form_columns,
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
            size = settings.page_pixel_size(width, height, 96)
            content = _content_rect_pixels(
                QRectF(0.0, 0.0, float(size.width()), float(size.height())),
                settings,
                width,
                height,
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
                fit_form_columns=settings.fit_form_columns,
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
    destination = Path(target)
    _validate_destination(destination, (".pdf",), overwrite)
    width = widget.width()
    height = widget.height()
    if width <= 0 or height <= 0:
        raise VisualizationExportError("Визуализация не имеет допустимого размера")
    temporary = _temporary_path(destination)
    painter: QPainter | None = None
    try:
        writer = QPdfWriter(str(temporary))
        settings = page_settings or PrintPageSettings()
        writer.setPageSize(settings.page_size_for_content(width, height))
        writer.setPageOrientation(settings.qt_orientation)
        writer.setPageMargins(settings.qt_margins, QPageLayout.Unit.Millimeter)
        writer.setResolution(dpi)
        writer.setTitle("GEOLOG GASRATIO@Pixler visualization")
        writer.setCreator("GEOLOG GASRATIO@Pixler")
        page_width = writer.width()
        page_height = writer.height()
        painter = QPainter()
        if not painter.begin(writer):
            raise VisualizationExportError("Не удалось запустить PDF renderer")
        try:
            paint_widget_page(
                widget,
                painter,
                QRectF(0.0, 0.0, float(page_width), float(page_height)),
                fit_form_columns=settings.fit_form_columns,
                high_quality=True,
            )
        except PageRenderError as exc:
            raise VisualizationExportError(str(exc)) from exc
        if not painter.end():
            raise VisualizationExportError("Не удалось завершить PDF renderer")
        if not temporary.exists() or temporary.stat().st_size == 0:
            raise VisualizationExportError("Не удалось сформировать PDF")
        os.replace(temporary, destination)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        if isinstance(exc, VisualizationExportError):
            raise
        raise VisualizationExportError(f"Не удалось экспортировать PDF: {destination}") from exc
    finally:
        if painter is not None and painter.isActive():
            painter.end()
    return destination


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
