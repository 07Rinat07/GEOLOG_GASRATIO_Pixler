from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPoint, QRect
from PySide6.QtGui import QPainter, QPdfWriter
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtWidgets import QWidget

from geoworkbench.printing.page_settings import PrintPageSettings


class VisualizationExportError(RuntimeError):
    pass


def export_widget_png(
    widget: QWidget, target: str | Path, *, overwrite: bool = False
) -> Path:
    destination = Path(target)
    _validate_destination(destination, ".png", overwrite)
    pixmap = widget.grab()
    if pixmap.isNull():
        raise VisualizationExportError("Не удалось получить изображение визуализации")
    payload = QByteArray()
    buffer = QBuffer(payload)
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly) or not pixmap.save(buffer, "PNG"):
        raise VisualizationExportError("Не удалось сформировать PNG")
    return _atomic_write(destination, payload.data())


def export_widget_svg(
    widget: QWidget, target: str | Path, *, overwrite: bool = False
) -> Path:
    destination = Path(target)
    _validate_destination(destination, ".svg", overwrite)
    width = widget.width()
    height = widget.height()
    if width <= 0 or height <= 0:
        raise VisualizationExportError("Визуализация не имеет допустимого размера")
    temporary = _temporary_path(destination)
    painter: QPainter | None = None
    try:
        generator = QSvgGenerator()
        generator.setFileName(str(temporary))
        generator.setSize(widget.size())
        generator.setViewBox(QRect(0, 0, width, height))
        generator.setTitle("GEOLOG GASRATIO@Pixler visualization")
        painter = QPainter()
        if not painter.begin(generator):
            raise VisualizationExportError("Не удалось запустить SVG renderer")
        widget.render(painter, QPoint())
        if not painter.end():
            raise VisualizationExportError("Не удалось завершить SVG renderer")
        if not temporary.exists() or temporary.stat().st_size == 0:
            raise VisualizationExportError("Не удалось сформировать SVG")
        os.replace(temporary, destination)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        if isinstance(exc, VisualizationExportError):
            raise
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
) -> Path:
    destination = Path(target)
    _validate_destination(destination, ".pdf", overwrite)
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
        writer.setResolution(300)
        writer.setTitle("GEOLOG GASRATIO@Pixler visualization")
        writer.setCreator("GEOLOG GASRATIO@Pixler")
        painter = QPainter()
        if not painter.begin(writer):
            raise VisualizationExportError("Не удалось запустить PDF renderer")
        page_width = writer.width()
        page_height = writer.height()
        scale = min(page_width / width, page_height / height)
        painter.translate(
            (page_width - width * scale) / 2.0,
            (page_height - height * scale) / 2.0,
        )
        painter.scale(scale, scale)
        widget.render(painter, QPoint())
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


def _validate_destination(destination: Path, suffix: str, overwrite: bool) -> None:
    if destination.suffix.casefold() != suffix:
        raise VisualizationExportError(
            "Неподдерживаемое расширение экспорта: " + destination.suffix
        )
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)


def _atomic_write(
    destination: Path, payload: bytes | bytearray | memoryview[int]
) -> Path:
    temporary = _temporary_path(destination)
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, destination)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise VisualizationExportError(f"Не удалось экспортировать PNG: {destination}") from exc
    return destination


def _temporary_path(destination: Path) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(descriptor)
    return Path(name)
