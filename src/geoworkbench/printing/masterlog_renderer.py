from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QLineF, QMarginsF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen

from geoworkbench.domain.models import MasterlogHeaderElement, MasterlogTemplate
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.header_fields import resolve_header_field


class MasterlogRenderError(RuntimeError):
    pass


def masterlog_size_mm(template: MasterlogTemplate) -> QSizeF:
    columns_width = sum(column.width_mm for column in template.columns)
    width = max(25.0, columns_width, 210.0 if template.page_format != "roll" else 0.0)
    body_height = template.properties.get("body_height_mm", 200.0)
    if not isinstance(body_height, (int, float)) or isinstance(body_height, bool):
        body_height = 200.0
    return QSizeF(width, template.header_height_mm + max(25.0, min(float(body_height), 4955.0)))


def paint_masterlog(
    painter: QPainter,
    target: QRectF,
    template: MasterlogTemplate,
    session: ProjectSession,
) -> None:
    size = masterlog_size_mm(template)
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
    _paint_columns(painter, template, size)
    painter.restore()


def export_masterlog_pdf(
    template: MasterlogTemplate,
    session: ProjectSession,
    target: str | Path,
    *,
    overwrite: bool = False,
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
        writer.setPageSize(_page_size(template))
        writer.setPageMargins(QMarginsF(0.0, 0.0, 0.0, 0.0), QPageLayout.Unit.Millimeter)
        writer.setResolution(300)
        writer.setTitle(template.name)
        writer.setCreator("GEOLOG GASRATIO@Pixler")
        painter = QPainter()
        if not painter.begin(writer):
            raise MasterlogRenderError("Не удалось запустить masterlog PDF renderer")
        paint_masterlog(
            painter,
            QRectF(0.0, 0.0, float(writer.width()), float(writer.height())),
            template,
            session,
        )
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


def _page_size(template: MasterlogTemplate) -> QPageSize:
    if template.page_format.upper() == "A3":
        return QPageSize(QPageSize.PageSizeId.A3)
    if template.page_format.upper() == "A4":
        return QPageSize(QPageSize.PageSizeId.A4)
    size = masterlog_size_mm(template)
    return QPageSize(size, QPageSize.Unit.Millimeter, "Masterlog roll")


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
            image = QImage.fromData(asset.payload)
            if not image.isNull():
                painter.drawImage(rect, image)
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


def _paint_columns(painter: QPainter, template: MasterlogTemplate, size: QSizeF) -> None:
    x = 0.0
    top = template.header_height_mm
    header_height = 12.0
    for column in template.columns:
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
        x += column.width_mm


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
