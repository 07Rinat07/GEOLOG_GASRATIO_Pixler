from __future__ import annotations

import os
import tempfile
from pathlib import Path
from collections.abc import Sequence
from typing import Protocol

import numpy as np
from PySide6.QtCore import QLineF, QMarginsF, QRectF, QSizeF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QPageLayout,
    QPageSize,
    QPainter,
    QPainterPath,
    QPdfWriter,
    QPen,
)
from PySide6.QtPrintSupport import QPrinter

from geoworkbench.domain.models import Dataset, MasterlogColumnTemplate, MasterlogHeaderElement, MasterlogTemplate
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.header_fields import resolve_header_field
from geoworkbench.printing.image_asset_rendering import draw_image_asset
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.services.localization import AppLanguage, Localizer


class MasterlogRenderError(RuntimeError):
    pass


class PagedPaintDevice(Protocol):
    def width(self) -> int: ...
    def height(self) -> int: ...
    def pageLayout(self) -> QPageLayout: ...
    def newPage(self) -> bool: ...


def masterlog_size_mm(
    template: MasterlogTemplate,
    session: ProjectSession | None = None,
    *,
    depth_range: tuple[float, float] | None = None,
) -> QSizeF:
    columns_width = sum(column.width_mm for column in template.columns)
    minimum_width = (
        _fixed_page_size_mm(template).width()
        if template.page_format.casefold() != "roll"
        else 0.0
    )
    width = max(25.0, columns_width, minimum_width)
    if depth_range is None and session is not None:
        depth_range = masterlog_depth_range(session)
    if depth_range is not None:
        depth_scale = _depth_scale(template)
        body_height = 12.0 + (depth_range[1] - depth_range[0]) * 1000.0 / depth_scale
    else:
        body_height = template.properties.get("body_height_mm", 200.0)
        if not isinstance(body_height, (int, float)) or isinstance(body_height, bool):
            body_height = 200.0
    return QSizeF(width, template.header_height_mm + max(25.0, min(float(body_height), 4955.0)))


def masterlog_page_ranges(
    template: MasterlogTemplate,
    session: ProjectSession,
    settings: MasterlogOutputSettings | None = None,
) -> tuple[tuple[float, float], ...]:
    available_range = masterlog_depth_range(session)
    depth_range: tuple[float, float] | None
    if settings is not None:
        if available_range is None:
            raise MasterlogRenderError("Dataset не содержит печатного глубинного интервала")
        if (
            settings.depth_top < available_range[0]
            or settings.depth_bottom > available_range[1]
        ):
            raise MasterlogRenderError("Интервал выпуска выходит за границы active dataset")
        depth_range = settings.depth_range
    else:
        depth_range = available_range
    if depth_range is None:
        return ()
    if template.page_format.casefold() == "roll":
        return (depth_range,)
    page_size = _fixed_page_size_mm(template)
    depth_scale = _depth_scale(template)
    plot_height_mm = page_size.height() - template.header_height_mm - 12.0
    if plot_height_mm <= 0:
        raise MasterlogRenderError("Высота шапки не оставляет места для глубинных колонок")
    capacity = plot_height_mm * depth_scale / 1000.0
    top, bottom = depth_range
    ranges: list[tuple[float, float]] = []
    page_top = top
    while page_top < bottom:
        page_bottom = min(bottom, page_top + capacity)
        ranges.append((page_top, page_bottom))
        page_top = page_bottom
    return tuple(ranges)


def masterlog_column_groups(
    template: MasterlogTemplate, page_width_mm: float
) -> tuple[tuple[MasterlogColumnTemplate, ...], ...]:
    if template.page_format.casefold() == "roll" or not template.columns:
        return (tuple(template.columns),)
    groups: list[tuple[MasterlogColumnTemplate, ...]] = []
    current: list[MasterlogColumnTemplate] = []
    current_width = 0.0
    for column in template.columns:
        if column.width_mm > page_width_mm:
            raise MasterlogRenderError(
                f"Колонка '{column.title}' шире печатной страницы"
            )
        if current and current_width + column.width_mm > page_width_mm:
            groups.append(tuple(current))
            current = []
            current_width = 0.0
        current.append(column)
        current_width += column.width_mm
    if current:
        groups.append(tuple(current))
    return tuple(groups)


def masterlog_page_size_mm(
    template: MasterlogTemplate,
    session: ProjectSession,
    settings: MasterlogOutputSettings | None = None,
) -> QSizeF:
    if template.page_format.casefold() == "roll":
        return masterlog_size_mm(
            template,
            session,
            depth_range=settings.depth_range if settings is not None else None,
        )
    return _fixed_page_size_mm(template)


def masterlog_depth_range(session: ProjectSession | None) -> tuple[float, float] | None:
    dataset = session.current_dataset if session is not None else None
    if dataset is None:
        return None
    try:
        values = np.asarray(dataset.active_index.values, dtype=np.float64)
    except (TypeError, ValueError):
        return None
    finite = values[np.isfinite(values)]
    if finite.size < 2:
        return None
    top, bottom = float(np.min(finite)), float(np.max(finite))
    return (top, bottom) if bottom > top else None


def paint_masterlog(
    painter: QPainter,
    target: QRectF,
    template: MasterlogTemplate,
    session: ProjectSession,
    *,
    depth_range: tuple[float, float] | None = None,
    canvas_size_mm: QSizeF | None = None,
    page_label: str | None = None,
    columns: Sequence[MasterlogColumnTemplate] | None = None,
) -> None:
    effective_range = depth_range or masterlog_depth_range(session)
    size = canvas_size_mm or masterlog_size_mm(
        template, session, depth_range=effective_range
    )
    scale = min(target.width() / size.width(), target.height() / size.height())
    painter.save()
    painter.translate(
        target.x() + (target.width() - size.width() * scale) / 2.0,
        target.y() + (target.height() - size.height() * scale) / 2.0,
    )
    painter.scale(scale, scale)
    painter.fillRect(QRectF(0.0, 0.0, size.width(), size.height()), Qt.GlobalColor.white)
    painter.setPen(QPen(QColor("#111827"), 0.25))
    painter.drawRect(QRectF(0.0, 0.0, size.width(), size.height()))
    painter.drawLine(
        QLineF(0.0, template.header_height_mm, size.width(), template.header_height_mm)
    )
    for element in template.header_elements:
        _paint_header_element(painter, element, session)
    _paint_columns(
        painter,
        template,
        size,
        session,
        effective_range,
        columns if columns is not None else template.columns,
    )
    if page_label:
        font = QFont()
        font.setPointSizeF(6.5)
        painter.setFont(font)
        painter.setPen(QColor("#475569"))
        painter.drawText(
            QRectF(2.0, size.height() - 5.0, size.width() - 4.0, 4.0),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            page_label,
        )
    painter.restore()


def export_masterlog_pdf(
    template: MasterlogTemplate,
    session: ProjectSession,
    target: str | Path,
    *,
    overwrite: bool = False,
    settings: MasterlogOutputSettings | None = None,
) -> Path:
    destination = Path(target)
    if destination.suffix.casefold() != ".pdf":
        raise MasterlogRenderError("Masterlog PDF должен иметь расширение .pdf")
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(descriptor)
    temporary = Path(name)
    painter: QPainter | None = None
    try:
        writer = QPdfWriter(str(temporary))
        writer.setPageSize(_page_size(template, session, settings))
        writer.setPageOrientation(_page_orientation(template))
        writer.setPageMargins(QMarginsF(0.0, 0.0, 0.0, 0.0), QPageLayout.Unit.Millimeter)
        writer.setResolution(300)
        writer.setTitle(template.name)
        writer.setCreator("GEOLOG GASRATIO@Pixler")
        painter = QPainter()
        if not painter.begin(writer):
            raise MasterlogRenderError("Не удалось запустить masterlog PDF renderer")
        paint_masterlog_pages(painter, writer, template, session, settings=settings)
        if not painter.end():
            raise MasterlogRenderError("Не удалось завершить masterlog PDF renderer")
        if not temporary.exists() or temporary.stat().st_size == 0:
            raise MasterlogRenderError("Не удалось сформировать masterlog PDF")
        os.replace(temporary, destination)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        if isinstance(exc, (FileExistsError, MasterlogRenderError)):
            raise
        raise MasterlogRenderError(f"Не удалось экспортировать masterlog PDF: {destination}") from exc
    finally:
        if painter is not None and painter.isActive():
            painter.end()
    return destination


def configure_masterlog_printer(
    printer: QPrinter,
    template: MasterlogTemplate,
    session: ProjectSession,
    settings: MasterlogOutputSettings | None = None,
) -> None:
    printer.setPageSize(_page_size(template, session, settings))
    printer.setPageOrientation(_page_orientation(template))
    printer.setPageMargins(
        QMarginsF(0.0, 0.0, 0.0, 0.0), QPageLayout.Unit.Millimeter
    )
    printer.setFullPage(True)


def render_masterlog_to_printer(
    printer: QPrinter,
    template: MasterlogTemplate,
    session: ProjectSession,
    settings: MasterlogOutputSettings | None = None,
) -> None:
    painter = QPainter()
    if not painter.begin(printer):
        raise MasterlogRenderError("Не удалось запустить системный masterlog renderer")
    try:
        paint_masterlog_pages(painter, printer, template, session, settings=settings)
    finally:
        if painter.isActive() and not painter.end():
            raise MasterlogRenderError("Не удалось завершить системный masterlog renderer")


def paint_masterlog_pages(
    painter: QPainter,
    device: PagedPaintDevice,
    template: MasterlogTemplate,
    session: ProjectSession,
    *,
    settings: MasterlogOutputSettings | None = None,
) -> None:
    page_size_mm = device.pageLayout().fullRect(QPageLayout.Unit.Millimeter).size()
    page_ranges = masterlog_page_ranges(template, session, settings)
    segments: tuple[tuple[float, float] | None, ...] = page_ranges or (None,)
    groups = masterlog_column_groups(template, page_size_mm.width())
    pages = tuple((group, segment) for group in groups for segment in segments)
    language = settings.language if settings is not None else AppLanguage.RU
    localizer = Localizer.create(language)
    for page_index, (columns, page_range) in enumerate(pages):
        if page_index and not device.newPage():
            raise MasterlogRenderError("Не удалось создать следующую страницу masterlog")
        paint_masterlog(
            painter,
            QRectF(0.0, 0.0, float(device.width()), float(device.height())),
            template,
            session,
            depth_range=page_range,
            canvas_size_mm=page_size_mm,
            page_label=localizer.text(
                "masterlog_output.page", page=page_index + 1, pages=len(pages)
            ),
            columns=columns,
        )


def _page_size(
    template: MasterlogTemplate,
    session: ProjectSession,
    settings: MasterlogOutputSettings | None = None,
) -> QPageSize:
    if template.page_format.upper() == "A3":
        return QPageSize(QPageSize.PageSizeId.A3)
    if template.page_format.upper() == "A4":
        return QPageSize(QPageSize.PageSizeId.A4)
    if template.page_format.casefold() == "custom":
        return QPageSize(
            _custom_page_size_mm(template),
            QPageSize.Unit.Millimeter,
            "Masterlog custom",
        )
    size = masterlog_size_mm(
        template,
        session,
        depth_range=settings.depth_range if settings is not None else None,
    )
    return QPageSize(size, QPageSize.Unit.Millimeter, "Masterlog roll")


def _fixed_page_size_mm(template: MasterlogTemplate) -> QSizeF:
    if template.page_format.upper() == "A3":
        size = QSizeF(297.0, 420.0)
    elif template.page_format.casefold() == "custom":
        size = _custom_page_size_mm(template)
    else:
        size = QSizeF(210.0, 297.0)
    if _page_orientation(template) is QPageLayout.Orientation.Landscape:
        return QSizeF(size.height(), size.width())
    return size


def _custom_page_size_mm(template: MasterlogTemplate) -> QSizeF:
    width = template.properties.get("custom_width_mm", 210.0)
    height = template.properties.get("custom_height_mm", 297.0)
    valid_width = (
        float(width)
        if isinstance(width, (int, float))
        and not isinstance(width, bool)
        and 25.0 <= float(width) <= 5000.0
        else 210.0
    )
    valid_height = (
        float(height)
        if isinstance(height, (int, float))
        and not isinstance(height, bool)
        and 25.0 <= float(height) <= 5000.0
        else 297.0
    )
    return QSizeF(valid_width, valid_height)


def _page_orientation(template: MasterlogTemplate) -> QPageLayout.Orientation:
    return (
        QPageLayout.Orientation.Landscape
        if template.properties.get("orientation") == "landscape"
        else QPageLayout.Orientation.Portrait
    )


def _depth_scale(template: MasterlogTemplate) -> int:
    return (
        template.depth_scale
        if isinstance(template.depth_scale, int)
        and not isinstance(template.depth_scale, bool)
        and template.depth_scale > 0
        else 500
    )


def _paint_header_element(
    painter: QPainter, element: MasterlogHeaderElement, session: ProjectSession
) -> None:
    rect = QRectF(element.x_mm, element.y_mm, element.width_mm, element.height_mm)
    if element.element_type == "line":
        painter.setPen(_pen(element.properties, "#334155", 0.6))
        painter.drawLine(rect.topLeft(), rect.bottomRight())
        return
    if element.element_type == "image":
        asset_ref = element.properties.get("asset_ref")
        asset = session.image_assets.get(asset_ref) if isinstance(asset_ref, str) else None
        if asset is not None:
            draw_image_asset(painter, rect, asset)
        return
    text = _header_text(element, session)
    color = _color(element.properties.get("color"), "#0f172a")
    size = element.properties.get("font_size_mm", 3.5)
    font_size = float(size) if isinstance(size, (int, float)) and not isinstance(size, bool) else 3.5
    font = QFont()
    font.setPointSizeF(max(1.0, min(font_size, 50.0)) * 72.0 / 25.4)
    painter.setFont(font)
    painter.setPen(color)
    painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)


def _paint_columns(
    painter: QPainter,
    template: MasterlogTemplate,
    size: QSizeF,
    session: ProjectSession,
    depth_range: tuple[float, float] | None,
    columns: Sequence[MasterlogColumnTemplate],
) -> None:
    x = 0.0
    top = template.header_height_mm
    header_height = 12.0
    dataset = session.current_dataset
    for column in columns:
        rect = QRectF(x, top, column.width_mm, size.height() - top)
        painter.setPen(QPen(QColor("#334155"), 0.25))
        painter.drawRect(rect)
        painter.drawLine(
            QLineF(x, top + header_height, x + column.width_mm, top + header_height)
        )
        font = QFont()
        font.setPointSizeF(7.0)
        painter.setFont(font)
        painter.setPen(QColor("#0f172a"))
        title = column.title
        if column.show_legend and column.curve_mnemonics:
            title += "\n" + ", ".join(column.curve_mnemonics)
        painter.drawText(
            QRectF(x + 1.0, top + 0.5, column.width_mm - 2.0, header_height - 1.0),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            title,
        )
        plot_rect = QRectF(
            x + 0.5,
            top + header_height,
            max(0.1, column.width_mm - 1.0),
            max(0.1, size.height() - top - header_height),
        )
        if depth_range is not None and dataset is not None:
            if column.column_type == "depth":
                _paint_depth_axis(painter, plot_rect, depth_range)
            else:
                _paint_curve_column(painter, plot_rect, column, dataset, depth_range)
        x += column.width_mm


def _paint_depth_axis(
    painter: QPainter, rect: QRectF, depth_range: tuple[float, float]
) -> None:
    top, bottom = depth_range
    font = QFont()
    font.setPointSizeF(6.5)
    painter.setFont(font)
    painter.setPen(QPen(QColor("#64748b"), 0.15))
    for index in range(6):
        fraction = index / 5.0
        y = rect.top() + rect.height() * fraction
        depth = top + (bottom - top) * fraction
        painter.drawLine(QLineF(rect.left(), y, rect.right(), y))
        painter.setPen(QColor("#0f172a"))
        painter.drawText(
            QRectF(rect.left() + 0.5, y - 2.0, rect.width() - 1.0, 4.0),
            Qt.AlignmentFlag.AlignCenter,
            f"{depth:g}",
        )
        painter.setPen(QPen(QColor("#64748b"), 0.15))


def curve_x_range(
    column: MasterlogColumnTemplate, dataset: Dataset
) -> tuple[float, float] | None:
    if column.x_min is not None and column.x_max is not None:
        return float(column.x_min), float(column.x_max)
    chunks: list[np.ndarray] = []
    for mnemonic in column.curve_mnemonics:
        curve = dataset.curve_by_mnemonic(mnemonic)
        if curve is None:
            continue
        values = np.asarray(curve.values, dtype=np.float64)
        valid = np.isfinite(values)
        if column.x_scale == "logarithmic":
            valid &= values > 0
        if np.any(valid):
            chunks.append(values[valid])
    if not chunks:
        return None
    minimum = min(float(np.min(chunk)) for chunk in chunks)
    maximum = max(float(np.max(chunk)) for chunk in chunks)
    if maximum <= minimum:
        if column.x_scale == "logarithmic" and minimum > 0:
            return minimum / 1.1, maximum * 1.1
        padding = max(abs(minimum) * 0.05, 1.0)
        return minimum - padding, maximum + padding
    return minimum, maximum


def _paint_curve_column(
    painter: QPainter,
    rect: QRectF,
    column: MasterlogColumnTemplate,
    dataset: Dataset,
    depth_range: tuple[float, float],
) -> None:
    x_range = curve_x_range(column, dataset)
    if x_range is None:
        return
    depth = np.asarray(dataset.active_index.values, dtype=np.float64)
    top, bottom = depth_range
    minimum, maximum = x_range
    if column.x_scale == "logarithmic":
        if minimum <= 0 or maximum <= 0:
            return
        minimum, maximum = float(np.log10(minimum)), float(np.log10(maximum))
    styles = {
        "solid": Qt.PenStyle.SolidLine,
        "dash": Qt.PenStyle.DashLine,
        "dot": Qt.PenStyle.DotLine,
        "dash_dot": Qt.PenStyle.DashDotLine,
    }
    palette = (column.line_color, "#dc2626", "#16a34a", "#9333ea", "#ea580c")
    painter.save()
    painter.setClipRect(rect)
    for curve_index, mnemonic in enumerate(column.curve_mnemonics):
        curve = dataset.curve_by_mnemonic(mnemonic)
        if curve is None:
            continue
        values = np.asarray(curve.values, dtype=np.float64)
        if values.shape != depth.shape:
            continue
        pen = QPen(
            _color(palette[curve_index % len(palette)], "#2563eb"),
            column.line_width,
            styles[column.line_style],
        )
        painter.setPen(pen)
        path = QPainterPath()
        drawing = False
        stride = max(1, values.size // 5000)
        for index in range(0, values.size, stride):
            value, depth_value = float(values[index]), float(depth[index])
            valid = np.isfinite(value) and np.isfinite(depth_value)
            if column.x_scale == "logarithmic":
                valid = valid and value > 0
                if valid:
                    value = float(np.log10(value))
            if not valid or not top <= depth_value <= bottom:
                drawing = False
                continue
            x_fraction = (value - minimum) / (maximum - minimum)
            y_fraction = (depth_value - top) / (bottom - top)
            point_x = rect.left() + rect.width() * x_fraction
            point_y = rect.top() + rect.height() * y_fraction
            if drawing:
                path.lineTo(point_x, point_y)
            else:
                path.moveTo(point_x, point_y)
                drawing = True
        painter.drawPath(path)
    painter.restore()


def _header_text(element: MasterlogHeaderElement, session: ProjectSession) -> str:
    if element.element_type == "text":
        value = element.properties.get("text")
        return str(value) if isinstance(value, (str, int, float)) else ""
    field = element.properties.get("field")
    if not isinstance(field, str):
        return "{field}"
    return resolve_header_field(session, field) or "{" + field + "}"


def _color(value: object, fallback: str) -> QColor:
    color = QColor(value) if isinstance(value, str) else QColor(fallback)
    return color if color.isValid() else QColor(fallback)


def _pen(properties: dict[str, object], fallback: str, fallback_width: float) -> QPen:
    width = properties.get("width", fallback_width)
    normalized = (
        float(width)
        if isinstance(width, (int, float))
        and not isinstance(width, bool)
        and 0.1 <= float(width) <= 20.0
        else fallback_width
    )
    return QPen(_color(properties.get("color"), fallback), normalized)
