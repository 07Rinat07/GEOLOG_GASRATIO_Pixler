from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from PySide6.QtCore import QMarginsF, QSize, QSizeF
from PySide6.QtGui import QPageLayout, QPageSize


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

    def __post_init__(self) -> None:
        if not isinstance(self.fit_form_columns, bool):
            raise ValueError("Автоподбор ширины колонок должен быть логическим")
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
        roll_height = min(
            5000.0,
            max(25.0, self.custom_width_mm * height / width),
        )
        return QPageSize(
            QSizeF(self.custom_width_mm, roll_height),
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
        size = self.page_size_for_content(content_width, content_height).size(
            QPageSize.Unit.Millimeter
        )
        if (
            self.page_format is not PrintPageFormat.ROLL
            and self.orientation is PrintOrientation.LANDSCAPE
        ):
            return QSizeF(size.height(), size.width())
        return size

    def content_size_mm(self, content_width: int, content_height: int) -> QSizeF:
        page = self.oriented_page_size_mm(content_width, content_height)
        width = page.width() - self.margin_left_mm - self.margin_right_mm
        height = page.height() - self.margin_top_mm - self.margin_bottom_mm
        if width <= 0.0 or height <= 0.0:
            raise ValueError("Поля печати полностью перекрывают полезную область страницы")
        return QSizeF(width, height)

    def page_pixel_size(self, content_width: int, content_height: int, dpi: int) -> QSize:
        if isinstance(dpi, bool) or not isinstance(dpi, int) or not 72 <= dpi <= 600:
            raise ValueError("Разрешение печати должно быть от 72 до 600 DPI")
        page = self.oriented_page_size_mm(content_width, content_height)
        return QSize(
            max(1, round(page.width() / 25.4 * dpi)),
            max(1, round(page.height() / 25.4 * dpi)),
        )
