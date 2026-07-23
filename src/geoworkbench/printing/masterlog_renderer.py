from __future__ import annotations

import os
import tempfile
from math import isfinite
from pathlib import Path
from collections.abc import Sequence
from typing import Protocol

import numpy as np
from PySide6.QtCore import QLineF, QMarginsF, QPointF, QRectF, QSizeF, Qt
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

from geoworkbench.domain.stratigraphy_presentation import (
    stratigraphy_text_angle,
    stratigraphy_text_position_fraction,
)
from geoworkbench.domain.models import (
    CurveData,
    Dataset,
    LithologyInterval,
    MasterlogColumnTemplate,
    MasterlogCurveStyle,
    MasterlogHeaderElement,
    MasterlogTemplate,
)
from geoworkbench.project.lithotype_catalog_controller import (
    CatalogLithotype,
    LithotypeCatalogController,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.annotation_schema import (
    AnnotationAnchor,
    AnnotationKind,
    AnnotationStyle,
    annotation_from_canvas,
    annotation_matches_scope,
    annotation_scope_id_for_session,
    is_annotation_object,
)
from geoworkbench.project.stratigraphy_controller import stratigraphy_rank_order
from geoworkbench.printing.header_fields import resolve_header_field
from geoworkbench.printing.image_asset_rendering import draw_image_asset
from geoworkbench.printing.lba_visuals import (
    LBA_TYPE_STYLES,
    lba_intensity_name,
    normalized_lba_intensity,
    resolve_lba_type_style,
)
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.printing.text_rendering import (
    column_heading_height,
    draw_oriented_text,
)
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.las_parameter_resolver import LasParameterResolver
from geoworkbench.tablet.grid_renderer import normalized_grid_lines
from geoworkbench.tablet.lithology_legend import LithologyLegendEntry
from geoworkbench.tablet.lithology_patterns import masterlog_lithology_brush
from geoworkbench.tablet.sampling import select_visible_samples


def _set_scaled_font_mm(painter: QPainter, font: QFont, size_mm: float) -> None:
    """Set font size in the same millimetre coordinate system as the form.

    ``paint_masterlog`` scales a millimetre canvas to the output device.  A normal
    QFont point size would be scaled a second time by the painter transform and
    produce oversized, clipped text.  Convert the requested local millimetres to
    pre-transform points using the device DPI so text and column geometry scale
    together in preview, PDF, images and physical printing.
    """
    device = painter.device()
    dpi_y = float(device.logicalDpiY()) if device is not None else 96.0
    if not np.isfinite(dpi_y) or dpi_y <= 0.0:
        dpi_y = 96.0
    safe_mm = max(0.25, min(float(size_mm), 50.0))
    font.setPointSizeF(safe_mm * 72.0 / dpi_y)


def _set_scaled_font_points(painter: QPainter, font: QFont, size_points: float) -> None:
    """Set a conventional final point size on the scaled Masterlog canvas."""
    _set_scaled_font_mm(painter, font, float(size_points) * 25.4 / 72.0)


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
        _fixed_page_size_mm(template).width() if template.page_format.casefold() != "roll" else 0.0
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
        if settings.depth_top < available_range[0] or settings.depth_bottom > available_range[1]:
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
            raise MasterlogRenderError(f"Колонка '{column.title}' шире печатной страницы")
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
    language: AppLanguage = AppLanguage.RU,
) -> None:
    effective_range = depth_range or masterlog_depth_range(session)
    size = canvas_size_mm or masterlog_size_mm(template, session, depth_range=effective_range)
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
    lithotype_catalog = {
        item.lithotype_id: item for item in LithotypeCatalogController(session).available()
    }
    for element in template.header_elements:
        _paint_header_element(
            painter,
            element,
            session,
            template,
            effective_range,
            language,
            lithotype_catalog,
        )
    _paint_columns(
        painter,
        template,
        size,
        session,
        effective_range,
        columns if columns is not None else template.columns,
        language,
        lithotype_catalog,
    )
    if page_label:
        font = QFont()
        _set_scaled_font_points(painter, font, 6.5)
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
        raise MasterlogRenderError(
            f"Не удалось экспортировать masterlog PDF: {destination}"
        ) from exc
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
    printer.setPageMargins(QMarginsF(0.0, 0.0, 0.0, 0.0), QPageLayout.Unit.Millimeter)
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
            language=language,
        )


def _page_size(
    template: MasterlogTemplate,
    session: ProjectSession,
    settings: MasterlogOutputSettings | None = None,
) -> QPageSize:
    fixed_ids = {
        "A0": QPageSize.PageSizeId.A0, "A1": QPageSize.PageSizeId.A1,
        "A2": QPageSize.PageSizeId.A2, "A3": QPageSize.PageSizeId.A3,
        "A4": QPageSize.PageSizeId.A4, "LETTER": QPageSize.PageSizeId.Letter,
        "LEGAL": QPageSize.PageSizeId.Legal,
    }
    page_id = fixed_ids.get(template.page_format.upper())
    if page_id is not None:
        return QPageSize(page_id)
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
    fixed = {
        "A0": QSizeF(841.0, 1189.0), "A1": QSizeF(594.0, 841.0),
        "A2": QSizeF(420.0, 594.0), "A3": QSizeF(297.0, 420.0),
        "A4": QSizeF(210.0, 297.0), "LETTER": QSizeF(215.9, 279.4),
        "LEGAL": QSizeF(215.9, 355.6),
    }
    if template.page_format.casefold() == "custom":
        size = _custom_page_size_mm(template)
    else:
        size = fixed.get(template.page_format.upper(), QSizeF(210.0, 297.0))
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
    painter: QPainter,
    element: MasterlogHeaderElement,
    session: ProjectSession,
    template: MasterlogTemplate,
    depth_range: tuple[float, float] | None,
    language: AppLanguage,
    lithotype_catalog: dict[str, CatalogLithotype],
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
            if element.properties.get("background") and isinstance(
                element.properties.get("background"), str
            ):
                background = QColor(str(element.properties["background"]))
                if background.isValid():
                    painter.fillRect(rect, background)
            draw_image_asset(
                painter,
                rect,
                asset,
                mode=str(element.properties.get("mode", "fit")),
                rotation=float(element.properties.get("rotation", 0.0)),
                opacity=float(element.properties.get("opacity", 1.0)),
            )
            if element.properties.get("frame") is True:
                painter.setPen(
                    QPen(_color(element.properties.get("frame_color"), "#64748b"), 0.35)
                )
                painter.drawRect(rect)
        else:
            _paint_image_placeholder(painter, rect, element.properties, language)
        return
    if element.element_type == "lithotype_swatch":
        _paint_lithotype_swatch(
            painter,
            rect,
            element.properties,
            language,
            lithotype_catalog,
        )
        return
    if element.element_type == "lithology_legend":
        entries = _masterlog_lithology_legend_entries(
            session,
            depth_range,
            language,
            element.properties.get("scope"),
            lithotype_catalog,
            element.properties.get("selected_lithotype_ids"),
        )
        _paint_lithology_legend(painter, rect, entries, element.properties, language)
        return
    if element.element_type == "lba_legend":
        _paint_lba_legend(painter, rect, element.properties, language)
        return
    text = _header_text(element, session, template)
    color = _color(element.properties.get("color"), "#0f172a")
    raw_background = element.properties.get("background")
    if isinstance(raw_background, str) and QColor(raw_background).isValid():
        painter.fillRect(rect, QColor(raw_background))
    if element.properties.get("frame") is True:
        painter.setPen(QPen(_color(element.properties.get("frame_color"), "#334155"), 0.35))
        painter.drawRect(rect)
    size = element.properties.get("font_size_mm", 3.5)
    font_size = (
        float(size) if isinstance(size, (int, float)) and not isinstance(size, bool) else 3.5
    )
    font = QFont()
    font.setBold(element.properties.get("bold") is True)
    _set_scaled_font_mm(painter, font, max(1.0, min(font_size, 50.0)))
    painter.setFont(font)
    painter.setPen(color)
    alignment_name = element.properties.get("alignment", "left")
    horizontal = {
        "center": Qt.AlignmentFlag.AlignHCenter,
        "right": Qt.AlignmentFlag.AlignRight,
    }.get(alignment_name, Qt.AlignmentFlag.AlignLeft)
    draw_oriented_text(
        painter,
        rect.adjusted(0.3, 0.1, -0.3, -0.1),
        text,
        orientation=str(element.properties.get("text_orientation", "horizontal")),
        position=str(element.properties.get("text_position", "center")),
        horizontal_alignment=horizontal,
        padding_x=0.5,
        padding_y=0.1,
    )


def _paint_image_placeholder(
    painter: QPainter,
    rect: QRectF,
    properties: dict[str, object],
    language: AppLanguage,
) -> None:
    """Paint an editable empty image slot instead of silently leaving a hole."""

    painter.save()
    try:
        background_value = properties.get("background", "#f8fafc")
        background = QColor(str(background_value))
        painter.fillRect(rect, background if background.isValid() else QColor("#f8fafc"))
        frame_color = _color(properties.get("frame_color"), "#64748b")
        painter.setPen(QPen(frame_color, 0.35, Qt.PenStyle.DashLine))
        painter.drawRect(rect)
        painter.drawLine(rect.topLeft(), rect.bottomRight())
        painter.drawLine(rect.topRight(), rect.bottomLeft())
        localized_key = {
            AppLanguage.RU: "placeholder_text_ru",
            AppLanguage.KK: "placeholder_text_kk",
            AppLanguage.EN: "placeholder_text_en",
        }[language]
        raw_text = properties.get(localized_key) or properties.get("placeholder_text")
        placeholder = str(raw_text).strip() if raw_text is not None else ""
        if not placeholder:
            placeholder = {
                AppLanguage.RU: "Загрузить логотип",
                AppLanguage.KK: "Логотипті жүктеу",
                AppLanguage.EN: "Load logo",
            }[language]
        font = QFont()
        font.setBold(True)
        size = properties.get("placeholder_font_size_mm", 2.6)
        font_size = (
            float(size)
            if isinstance(size, (int, float)) and not isinstance(size, bool)
            else 2.6
        )
        _set_scaled_font_mm(painter, font, max(1.0, min(font_size, 12.0)))
        painter.setFont(font)
        painter.setPen(frame_color)
        painter.drawText(
            rect.adjusted(1.0, 1.0, -1.0, -1.0),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            placeholder,
        )
    finally:
        painter.restore()


def _paint_lithotype_swatch(
    painter: QPainter,
    rect: QRectF,
    properties: dict[str, object],
    language: AppLanguage,
    catalog: dict[str, CatalogLithotype],
) -> None:
    lithotype_id = properties.get("lithotype_id")
    lithotype = catalog.get(lithotype_id) if isinstance(lithotype_id, str) else None
    if lithotype is None:
        painter.save()
        try:
            painter.setPen(QPen(QColor("#dc2626"), 0.3, Qt.PenStyle.DashLine))
            painter.drawRect(rect)
            painter.drawLine(rect.topLeft(), rect.bottomRight())
            painter.drawLine(rect.topRight(), rect.bottomLeft())
        finally:
            painter.restore()
        return
    background = properties.get("background")
    if isinstance(background, str) and QColor(background).isValid():
        painter.fillRect(rect, QColor(background))
    mode = str(properties.get("display_mode", "pattern_code_name"))
    pattern_width = (
        rect.width()
        if mode == "pattern_only"
        else min(rect.width() * 0.38, max(5.0, rect.height() * 1.4))
    )
    pattern_rect = QRectF(rect.left(), rect.top(), pattern_width, rect.height()).adjusted(
        0.25, 0.25, -0.25, -0.25
    )
    painter.fillRect(pattern_rect, masterlog_lithology_brush(painter, lithotype.color, lithotype.pattern_key))
    painter.setPen(QPen(QColor("#64748b"), 0.25))
    painter.drawRect(pattern_rect)
    if mode != "pattern_only":
        name = lithotype.localized_name(language.value)
        text = f"{lithotype.code} — {name}" if mode == "pattern_code_name" else name
        size = properties.get("font_size_mm", 3.5)
        font_size = (
            float(size)
            if isinstance(size, (int, float)) and not isinstance(size, bool)
            else 3.5
        )
        font = QFont()
        font.setBold(properties.get("bold") is True)
        _set_scaled_font_mm(painter, font, max(1.0, min(font_size, 50.0)))
        painter.setFont(font)
        painter.setPen(_color(properties.get("color"), "#0f172a"))
        raw_alignment = properties.get("alignment", "left")
        alignment_name = raw_alignment if isinstance(raw_alignment, str) else "left"
        horizontal = {
            "center": Qt.AlignmentFlag.AlignHCenter,
            "right": Qt.AlignmentFlag.AlignRight,
        }.get(alignment_name, Qt.AlignmentFlag.AlignLeft)
        text_rect = QRectF(
            rect.left() + pattern_width + 0.4,
            rect.top(),
            max(0.0, rect.width() - pattern_width - 0.4),
            rect.height(),
        )
        draw_oriented_text(
            painter,
            text_rect,
            text,
            orientation=str(properties.get("text_orientation", "horizontal")),
            position=str(properties.get("text_position", "center")),
            horizontal_alignment=horizontal,
            padding_x=0.35,
            padding_y=0.15,
        )
    if properties.get("frame") is True:
        painter.setPen(QPen(_color(properties.get("frame_color"), "#334155"), 0.35))
        painter.drawRect(rect)


def masterlog_lithology_legend_entries(
    session: ProjectSession,
    depth_range: tuple[float, float] | None,
    language: AppLanguage,
    scope: str = "used",
) -> tuple[LithologyLegendEntry, ...]:
    catalog = {item.lithotype_id: item for item in LithotypeCatalogController(session).available()}
    return _masterlog_lithology_legend_entries(
        session,
        depth_range,
        language,
        scope,
        catalog,
        None,
    )


def _masterlog_lithology_legend_entries(
    session: ProjectSession,
    depth_range: tuple[float, float] | None,
    language: AppLanguage,
    scope: object,
    catalog: dict[str, CatalogLithotype],
    selected_lithotype_ids: object = None,
) -> tuple[LithologyLegendEntry, ...]:
    selected_scope = (
        scope
        if isinstance(scope, str) and scope in {"used", "all", "manual", "used_manual"}
        else "used"
    )
    raw_manual_ids = (
        selected_lithotype_ids
        if isinstance(selected_lithotype_ids, (list, tuple))
        else ()
    )
    manual_ids = [str(value) for value in raw_manual_ids if isinstance(value, str)]
    unknown_names = {
        AppLanguage.RU: "Неизвестный литотип",
        AppLanguage.KK: "Белгісіз литотип",
        AppLanguage.EN: "Unknown lithotype",
    }
    unknown_descriptions: dict[str, str] = {}
    if selected_scope == "all":
        lithotype_ids = list(catalog)
    elif selected_scope == "manual":
        lithotype_ids = manual_ids
    else:
        events: list[tuple[float, int, str]] = []
        well = session.current_well
        if well is not None:
            top = depth_range[0] if depth_range is not None else float("-inf")
            bottom = depth_range[1] if depth_range is not None else float("inf")
            for interval in well.lithology:
                if interval.bottom_depth < top or interval.top_depth > bottom:
                    continue
                events.append((interval.top_depth, 0, interval.lithotype_id))
                if interval.description:
                    unknown_descriptions.setdefault(
                        interval.lithotype_id, interval.description.strip()
                    )
            for sample in well.cuttings:
                if sample.bottom_depth < top or sample.top_depth > bottom:
                    continue
                for component_index, component in enumerate(sample.components, start=1):
                    events.append((sample.top_depth, component_index, component.lithotype_id))
        lithotype_ids = []
        seen: set[str] = set()
        for _, _, lithotype_id in sorted(events):
            if lithotype_id not in seen:
                seen.add(lithotype_id)
                lithotype_ids.append(lithotype_id)
        if selected_scope == "used_manual":
            for lithotype_id in manual_ids:
                if lithotype_id not in seen:
                    seen.add(lithotype_id)
                    lithotype_ids.append(lithotype_id)

    entries: list[LithologyLegendEntry] = []
    for lithotype_id in lithotype_ids:
        definition = catalog.get(lithotype_id)
        if definition is None:
            entries.append(
                LithologyLegendEntry(
                    lithotype_id,
                    lithotype_id,
                    unknown_descriptions.get(lithotype_id) or unknown_names[language],
                    "#b0b0b0",
                    "solid",
                )
            )
            continue
        entries.append(
            LithologyLegendEntry(
                definition.lithotype_id,
                definition.code,
                definition.localized_name(language.value),
                definition.color,
                definition.pattern_key,
            )
        )
    return tuple(entries)


def _paint_lithology_legend(
    painter: QPainter,
    rect: QRectF,
    entries: tuple[LithologyLegendEntry, ...],
    properties: dict[str, object],
    language: AppLanguage,
) -> None:
    raw_columns = properties.get("columns", 4)
    columns = (
        raw_columns if isinstance(raw_columns, int) and not isinstance(raw_columns, bool) else 4
    )
    columns = max(1, min(columns, 12, max(1, len(entries))))
    raw_size = properties.get("font_size_mm", 2.6)
    font_size = (
        float(raw_size)
        if isinstance(raw_size, (int, float)) and not isinstance(raw_size, bool)
        else 2.6
    )
    font_size = max(1.0, min(font_size, 8.0))
    show_code = properties.get("show_code", True)
    show_code = show_code if isinstance(show_code, bool) else True
    color = _color(properties.get("color"), "#0f172a")
    titles = {
        AppLanguage.RU: "ЛИТОЛОГИЧЕСКАЯ ЛЕГЕНДА",
        AppLanguage.KK: "ЛИТОЛОГИЯЛЫҚ ШАРТТЫ БЕЛГІЛЕР",
        AppLanguage.EN: "LITHOLOGICAL LEGEND",
    }
    empty_texts = {
        AppLanguage.RU: "В выбранном интервале нет литологии",
        AppLanguage.KK: "Таңдалған аралықта литология жоқ",
        AppLanguage.EN: "No lithology in the selected interval",
    }
    title_height = min(4.0, max(2.0, rect.height() * 0.18))
    content = rect.adjusted(0.0, title_height, 0.0, 0.0)
    painter.save()
    painter.setClipRect(rect)
    painter.setPen(QPen(QColor("#64748b"), 0.2))
    painter.drawRect(rect)
    title_font = QFont()
    title_font.setBold(True)
    _set_scaled_font_mm(painter, title_font, min(3.2, font_size + 0.4))
    painter.setFont(title_font)
    painter.setPen(color)
    painter.drawText(
        QRectF(rect.left() + 0.8, rect.top(), rect.width() - 1.6, title_height),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        titles[language],
    )
    if not entries:
        painter.drawText(
            content.adjusted(0.8, 0.0, -0.8, 0.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            empty_texts[language],
        )
        painter.restore()
        return
    rows = (len(entries) + columns - 1) // columns
    cell_width = content.width() / columns
    cell_height = content.height() / rows
    font = QFont()
    _set_scaled_font_mm(painter, font, font_size)
    painter.setFont(font)
    for index, entry in enumerate(entries):
        row, column = divmod(index, columns)
        cell = QRectF(
            content.left() + column * cell_width,
            content.top() + row * cell_height,
            cell_width,
            cell_height,
        )
        swatch_width = min(8.0, max(3.0, cell_width * 0.2))
        swatch = cell.adjusted(0.5, 0.5, -(cell.width() - swatch_width), -0.5)
        painter.fillRect(swatch, masterlog_lithology_brush(painter, entry.color, entry.pattern_key))
        painter.setPen(QPen(QColor("#475569"), 0.15))
        painter.drawRect(swatch)
        label = f"{entry.code} — {entry.name}" if show_code else entry.name
        painter.setPen(color)
        painter.drawText(
            cell.adjusted(swatch_width + 1.2, 0.0, -0.5, 0.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            label,
        )
    painter.restore()



def _paint_lba_intensity_symbol(
    painter: QPainter,
    center_x: float,
    center_y: float,
    diameter: float,
    color: QColor,
    intensity: int | None,
) -> None:
    """Paint the conventional LBA point/ring symbol used by masterlogs."""

    resolved = normalized_lba_intensity(intensity)
    diameter = max(1.2, float(diameter))
    radius = diameter / 2.0
    symbol_rect = QRectF(center_x - radius, center_y - radius, diameter, diameter)
    painter.save()
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if resolved == 1:
        dot = max(0.8, diameter * 0.24)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(QRectF(center_x - dot / 2.0, center_y - dot / 2.0, dot, dot))
    elif resolved == 2:
        painter.setPen(QPen(color, max(0.25, diameter * 0.07), Qt.PenStyle.DashLine))
        painter.drawEllipse(symbol_rect)
    elif resolved == 3:
        painter.setPen(QPen(color, max(0.25, diameter * 0.07)))
        painter.drawEllipse(symbol_rect)
    elif resolved == 4:
        painter.setPen(QPen(color, max(0.5, diameter * 0.16)))
        painter.drawEllipse(symbol_rect.adjusted(0.2, 0.2, -0.2, -0.2))
    elif resolved == 5:
        painter.setPen(QPen(color.darker(130), max(0.2, diameter * 0.05)))
        painter.setBrush(color)
        painter.drawEllipse(symbol_rect)
    else:
        painter.setPen(QPen(color, max(0.25, diameter * 0.07)))
        painter.drawEllipse(symbol_rect)
        painter.drawLine(symbol_rect.topLeft(), symbol_rect.bottomRight())
        painter.drawLine(symbol_rect.topRight(), symbol_rect.bottomLeft())
    painter.restore()


def _paint_lba_legend(
    painter: QPainter,
    rect: QRectF,
    properties: dict[str, object],
    language: AppLanguage,
) -> None:
    titles = {
        AppLanguage.RU: "ЛЮМИНЕСЦЕНТНО-БИТУМИНОЛОГИЧЕСКИЙ АНАЛИЗ (ЛБА)",
        AppLanguage.KK: "ЛЮМИНЕСЦЕНТТІ-БИТУМНОЛОГИЯЛЫҚ ТАЛДАУ (ЛБА)",
        AppLanguage.EN: "LUMINESCENT-BITUMEN ANALYSIS (LBA)",
    }
    type_titles = {
        AppLanguage.RU: "Тип битумоида",
        AppLanguage.KK: "Битумоид түрі",
        AppLanguage.EN: "Bitumen type",
    }
    intensity_titles = {
        AppLanguage.RU: "Интенсивность",
        AppLanguage.KK: "Қарқындылық",
        AppLanguage.EN: "Intensity",
    }
    raw_size = properties.get("font_size_mm", 2.4)
    font_size = (
        float(raw_size)
        if isinstance(raw_size, (int, float)) and not isinstance(raw_size, bool)
        else 2.4
    )
    color = _color(properties.get("color"), "#0f172a")
    title_height = min(5.0, max(2.5, rect.height() * 0.18))
    body = rect.adjusted(0.8, title_height + 0.4, -0.8, -0.6)
    left = QRectF(body.left(), body.top(), body.width() * 0.58, body.height())
    right = QRectF(left.right() + 0.5, body.top(), body.right() - left.right() - 0.5, body.height())

    painter.save()
    painter.setClipRect(rect)
    painter.setPen(QPen(QColor("#64748b"), 0.2))
    painter.drawRect(rect)
    title_font = QFont()
    title_font.setBold(True)
    _set_scaled_font_mm(painter, title_font, min(3.2, font_size + 0.5))
    painter.setFont(title_font)
    painter.setPen(color)
    painter.drawText(
        QRectF(rect.left() + 0.8, rect.top(), rect.width() - 1.6, title_height),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        titles[language],
    )

    body_font = QFont()
    _set_scaled_font_mm(painter, body_font, max(1.0, min(font_size, 8.0)))
    painter.setFont(body_font)
    heading_height = min(3.5, body.height() * 0.16)
    painter.drawText(
        QRectF(left.left(), left.top(), left.width(), heading_height),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        type_titles[language],
    )
    painter.drawText(
        QRectF(right.left(), right.top(), right.width(), heading_height),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        intensity_titles[language],
    )

    type_area = left.adjusted(0.0, heading_height, 0.0, 0.0)
    type_row_height = type_area.height() / len(LBA_TYPE_STYLES)
    for index, style in enumerate(LBA_TYPE_STYLES):
        row = QRectF(
            type_area.left(),
            type_area.top() + index * type_row_height,
            type_area.width(),
            type_row_height,
        )
        swatch = QRectF(
            row.left() + 0.4,
            row.top() + max(0.2, row.height() * 0.15),
            min(8.0, row.width() * 0.18),
            max(0.8, row.height() * 0.7),
        )
        painter.fillRect(swatch, QColor(style.color))
        painter.setPen(QPen(QColor("#475569"), 0.15))
        painter.drawRect(swatch)
        painter.setPen(color)
        painter.drawText(
            QRectF(swatch.right() + 1.0, row.top(), row.right() - swatch.right() - 1.0, row.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"{style.code} - {style.localized_name(language)}",
        )

    intensity_area = right.adjusted(0.0, heading_height, 0.0, 0.0)
    intensity_row_height = intensity_area.height() / 5.0
    for intensity in range(1, 6):
        row = QRectF(
            intensity_area.left(),
            intensity_area.top() + (intensity - 1) * intensity_row_height,
            intensity_area.width(),
            intensity_row_height,
        )
        symbol_diameter = min(row.height() * 0.72, 5.0)
        _paint_lba_intensity_symbol(
            painter,
            row.left() + symbol_diameter / 2.0 + 0.4,
            row.center().y(),
            symbol_diameter,
            QColor("#92400e"),
            intensity,
        )
        painter.setPen(color)
        painter.drawText(
            QRectF(
                row.left() + symbol_diameter + 1.2,
                row.top(),
                max(0.1, row.width() - symbol_diameter - 1.2),
                row.height(),
            ),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"{intensity} - {lba_intensity_name(intensity, language)}",
        )
    painter.restore()

def _paint_columns(
    painter: QPainter,
    template: MasterlogTemplate,
    size: QSizeF,
    session: ProjectSession,
    depth_range: tuple[float, float] | None,
    columns: Sequence[MasterlogColumnTemplate],
    language: AppLanguage,
    lithotype_catalog: dict[str, CatalogLithotype],
) -> None:
    x = 0.0
    top = template.header_height_mm
    header_height = column_heading_height(columns)
    dataset = session.current_dataset
    bindings = masterlog_curve_bindings(template, dataset) if dataset is not None else {}
    annotation_columns: list[tuple[MasterlogColumnTemplate, QRectF]] = []
    for column in columns:
        rect = QRectF(x, top, column.width_mm, size.height() - top)
        painter.setPen(QPen(QColor("#334155"), 0.25))
        painter.drawRect(rect)
        painter.drawLine(QLineF(x, top + header_height, x + column.width_mm, top + header_height))
        _paint_column_heading(
            painter,
            QRectF(x + 0.5, top + 0.25, column.width_mm - 1.0, header_height - 0.5),
            column,
            dataset,
            bindings,
        )
        plot_rect = QRectF(
            x + 0.5,
            top + header_height,
            max(0.1, column.width_mm - 1.0),
            max(0.1, size.height() - top - header_height),
        )
        if depth_range is not None and dataset is not None:
            _paint_column_grid(painter, plot_rect, column)
            if column.column_type == "depth":
                _paint_depth_axis(painter, plot_rect, depth_range)
            elif column.column_type == "stratigraphy":
                _paint_stratigraphy_column(painter, plot_rect, session, depth_range)
            elif column.column_type == "lithology":
                _paint_lithology_column(
                    painter, plot_rect, column, session, depth_range, lithotype_catalog
                )
            elif column.column_type == "cuttings":
                _paint_cuttings_column(
                    painter, plot_rect, column, session, depth_range, lithotype_catalog
                )
            elif column.column_type == "cuttings_description":
                _paint_cuttings_descriptions(painter, plot_rect, session, depth_range)
            elif column.column_type == "analysis_interpretation":
                _paint_sample_interpretations(painter, plot_rect, session, depth_range)
            elif column.column_type == "calcimetry":
                _paint_calcimetry_column(
                    painter, plot_rect, column, dataset, session, depth_range, bindings
                )
            elif column.column_type == "lba":
                _paint_lba_column(painter, plot_rect, session, depth_range)
            elif column.column_type in {"text", "description"}:
                _paint_lithology_descriptions(
                    painter,
                    plot_rect,
                    session,
                    depth_range,
                    language,
                    lithotype_catalog,
                )
            else:
                _paint_curve_column(painter, plot_rect, column, dataset, depth_range, bindings)
            _paint_depth_symbols(painter, plot_rect, template, column, session, depth_range)
            _paint_inspection_callouts(painter, plot_rect, template, column, session, depth_range)
            annotation_columns.append((column, plot_rect))
        x += column.width_mm
    if depth_range is not None and dataset is not None and annotation_columns:
        # User-authored annotations are one page-wide top layer. Drawing them
        # after all columns allows the same free cross-column placement seen on
        # the F4 canvas and prevents per-column duplication/clipping.
        _paint_annotations(
            painter, annotation_columns, session, depth_range, bindings
        )


def _paint_column_grid(
    painter: QPainter,
    rect: QRectF,
    column: MasterlogColumnTemplate,
) -> None:
    if not column.grid_x and not column.grid_y:
        return
    major_color = QColor("#64748b")
    major_color.setAlphaF(column.grid_alpha)
    minor_color = QColor("#94a3b8")
    minor_color.setAlphaF(column.grid_alpha * 0.45)
    lines = normalized_grid_lines(
        column.grid_major_divisions,
        column.grid_minor_divisions,
    )
    painter.save()
    painter.setClipRect(rect)

    def draw_axis(vertical: bool) -> None:
        for line in lines:
            position = (
                rect.left() + rect.width() * line.fraction
                if vertical
                else rect.top() + rect.height() * line.fraction
            )
            painter.setPen(
                QPen(
                    major_color if line.major else minor_color,
                    0.2 if line.major else 0.1,
                )
            )
            if vertical:
                painter.drawLine(QLineF(position, rect.top(), position, rect.bottom()))
            else:
                painter.drawLine(QLineF(rect.left(), position, rect.right(), position))

    if column.grid_x:
        draw_axis(True)
    if column.grid_y:
        draw_axis(False)
    painter.restore()


def _paint_column_heading(
    painter: QPainter,
    rect: QRectF,
    column: MasterlogColumnTemplate,
    dataset: Dataset | None,
    bindings: dict[str, str],
) -> None:
    title_font = QFont()
    _set_scaled_font_points(painter, title_font, 6.5)
    painter.setFont(title_font)
    painter.setPen(QColor("#0f172a"))
    orientation = str(column.properties.get("title_orientation", "horizontal"))
    position = str(column.properties.get("title_position", "center"))
    if not column.show_legend or not column.curve_mnemonics:
        draw_oriented_text(
            painter,
            rect,
            column.title,
            orientation=orientation,
            position=position,
            padding_x=0.5,
            padding_y=0.2,
        )
        return
    # A vertical title needs a taller title lane than a horizontal caption.
    # Keep the legend available, but reserve enough height for a readable
    # bottom-to-top/top-to-bottom heading in A4/A3 print layouts.
    title_height = (
        rect.height() * 0.62
        if orientation != "horizontal"
        else min(4.2, rect.height() * 0.38)
    )
    draw_oriented_text(
        painter,
        QRectF(rect.left() + 0.5, rect.top(), rect.width() - 1.0, title_height),
        column.title,
        orientation=orientation,
        position=position,
        padding_x=0.2,
        padding_y=0.1,
    )
    legend_rect = QRectF(
        rect.left() + 0.25,
        rect.top() + title_height,
        rect.width() - 0.5,
        max(0.1, rect.height() - title_height),
    )
    count = len(column.curve_mnemonics)
    rows = 2 if count > 4 else 1
    columns = (count + rows - 1) // rows
    cell_width = legend_rect.width() / max(1, columns)
    cell_height = legend_rect.height() / rows
    legend_font = QFont()
    _set_scaled_font_points(painter, legend_font, 4.6)
    painter.setFont(legend_font)
    for index, mnemonic in enumerate(column.curve_mnemonics):
        row, column_index = divmod(index, columns)
        cell = QRectF(
            legend_rect.left() + column_index * cell_width,
            legend_rect.top() + row * cell_height,
            cell_width,
            cell_height,
        )
        style = masterlog_curve_style(column, mnemonic, index)
        painter.setPen(_color(style.color, column.line_color))
        label = mnemonic
        value_range = curve_display_range(column, dataset, mnemonic, bindings)
        if value_range is not None:
            label += f" {value_range[0]:g}–{value_range[1]:g}"
        painter.drawText(
            cell.adjusted(0.2, 0.0, -0.2, 0.0),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            label,
        )


def _paint_inspection_callouts(
    painter: QPainter,
    rect: QRectF,
    template: MasterlogTemplate,
    column: MasterlogColumnTemplate,
    session: ProjectSession,
    depth_range: tuple[float, float],
) -> None:
    well = session.current_well
    if well is None:
        return
    top, bottom = depth_range
    painter.save()
    painter.setClipRect(rect)
    for item in well.canvas_objects:
        if (
            item.object_type != "masterlog_inspection"
            or item.track_id != column.column_id
            or item.properties.get("template_id") != template.template_id
            or item.top_depth is None
            or not top <= item.top_depth <= bottom
        ):
            continue
        y = rect.top() + (item.top_depth - top) / (bottom - top) * rect.height()
        painter.setPen(QPen(QColor("#dc2626"), 0.6))
        painter.drawLine(QLineF(rect.left(), y, rect.right(), y))
        if item.bottom_depth is not None:
            y_bottom = (
                rect.top() + (min(item.bottom_depth, bottom) - top) / (bottom - top) * rect.height()
            )
            painter.drawRect(QRectF(rect.left(), y, rect.width(), max(0.2, y_bottom - y)))
        text = item.properties.get("text")
        if not isinstance(text, str) or not text:
            continue
        font = QFont()
        _set_scaled_font_points(painter, font, 5.5)
        painter.setFont(font)
        text_height = min(18.0, max(6.0, 3.5 * len(text.splitlines())))
        text_rect = QRectF(
            rect.left() + 1.0,
            min(max(rect.top(), y + 0.5), rect.bottom() - text_height),
            rect.width() - 2.0,
            text_height,
        )
        painter.fillRect(text_rect, QColor(255, 255, 255, 225))
        painter.setPen(QPen(QColor("#dc2626"), 0.3))
        painter.drawRect(text_rect)
        painter.setPen(QColor("#7f1d1d"))
        painter.drawText(
            text_rect.adjusted(0.6, 0.3, -0.6, -0.3),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            text,
        )
    painter.restore()


def visible_lithology_intervals(
    intervals: Sequence[LithologyInterval], depth_range: tuple[float, float]
) -> tuple[LithologyInterval, ...]:
    top, bottom = depth_range
    return tuple(
        interval
        for interval in intervals
        if interval.bottom_depth >= top and interval.top_depth <= bottom
    )


def _interval_rect(
    rect: QRectF,
    interval: LithologyInterval,
    depth_range: tuple[float, float],
) -> QRectF:
    top, bottom = depth_range
    visible_top = max(top, interval.top_depth)
    visible_bottom = min(bottom, interval.bottom_depth)
    y_top = rect.top() + (visible_top - top) / (bottom - top) * rect.height()
    y_bottom = rect.top() + (visible_bottom - top) / (bottom - top) * rect.height()
    return QRectF(rect.left(), y_top, rect.width(), max(0.0, y_bottom - y_top))


def _paint_lithology_column(
    painter: QPainter,
    rect: QRectF,
    column: MasterlogColumnTemplate,
    session: ProjectSession,
    depth_range: tuple[float, float],
    lithotype_catalog: dict[str, CatalogLithotype],
) -> None:
    well = session.current_well
    if well is None:
        return
    painter.save()
    painter.setClipRect(rect)
    for interval in visible_lithology_intervals(well.lithology, depth_range):
        interval_rect = _interval_rect(rect, interval, depth_range)
        definition = lithotype_catalog.get(interval.lithotype_id)
        color = definition.color if definition is not None else "#b0b0b0"
        pattern = definition.pattern_key if definition is not None else "solid"
        painter.fillRect(interval_rect, masterlog_lithology_brush(painter, color, pattern))
        painter.setPen(QPen(QColor("#334155"), 0.2))
        painter.drawRect(interval_rect)
        if (
            interval_rect.height() >= 4.0
            and bool(column.properties.get("show_interval_labels", False))
        ):
            label = definition.code if definition is not None else interval.lithotype_id
            painter.setPen(QColor("#0f172a"))
            painter.drawText(
                interval_rect.adjusted(0.5, 0.25, -0.5, -0.25),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                label,
            )
    painter.restore()


def _paint_stratigraphy_label(
    painter: QPainter,
    interval_rect: QRectF,
    text: str,
    *,
    orientation: str,
    position: str,
) -> None:
    # Validate through the same presentation helpers used by the screen renderer.
    if not isfinite(stratigraphy_text_angle(orientation)):
        return
    if not 0.0 <= stratigraphy_text_position_fraction(position) <= 1.0:
        return
    draw_oriented_text(
        painter,
        interval_rect,
        text,
        orientation=orientation,
        position=position,
        horizontal_alignment=Qt.AlignmentFlag.AlignHCenter,
        word_wrap=True,
        padding_x=0.4,
        padding_y=0.2,
    )


def _paint_stratigraphy_column(
    painter: QPainter,
    rect: QRectF,
    session: ProjectSession,
    depth_range: tuple[float, float],
) -> None:
    well = session.current_well
    if well is None:
        return
    visible = [
        item
        for item in well.stratigraphy
        if item.bottom_depth >= depth_range[0] and item.top_depth <= depth_range[1]
    ]
    ranks = sorted({item.rank or "" for item in visible}, key=stratigraphy_rank_order)
    if not ranks:
        return
    lane_width = rect.width() / len(ranks)
    lanes = {rank: index for index, rank in enumerate(ranks)}
    top, bottom = depth_range
    painter.save()
    painter.setClipRect(rect)
    font = QFont()
    _set_scaled_font_points(painter, font, 5.5)
    painter.setFont(font)
    for interval in visible:
        lane = lanes[interval.rank or ""]
        y_top = rect.top() + (max(top, interval.top_depth) - top) / (bottom - top) * rect.height()
        y_bottom = (
            rect.top() + (min(bottom, interval.bottom_depth) - top) / (bottom - top) * rect.height()
        )
        interval_rect = QRectF(
            rect.left() + lane * lane_width,
            y_top,
            lane_width,
            max(0.2, y_bottom - y_top),
        )
        color = QColor(interval.color)
        if not color.isValid():
            color = QColor("#dbeafe")
        painter.fillRect(interval_rect, color)
        painter.setPen(QPen(QColor("#334155"), 0.2))
        painter.drawRect(interval_rect)
        if interval_rect.height() >= 3.0:
            text = "\n".join(value for value in (interval.code, interval.name) if value)
            painter.setPen(QColor("#0f172a"))
            _paint_stratigraphy_label(
                painter,
                interval_rect,
                text,
                orientation=interval.text_orientation,
                position=interval.text_position,
            )
    painter.restore()


def _paint_cuttings_column(
    painter: QPainter,
    rect: QRectF,
    column: MasterlogColumnTemplate,
    session: ProjectSession,
    depth_range: tuple[float, float],
    lithotype_catalog: dict[str, CatalogLithotype],
) -> None:
    well = session.current_well
    if well is None:
        return
    top, bottom = depth_range
    painter.save()
    painter.setClipRect(rect)
    for sample in well.cuttings:
        if sample.bottom_depth < top or sample.top_depth > bottom:
            continue
        visible_top = max(top, sample.top_depth)
        visible_bottom = min(bottom, sample.bottom_depth)
        y_top = rect.top() + (visible_top - top) / (bottom - top) * rect.height()
        y_bottom = rect.top() + (visible_bottom - top) / (bottom - top) * rect.height()
        x = rect.left()
        for component in sample.components:
            width = rect.width() * component.percentage / 100.0
            definition = lithotype_catalog.get(component.lithotype_id)
            color = definition.color if definition is not None else "#b0b0b0"
            pattern = definition.pattern_key if definition is not None else "solid"
            component_rect = QRectF(x, y_top, width, max(0.1, y_bottom - y_top))
            painter.fillRect(component_rect, masterlog_lithology_brush(painter, color, pattern))
            painter.setPen(QPen(QColor("#334155"), 0.2))
            painter.drawRect(component_rect)
            if (
                component_rect.width() >= 8
                and component_rect.height() >= 4
                and bool(column.properties.get("show_interval_labels", False))
            ):
                code = definition.code if definition is not None else component.lithotype_id
                painter.setPen(QColor("#0f172a"))
                painter.drawText(
                    component_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    f"{code} {component.percentage:g}%",
                )
            x += width
    painter.restore()


def _paint_calcimetry_column(
    painter: QPainter,
    rect: QRectF,
    column: MasterlogColumnTemplate,
    dataset: Dataset,
    session: ProjectSession,
    depth_range: tuple[float, float],
    bindings: dict[str, str],
) -> None:
    # Some providers store calcite/dolomite as LAS curves, while other jobs keep
    # them as discrete cuttings-sample analyses.  The masterlog supports both.
    if column.curve_mnemonics:
        _paint_curve_column(painter, rect, column, dataset, depth_range, bindings)
    well = session.current_well
    if well is None:
        return
    top, bottom = depth_range
    painter.save()
    painter.setClipRect(rect)
    for sample in well.cuttings:
        if sample.bottom_depth < top or sample.top_depth > bottom:
            continue
        if sample.calcite_percent is None and sample.dolomite_percent is None:
            continue
        y_top = rect.top() + (max(top, sample.top_depth) - top) / (bottom - top) * rect.height()
        y_bottom = (
            rect.top() + (min(bottom, sample.bottom_depth) - top) / (bottom - top) * rect.height()
        )
        height = max(0.2, y_bottom - y_top)
        calcite = sample.calcite_percent
        dolomite = sample.dolomite_percent
        residue = sample.insoluble_residue_percent
        left = rect.left()
        for value, color in (
            (calcite, "#22d3ee"),
            (dolomite, "#a78bfa"),
            (residue, "#d1d5db"),
        ):
            if value is None:
                continue
            numeric = min(100.0, max(0.0, float(value)))
            if numeric > 0.0:
                width = rect.width() * numeric / 100.0
                fill = QColor(color)
                fill.setAlpha(150)
                painter.fillRect(QRectF(left, y_top, width, height), fill)
                left += width
            else:
                painter.setPen(QPen(QColor(color), 0.7))
                painter.drawLine(QLineF(left, y_top, left, y_bottom))
        painter.setPen(QPen(QColor("#334155"), 0.2))
        painter.drawRect(QRectF(rect.left(), y_top, rect.width(), height))
        if height >= 5.0:
            painter.setPen(QColor("#0f172a"))
            parts: list[str] = []
            if calcite is not None:
                parts.append(f"Ca {calcite:g}%")
            if dolomite is not None:
                parts.append(f"Dol {dolomite:g}%")
            if residue is not None:
                parts.append(f"IR {residue:g}%")
            painter.drawText(
                QRectF(rect.left() + 0.5, y_top, rect.width() - 1.0, height),
                Qt.AlignmentFlag.AlignCenter,
                "  ".join(parts),
            )
    painter.restore()


def _paint_lba_column(
    painter: QPainter,
    rect: QRectF,
    session: ProjectSession,
    depth_range: tuple[float, float],
) -> None:
    well = session.current_well
    if well is None:
        return
    top, bottom = depth_range
    painter.save()
    painter.setClipRect(rect)
    font = QFont()
    _set_scaled_font_points(painter, font, 5.0)
    painter.setFont(font)
    for sample in well.cuttings:
        if sample.bottom_depth < top or sample.top_depth > bottom:
            continue
        intensity = normalized_lba_intensity(sample.lba_intensity)
        style = resolve_lba_type_style(sample.lba_type_id)
        has_lba = any(
            value not in (None, "")
            for value in (
                sample.lba_type_id,
                sample.lba_intensity,
                sample.lba_color,
                sample.lba_distribution,
                sample.lba_cut,
                sample.lba_description,
            )
        )
        if not has_lba:
            continue
        y_top = rect.top() + (max(top, sample.top_depth) - top) / (bottom - top) * rect.height()
        y_bottom = (
            rect.top() + (min(bottom, sample.bottom_depth) - top) / (bottom - top) * rect.height()
        )
        sample_rect = QRectF(rect.left(), y_top, rect.width(), max(0.2, y_bottom - y_top))
        painter.setPen(QPen(QColor("#cbd5e1"), 0.15))
        painter.drawRect(sample_rect)
        symbol_diameter = min(max(2.0, sample_rect.height() * 0.72), max(2.0, rect.width() * 0.42), 6.5)
        _paint_lba_intensity_symbol(
            painter,
            sample_rect.center().x(),
            sample_rect.center().y(),
            symbol_diameter,
            QColor(style.color),
            intensity,
        )
        if sample_rect.height() >= 4.0 and rect.width() >= 10.0:
            painter.setPen(QColor("#0f172a"))
            painter.drawText(
                QRectF(sample_rect.left() + 0.4, sample_rect.top(), sample_rect.width() * 0.34, sample_rect.height()),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                style.code,
            )
        if sample_rect.height() >= 5.5 and rect.width() >= 18.0:
            details = []
            if intensity is not None:
                details.append(str(intensity))
            if sample.lba_color:
                details.append(sample.lba_color)
            if sample.lba_description:
                details.append(sample.lba_description)
            if details:
                painter.setPen(QColor("#475569"))
                painter.drawText(
                    QRectF(
                        sample_rect.center().x() + symbol_diameter / 2.0 + 0.5,
                        sample_rect.top(),
                        max(0.2, sample_rect.right() - sample_rect.center().x() - symbol_diameter / 2.0 - 0.8),
                        sample_rect.height(),
                    ),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
                    " ".join(details),
                )
    painter.restore()


def _paint_lithology_descriptions(
    painter: QPainter,
    rect: QRectF,
    session: ProjectSession,
    depth_range: tuple[float, float],
    language: AppLanguage,
    lithotype_catalog: dict[str, CatalogLithotype],
) -> None:
    well = session.current_well
    if well is None:
        return
    painter.save()
    painter.setClipRect(rect)
    font = QFont()
    _set_scaled_font_points(painter, font, 6.5)
    painter.setFont(font)
    for interval in visible_lithology_intervals(well.lithology, depth_range):
        interval_rect = _interval_rect(rect, interval, depth_range)
        definition = lithotype_catalog.get(interval.lithotype_id)
        name = (
            _lithotype_name(definition, language)
            if definition is not None
            else interval.lithotype_id
        )
        description = interval.description.strip() if interval.description else name
        painter.setPen(QPen(QColor("#94a3b8"), 0.15))
        painter.drawRect(interval_rect)
        if interval_rect.height() >= 3.0:
            painter.setPen(QColor("#0f172a"))
            painter.drawText(
                interval_rect.adjusted(1.0, 0.5, -1.0, -0.5),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                description,
            )
    painter.restore()


def _paint_cuttings_descriptions(
    painter: QPainter,
    rect: QRectF,
    session: ProjectSession,
    depth_range: tuple[float, float],
) -> None:
    well = session.current_well
    if well is None:
        return
    top, bottom = depth_range
    painter.save()
    painter.setClipRect(rect)
    font = QFont()
    _set_scaled_font_points(painter, font, 6.5)
    painter.setFont(font)
    for sample in well.cuttings:
        if not sample.description or sample.bottom_depth < top or sample.top_depth > bottom:
            continue
        y_top = rect.top() + (max(top, sample.top_depth) - top) / (bottom - top) * rect.height()
        y_bottom = (
            rect.top() + (min(bottom, sample.bottom_depth) - top) / (bottom - top) * rect.height()
        )
        sample_rect = QRectF(rect.left(), y_top, rect.width(), max(0.2, y_bottom - y_top))
        painter.setPen(QPen(QColor("#94a3b8"), 0.15))
        painter.drawRect(sample_rect)
        if sample_rect.height() >= 3.0:
            painter.setPen(QColor("#0f172a"))
            painter.drawText(
                sample_rect.adjusted(0.6, 0.3, -0.6, -0.3),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                sample.description,
            )
    painter.restore()


def _paint_sample_interpretations(
    painter: QPainter,
    rect: QRectF,
    session: ProjectSession,
    depth_range: tuple[float, float],
) -> None:
    well = session.current_well
    if well is None:
        return
    top, bottom = depth_range
    painter.save()
    painter.setClipRect(rect)
    font = QFont()
    _set_scaled_font_points(painter, font, 6.0)
    painter.setFont(font)
    for sample in well.cuttings:
        text = sample.analysis_interpretation
        if not text or sample.bottom_depth < top or sample.top_depth > bottom:
            continue
        y_top = rect.top() + (max(top, sample.top_depth) - top) / (bottom - top) * rect.height()
        y_bottom = (
            rect.top() + (min(bottom, sample.bottom_depth) - top) / (bottom - top) * rect.height()
        )
        sample_rect = QRectF(rect.left(), y_top, rect.width(), max(0.2, y_bottom - y_top))
        painter.fillRect(sample_rect, QColor("#f8fafc"))
        painter.setPen(QPen(QColor("#64748b"), 0.15))
        painter.drawRect(sample_rect)
        if sample_rect.height() >= 3.0:
            painter.setPen(QColor("#0f172a"))
            painter.drawText(
                sample_rect.adjusted(0.5, 0.25, -0.5, -0.25),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                text,
            )
    painter.restore()


def _lithotype_name(definition: CatalogLithotype, language: AppLanguage) -> str:
    if language is AppLanguage.EN:
        return definition.name_en
    if language is AppLanguage.KK:
        return definition.name_kk or definition.name_ru
    return definition.name_ru



def _paint_annotations(
    painter: QPainter,
    column_rects: Sequence[tuple[MasterlogColumnTemplate, QRectF]],
    session: ProjectSession,
    depth_range: tuple[float, float],
    bindings: dict[str, str],
) -> None:
    """Paint one page-wide annotation layer after every Masterlog column."""

    well = session.current_well
    if well is None or not column_rects:
        return
    depth_top, depth_bottom = depth_range
    if depth_bottom <= depth_top:
        return

    owner_by_id = {column.column_id: (column, rect) for column, rect in column_rects}
    default_owner = next(
        (
            item
            for item in column_rects
            if item[0].column_type != "depth"
        ),
        column_rects[0],
    )
    full_rect = QRectF(column_rects[0][1])
    for _column, rect in column_rects[1:]:
        full_rect = full_rect.united(rect)

    px_to_mm = 25.4 / 96.0
    pen_styles = {
        "solid": Qt.PenStyle.SolidLine,
        "dash": Qt.PenStyle.DashLine,
        "dot": Qt.PenStyle.DotLine,
    }
    painter.save()
    painter.setClipRect(full_rect)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    active_scope_id = annotation_scope_id_for_session(session)
    for item in well.canvas_objects:
        if not is_annotation_object(item):
            continue
        record = annotation_from_canvas(item)
        if not annotation_matches_scope(record, active_scope_id):
            continue
        if not record.visible or not record.print_enabled:
            continue
        owner = owner_by_id.get(record.track_id or "", default_owner)
        column, rect = owner
        if record.depth is None or not isfinite(record.depth):
            continue
        depth = float(record.depth)
        if depth < depth_top or depth > depth_bottom:
            continue

        anchor_y = rect.top() + (depth - depth_top) / (depth_bottom - depth_top) * rect.height()
        anchor_x = rect.left() + rect.width() * min(1.0, max(0.0, record.x_fraction))
        if record.anchor is AnnotationAnchor.CURVE and record.parameter_mnemonic:
            curve_x = _parameter_symbol_x(
                rect,
                column,
                session.current_dataset,
                record.parameter_mnemonic,
                depth,
                bindings,
            )
            if curve_x is not None:
                anchor_x = curve_x

        width = min(full_rect.width(), max(10.0, record.width * px_to_mm))
        height = min(full_rect.height(), max(6.0, record.height * px_to_mm))
        left = anchor_x + record.offset_x * px_to_mm
        top_y = anchor_y + record.offset_y * px_to_mm
        # Keep a small part reachable/printable, while still permitting a box
        # to span several adjacent tracks.
        visible_margin = min(4.0, width, height)
        left = min(
            max(left, full_rect.left() - width + visible_margin),
            full_rect.right() - visible_margin,
        )
        top_y = min(
            max(top_y, full_rect.top() - height + visible_margin),
            full_rect.bottom() - visible_margin,
        )
        box = QRectF(left, top_y, width, height)
        style = record.style

        painter.save()
        if record.kind in {AnnotationKind.CALLOUT, AnnotationKind.VALUE}:
            endpoint = _closest_point_on_rect(box, QPointF(anchor_x, anchor_y))
            leader = QPen(
                _color(style.leader_color, "#2563eb"),
                max(0.1, style.leader_width * px_to_mm),
                pen_styles.get(style.leader_style, Qt.PenStyle.SolidLine),
            )
            leader.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(leader)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(QLineF(QPointF(anchor_x, anchor_y), endpoint))
            _paint_annotation_arrow(
                painter,
                QPointF(anchor_x, anchor_y),
                endpoint,
                style.arrow_style,
                _color(style.leader_color, "#2563eb"),
                max(1.4, 2.2 + style.leader_width * 0.55),
            )

        if style.rotation:
            painter.translate(box.center())
            painter.rotate(style.rotation)
            painter.translate(-box.center())
        radius = max(0.0, style.corner_radius * px_to_mm)
        if style.shadow:
            shadow = QColor("#0f172a")
            shadow.setAlpha(min(110, int(30 + style.shadow_blur * 5)))
            shadow_box = box.translated(
                style.shadow_offset_x * px_to_mm,
                style.shadow_offset_y * px_to_mm,
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shadow)
            painter.drawRoundedRect(shadow_box, radius, radius)

        fill = _color(style.fill_color, "#ffffff")
        fill.setAlphaF(min(1.0, max(0.0, style.fill_opacity)))
        border = QPen(
            _color(style.border_color, "#2563eb"),
            max(0.0, style.border_width * px_to_mm),
            pen_styles.get(style.border_style, Qt.PenStyle.SolidLine),
        )
        painter.setPen(border if style.border_width > 0 else Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(box, radius, radius)

        padding = max(0.0, style.padding * px_to_mm)
        content = box.adjusted(padding, padding, -padding, -padding)
        asset = session.image_assets.get(record.asset_ref) if record.asset_ref else None
        if record.kind in {AnnotationKind.IMAGE, AnnotationKind.SYMBOL} and asset is not None:
            caption_height = 0.0
            if record.text:
                caption_height = min(content.height() * 0.35, max(4.0, style.font_size * 0.45))
            image_rect = content.adjusted(0.0, 0.0, 0.0, -caption_height)
            draw_image_asset(painter, image_rect, asset)
            if caption_height > 0:
                caption = QRectF(
                    content.left(),
                    content.bottom() - caption_height,
                    content.width(),
                    caption_height,
                )
                _paint_annotation_text(painter, caption, record.text, style)
        else:
            _paint_annotation_text(painter, content, record.text, style)
        painter.restore()

    painter.restore()


def _paint_annotation_text(
    painter: QPainter,
    rect: QRectF,
    text: str,
    style: AnnotationStyle,
) -> None:
    font = QFont(style.font_family)
    _set_scaled_font_points(painter, font, style.font_size)
    font.setBold(style.bold)
    font.setItalic(style.italic)
    font.setUnderline(style.underline)
    painter.setFont(font)
    painter.setPen(_color(style.text_color, "#0f172a"))
    flags = Qt.TextFlag.TextWordWrap
    flags |= {
        "left": Qt.AlignmentFlag.AlignLeft,
        "center": Qt.AlignmentFlag.AlignHCenter,
        "right": Qt.AlignmentFlag.AlignRight,
    }.get(style.alignment, Qt.AlignmentFlag.AlignLeft)
    flags |= {
        "top": Qt.AlignmentFlag.AlignTop,
        "center": Qt.AlignmentFlag.AlignVCenter,
        "bottom": Qt.AlignmentFlag.AlignBottom,
    }.get(style.vertical_alignment, Qt.AlignmentFlag.AlignTop)
    painter.drawText(rect, int(flags), text)


def _closest_point_on_rect(rect: QRectF, point: QPointF) -> QPointF:
    x = min(max(point.x(), rect.left()), rect.right())
    y = min(max(point.y(), rect.top()), rect.bottom())
    if rect.contains(point):
        edges = (
            (abs(point.x() - rect.left()), QPointF(rect.left(), point.y())),
            (abs(point.x() - rect.right()), QPointF(rect.right(), point.y())),
            (abs(point.y() - rect.top()), QPointF(point.x(), rect.top())),
            (abs(point.y() - rect.bottom()), QPointF(point.x(), rect.bottom())),
        )
        return min(edges, key=lambda entry: entry[0])[1]
    return QPointF(x, y)


def _paint_annotation_arrow(
    painter: QPainter,
    anchor: QPointF,
    endpoint: QPointF,
    arrow_style: str,
    color: QColor,
    size: float,
) -> None:
    if arrow_style == "none":
        return
    vector = endpoint - anchor
    length = (vector.x() ** 2 + vector.y() ** 2) ** 0.5
    if length <= 1e-9:
        return
    ux, uy = vector.x() / length, vector.y() / length
    px, py = -uy, ux
    first = QPointF(
        anchor.x() + ux * size + px * size * 0.55,
        anchor.y() + uy * size + py * size * 0.55,
    )
    second = QPointF(
        anchor.x() + ux * size - px * size * 0.55,
        anchor.y() + uy * size - py * size * 0.55,
    )
    painter.save()
    painter.setPen(QPen(color, max(0.1, size * 0.12)))
    if arrow_style == "circle":
        painter.setBrush(color)
        painter.drawEllipse(anchor, size * 0.35, size * 0.35)
    elif arrow_style == "open":
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(QLineF(anchor, first))
        painter.drawLine(QLineF(anchor, second))
    else:
        painter.setBrush(color)
        path = QPainterPath(anchor)
        path.lineTo(first)
        path.lineTo(second)
        path.closeSubpath()
        painter.drawPath(path)
    painter.restore()

def _paint_depth_symbols(
    painter: QPainter,
    rect: QRectF,
    template: MasterlogTemplate,
    column: MasterlogColumnTemplate,
    session: ProjectSession,
    depth_range: tuple[float, float],
) -> None:
    well = session.current_well
    if well is None:
        return
    top, bottom = depth_range
    if bottom <= top:
        return
    painter.save()
    painter.setClipRect(rect)
    for item in well.canvas_objects:
        if (
            item.object_type != "masterlog_symbol"
            or item.anchor_type not in {"depth", "interval", "parameter", "time"}
            or item.track_id != column.column_id
            or item.properties.get("template_id") != template.template_id
        ):
            continue
        symbol_top = item.top_depth if item.top_depth is not None else item.y
        symbol_bottom = (
            item.bottom_depth
            if item.anchor_type == "interval" and item.bottom_depth is not None
            else symbol_top
        )
        if (
            not isinstance(symbol_top, (int, float))
            or isinstance(symbol_top, bool)
            or not isinstance(symbol_bottom, (int, float))
            or isinstance(symbol_bottom, bool)
            or not isfinite(float(symbol_top))
            or not isfinite(float(symbol_bottom))
            or float(symbol_bottom) < top
            or float(symbol_top) > bottom
            or float(symbol_bottom) < float(symbol_top)
        ):
            continue
        asset_ref = item.properties.get("asset_ref")
        asset = session.image_assets.get(asset_ref) if isinstance(asset_ref, str) else None
        if asset is None:
            continue
        if (
            not isinstance(item.width, (int, float))
            or isinstance(item.width, bool)
            or not isinstance(item.height, (int, float))
            or isinstance(item.height, bool)
            or not isfinite(float(item.width))
            or not isfinite(float(item.height))
        ):
            continue
        width = min(max(float(item.width), 1.0), rect.width())
        y_top = rect.top() + (max(float(symbol_top), top) - top) / (bottom - top) * rect.height()
        if item.anchor_type == "interval":
            y_bottom = (
                rect.top()
                + (min(float(symbol_bottom), bottom) - top) / (bottom - top) * rect.height()
            )
            height = max(y_bottom - y_top, 0.1)
            y = (y_top + y_bottom) / 2.0
        else:
            height = min(max(float(item.height), 1.0), rect.height())
            y = y_top
        center_x = rect.center().x()
        if item.anchor_type == "parameter":
            parameter_x = _parameter_symbol_x(
                rect,
                column,
                session.current_dataset,
                item.parameter_mnemonic,
                float(symbol_top),
            )
            if parameter_x is None:
                continue
            center_x = parameter_x
        offset_x = (
            float(item.x)
            if isinstance(item.x, (int, float)) and not isinstance(item.x, bool) and isfinite(float(item.x))
            else 0.0
        )
        raw_offset_y = item.properties.get("offset_y_mm", 0.0)
        offset_y = (
            float(raw_offset_y)
            if isinstance(raw_offset_y, (int, float))
            and not isinstance(raw_offset_y, bool)
            and isfinite(float(raw_offset_y))
            else 0.0
        )
        center_x += offset_x
        y += offset_y
        symbol_rect = QRectF(center_x - width / 2.0, y - height / 2.0, width, height)
        if not draw_image_asset(painter, symbol_rect, asset):
            continue
        label = item.properties.get("label")
        if isinstance(label, str) and label:
            painter.setPen(QColor("#0f172a"))
            font = QFont()
            _set_scaled_font_points(painter, font, 6.0)
            painter.setFont(font)
            painter.drawText(
                QRectF(symbol_rect.right() + 0.5, y - 2.5, rect.right() - symbol_rect.right(), 5.0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                label,
            )
    painter.restore()


def _paint_depth_axis(painter: QPainter, rect: QRectF, depth_range: tuple[float, float]) -> None:
    top, bottom = depth_range
    font = QFont()
    _set_scaled_font_points(painter, font, 6.5)
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


def masterlog_curve_bindings(template: MasterlogTemplate, dataset: Dataset) -> dict[str, str]:
    """Return explicit and safe automatic curve mappings for one Masterlog.

    A field LAS often uses vendor mnemonics such as ``S106`` or ``S202``.
    Saved user mappings always win; missing mappings are filled by the common
    semantic LAS resolver from mnemonic, description and unit evidence.
    Ambiguous parameters are intentionally left unresolved instead of choosing
    a random channel.
    """
    bindings: dict[str, str] = {}
    profiles = template.properties.get("dataset_curve_bindings", {})
    if isinstance(profiles, dict):
        raw = profiles.get(dataset.dataset_id, {})
        if isinstance(raw, dict):
            bindings.update(
                {
                    str(mnemonic): str(curve_id)
                    for mnemonic, curve_id in raw.items()
                    if isinstance(mnemonic, str)
                    and isinstance(curve_id, str)
                    and curve_id in dataset.curves
                }
            )

    targets = {
        mnemonic.strip().upper()
        for column in template.columns
        for mnemonic in column.curve_mnemonics
        if mnemonic.strip()
    }
    if targets:
        resolution = LasParameterResolver().resolve_dataset(
            dataset, targets=targets, minimum_confidence=0.65
        )
        for canonical, match in resolution.matches.items():
            bindings.setdefault(canonical, match.curve_id)
    return bindings


def _mapped_curve(dataset: Dataset, mnemonic: str, bindings: dict[str, str]) -> CurveData | None:
    curve_id = bindings.get(mnemonic)
    return (
        dataset.curves.get(curve_id)
        if curve_id is not None
        else dataset.curve_by_mnemonic(mnemonic)
    )


_MASTERLOG_CURVE_PALETTE = (
    "#2563eb",
    "#dc2626",
    "#16a34a",
    "#9333ea",
    "#ea580c",
    "#0891b2",
    "#be185d",
    "#4f46e5",
)


def masterlog_curve_style(
    column: MasterlogColumnTemplate,
    mnemonic: str,
    curve_index: int,
) -> MasterlogCurveStyle:
    saved = column.curve_styles.get(mnemonic)
    if saved is not None:
        return saved
    color = (
        column.line_color
        if curve_index == 0
        else _MASTERLOG_CURVE_PALETTE[curve_index % len(_MASTERLOG_CURVE_PALETTE)]
    )
    return MasterlogCurveStyle(color, column.line_width, column.line_style)


def curve_x_range(
    column: MasterlogColumnTemplate,
    dataset: Dataset,
    bindings: dict[str, str] | None = None,
) -> tuple[float, float] | None:
    if column.x_min is not None and column.x_max is not None:
        return float(column.x_min), float(column.x_max)
    chunks: list[np.ndarray] = []
    for mnemonic in column.curve_mnemonics:
        curve = _mapped_curve(dataset, mnemonic, bindings or {})
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


def curve_display_range(
    column: MasterlogColumnTemplate,
    dataset: Dataset | None,
    mnemonic: str,
    bindings: dict[str, str] | None = None,
) -> tuple[float, float] | None:
    style = column.curve_styles.get(mnemonic)
    if style is not None and style.x_min is not None and style.x_max is not None:
        return float(style.x_min), float(style.x_max)
    if dataset is None:
        if column.x_min is not None and column.x_max is not None:
            return float(column.x_min), float(column.x_max)
        return None
    return curve_x_range(column, dataset, bindings)


def _parameter_symbol_x(
    rect: QRectF,
    column: MasterlogColumnTemplate,
    dataset: Dataset | None,
    mnemonic: str | None,
    depth: float,
    bindings: dict[str, str] | None = None,
) -> float | None:
    if dataset is None or not mnemonic or mnemonic not in column.curve_mnemonics:
        return None
    curve = _mapped_curve(dataset, mnemonic, bindings or {})
    x_range = curve_display_range(column, dataset, mnemonic, bindings)
    if curve is None or x_range is None:
        return None
    depths = np.asarray(dataset.active_index.values, dtype=np.float64)
    values = np.asarray(curve.values, dtype=np.float64)
    if depths.shape != values.shape:
        return None
    valid = np.isfinite(depths) & np.isfinite(values)
    if column.x_scale == "logarithmic":
        valid &= values > 0
    if not np.any(valid):
        return None
    indexes = np.flatnonzero(valid)
    nearest = int(indexes[np.argmin(np.abs(depths[indexes] - depth))])
    value = float(values[nearest])
    minimum, maximum = x_range
    if column.x_scale == "logarithmic":
        if value <= 0 or minimum <= 0 or maximum <= 0:
            return None
        value, minimum, maximum = map(float, np.log10((value, minimum, maximum)))
    if maximum <= minimum:
        return None
    fraction = min(1.0, max(0.0, (value - minimum) / (maximum - minimum)))
    return rect.left() + rect.width() * fraction


def _paint_curve_column(
    painter: QPainter,
    rect: QRectF,
    column: MasterlogColumnTemplate,
    dataset: Dataset,
    depth_range: tuple[float, float],
    bindings: dict[str, str],
) -> None:
    """Paint curves without bridging LAS NULL intervals.

    Screen and printed output use the same gap-preserving sampler.  Numeric zero
    remains a real point on a linear track; missing values stay NaN and terminate
    the current QPainterPath segment.
    """
    depth = np.asarray(dataset.active_index.values, dtype=np.float64)
    top, bottom = depth_range
    styles = {
        "solid": Qt.PenStyle.SolidLine,
        "dash": Qt.PenStyle.DashLine,
        "dot": Qt.PenStyle.DotLine,
        "dash_dot": Qt.PenStyle.DashDotLine,
    }
    painter.save()
    painter.setClipRect(rect)
    for curve_index, mnemonic in enumerate(column.curve_mnemonics):
        curve = _mapped_curve(dataset, mnemonic, bindings)
        if curve is None:
            continue
        x_range = curve_display_range(column, dataset, mnemonic, bindings)
        if x_range is None:
            continue
        minimum, maximum = x_range
        logarithmic = column.x_scale == "logarithmic"
        if logarithmic:
            if minimum <= 0 or maximum <= 0:
                continue
            minimum, maximum = float(np.log10(minimum)), float(np.log10(maximum))
        source_values = np.asarray(curve.values, dtype=np.float64)
        if source_values.shape != depth.shape:
            continue
        values, sampled_depth = select_visible_samples(
            depth,
            source_values,
            top,
            bottom,
            max_points=5000,
            positive_values_only=logarithmic,
        )
        if not values.size:
            continue
        if logarithmic:
            transformed = np.full(values.shape, np.nan, dtype=np.float64)
            valid = np.isfinite(values) & (values > 0.0)
            transformed[valid] = np.log10(values[valid])
            values = transformed

        curve_style = masterlog_curve_style(column, mnemonic, curve_index)
        painter.setPen(
            QPen(
                _color(curve_style.color, column.line_color),
                curve_style.width,
                styles[curve_style.line_style],
            )
        )
        path = QPainterPath()
        drawing = False
        for value, depth_value in zip(values, sampled_depth, strict=True):
            if not np.isfinite(value) or not np.isfinite(depth_value):
                drawing = False
                continue
            x_fraction = min(1.0, max(0.0, (float(value) - minimum) / (maximum - minimum)))
            y_fraction = (float(depth_value) - top) / (bottom - top)
            point_x = rect.left() + rect.width() * x_fraction
            point_y = rect.top() + rect.height() * y_fraction
            if drawing:
                path.lineTo(point_x, point_y)
            else:
                path.moveTo(point_x, point_y)
                drawing = True
        painter.drawPath(path)
    painter.restore()


def _header_text(
    element: MasterlogHeaderElement,
    session: ProjectSession,
    template: MasterlogTemplate,
) -> str:
    if element.element_type == "text":
        value = element.properties.get("text")
        return str(value) if isinstance(value, (str, int, float)) else ""
    field = element.properties.get("field")
    if not isinstance(field, str):
        return "{field}"
    return resolve_header_field(session, field, template) or "{" + field + "}"


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
