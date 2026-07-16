from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtGui import QPageLayout, QPageSize


class PrintPageFormat(StrEnum):
    A4 = "a4"
    A3 = "a3"


class PrintOrientation(StrEnum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


@dataclass(frozen=True, slots=True)
class PrintPageSettings:
    page_format: PrintPageFormat = PrintPageFormat.A4
    orientation: PrintOrientation = PrintOrientation.PORTRAIT

    @property
    def qt_page_size(self) -> QPageSize:
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
