from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from PySide6.QtCore import QMarginsF, QSize, QSizeF
from PySide6.QtGui import QPageLayout, QPageSize

from geoworkbench.printing.print_layout import (
    PrintMediaDimensions,
    PrintScaleMode,
    resolve_media_dimensions,
)


class PrintPageFormat(StrEnum):
    A0 = "a0"
    A1 = "a1"
    A2 = "a2"
    A3 = "a3"
    A4 = "a4"
    LETTER = "letter"
    LEGAL = "legal"
    CUSTOM = "custom"
    ROLL = "roll"


class PrintOrientation(StrEnum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


@dataclass(frozen=True, slots=True)
class PrintPageSettings:
    page_format: PrintPageFormat = PrintPageFormat.A4
    orientation: PrintOrientation = PrintOrientation.PORTRAIT
    custom_width_mm: float = 210.0
    custom_height_mm: float = 297.0
    fit_form_columns: bool = True
    margin_left_mm: float = 10.0
    margin_top_mm: float = 10.0
    margin_right_mm: float = 10.0
    margin_bottom_mm: float = 10.0
    scale_mode: PrintScaleMode = PrintScaleMode.FIT
    continuation_overlap_mm: float = 5.0

    def __post_init__(self) -> None:
        if not isinstance(self.fit_form_columns, bool):
            raise ValueError("Автоподбор ширины колонок должен быть логическим")
        if not isinstance(self.scale_mode, PrintScaleMode):
            raise ValueError("Режим масштаба печати должен использовать PrintScaleMode")
        for name, value in (
            ("ширина", self.custom_width_mm),
            ("высота", self.custom_height_mm),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"Пользовательская {name} страницы должна быть числом")
            if not isfinite(value) or not 25.0 <= value <= 5000.0:
                raise ValueError(f"Пользовательская {name} страницы должна быть от 25 до 5000 мм")
        for name, value in (
            ("левое поле", self.margin_left_mm),
            ("верхнее поле", self.margin_top_mm),
            ("правое поле", self.margin_right_mm),
            ("нижнее поле", self.margin_bottom_mm),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name.capitalize()} должно быть числом")
            if not isfinite(value) or not 0.0 <= value <= 100.0:
                raise ValueError(f"{name.capitalize()} должно быть от 0 до 100 мм")
        if (
            isinstance(self.continuation_overlap_mm, bool)
            or not isinstance(self.continuation_overlap_mm, (int, float))
            or not isfinite(self.continuation_overlap_mm)
            or not 0.0 <= self.continuation_overlap_mm <= 50.0
        ):
            raise ValueError("Перекрытие страниц продолжения должно быть от 0 до 50 мм")

    @property
    def effective_fit_form_columns(self) -> bool:
        return self.scale_mode is PrintScaleMode.FIT and self.fit_form_columns

    @property
    def margins_mm(self) -> tuple[float, float, float, float]:
        return (
            float(self.margin_left_mm),
            float(self.margin_top_mm),
            float(self.margin_right_mm),
            float(self.margin_bottom_mm),
        )

    def media_dimensions(self, content_width: int, content_height: int) -> PrintMediaDimensions:
        return resolve_media_dimensions(
            page_format=self.page_format.value,
            orientation=self.orientation.value,
            custom_width_mm=self.custom_width_mm,
            custom_height_mm=self.custom_height_mm,
            margins_mm=self.margins_mm,
            content_width_px=content_width,
            content_height_px=content_height,
            scale_mode=self.scale_mode,
        )

    @property
    def qt_page_size(self) -> QPageSize:
        if self.page_format in {PrintPageFormat.CUSTOM, PrintPageFormat.ROLL}:
            return QPageSize(
                QSizeF(self.custom_width_mm, self.custom_height_mm),
                QPageSize.Unit.Millimeter,
                "Custom",
            )
        page_ids = {
            PrintPageFormat.A0: QPageSize.PageSizeId.A0,
            PrintPageFormat.A1: QPageSize.PageSizeId.A1,
            PrintPageFormat.A2: QPageSize.PageSizeId.A2,
            PrintPageFormat.A3: QPageSize.PageSizeId.A3,
            PrintPageFormat.A4: QPageSize.PageSizeId.A4,
            PrintPageFormat.LETTER: QPageSize.PageSizeId.Letter,
            PrintPageFormat.LEGAL: QPageSize.PageSizeId.Legal,
        }
        return QPageSize(page_ids.get(self.page_format, QPageSize.PageSizeId.A4))

    def page_size_for_content(self, width: int, height: int) -> QPageSize:
        if width <= 0 or height <= 0:
            raise ValueError("Размер содержимого должен быть положительным")
        if self.page_format is not PrintPageFormat.ROLL:
            return self.qt_page_size
        media = self.media_dimensions(width, height)
        return QPageSize(
            QSizeF(media.width_mm, media.height_mm),
            QPageSize.Unit.Millimeter,
            "Roll",
        )

    @property
    def qt_orientation(self) -> QPageLayout.Orientation:
        if self.page_format is PrintPageFormat.ROLL:
            return QPageLayout.Orientation.Portrait
        if self.orientation is PrintOrientation.LANDSCAPE:
            return QPageLayout.Orientation.Landscape
        return QPageLayout.Orientation.Portrait

    @property
    def qt_margins(self) -> QMarginsF:
        return QMarginsF(
            self.margin_left_mm,
            self.margin_top_mm,
            self.margin_right_mm,
            self.margin_bottom_mm,
        )

    def oriented_page_size_mm(self, content_width: int, content_height: int) -> QSizeF:
        media = self.media_dimensions(content_width, content_height)
        return QSizeF(media.width_mm, media.height_mm)

    def content_size_mm(self, content_width: int, content_height: int) -> QSizeF:
        media = self.media_dimensions(content_width, content_height)
        return QSizeF(media.content_width_mm, media.content_height_mm)

    def page_pixel_size(self, content_width: int, content_height: int, dpi: int) -> QSize:
        if isinstance(dpi, bool) or not isinstance(dpi, int) or not 72 <= dpi <= 600:
            raise ValueError("Разрешение печати должно быть от 72 до 600 DPI")
        page = self.oriented_page_size_mm(content_width, content_height)
        return QSize(
            max(1, round(page.width() / 25.4 * dpi)),
            max(1, round(page.height() / 25.4 * dpi)),
        )
