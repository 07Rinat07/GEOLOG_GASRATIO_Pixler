from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from PySide6.QtCore import QSizeF
from PySide6.QtGui import QPageLayout, QPageSize


class PrintPageFormat(StrEnum):
    A4 = "a4"
    A3 = "a3"
    CUSTOM = "custom"


class PrintOrientation(StrEnum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


@dataclass(frozen=True, slots=True)
class PrintPageSettings:
    page_format: PrintPageFormat = PrintPageFormat.A4
    orientation: PrintOrientation = PrintOrientation.PORTRAIT
    custom_width_mm: float = 210.0
    custom_height_mm: float = 297.0

    def __post_init__(self) -> None:
        for name, value in (
            ("ширина", self.custom_width_mm),
            ("высота", self.custom_height_mm),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"Пользовательская {name} страницы должна быть числом")
            if not isfinite(value) or not 25.0 <= value <= 5000.0:
                raise ValueError(
                    f"Пользовательская {name} страницы должна быть от 25 до 5000 мм"
                )

    @property
    def qt_page_size(self) -> QPageSize:
        if self.page_format is PrintPageFormat.CUSTOM:
            return QPageSize(
                QSizeF(self.custom_width_mm, self.custom_height_mm),
                QPageSize.Unit.Millimeter,
                "Custom",
            )
        page_id = (
            QPageSize.PageSizeId.A3
            if self.page_format is PrintPageFormat.A3
            else QPageSize.PageSizeId.A4
        )
        return QPageSize(page_id)

    @property
    def qt_orientation(self) -> QPageLayout.Orientation:
        if self.orientation is PrintOrientation.LANDSCAPE:
            return QPageLayout.Orientation.Landscape
        return QPageLayout.Orientation.Portrait
