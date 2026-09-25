from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPageLayout, QPainter

from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import (
    PAGE_FOOTER_HEIGHT,
)
from geoworkbench.printing.report_visual_system import (
    REPORT_BRAND_WORDMARK,
    modern_oilfield_report_profile,
)
from geoworkbench.printing.unicode_support import print_font
from geoworkbench.services.localization import AppLanguage


class PageCanvas:
    def __init__(self, device: Any, painter: QPainter, language: AppLanguage) -> None:
        self.device = device
        self.painter = painter
        self.language = language
        paint_rect = device.pageLayout().paintRect(QPageLayout.Unit.Point)
        # QPdfWriter and QPrinter already place the painter origin at the
        # printable area's top-left corner when full-page mode is disabled.
        # Reusing paint_rect.x()/y() would apply the margins a second time and
        # move the right and bottom edges outside the physical page.
        self.page_rect = QRectF(0.0, 0.0, paint_rect.width(), paint_rect.height())
        self.content_rect = self.page_rect.adjusted(
            0.0,
            0.0,
            0.0,
            -PAGE_FOOTER_HEIGHT,
        )
        self.page_number = 0
        self.y = self.content_rect.top()
        self.started = False

    @property
    def remaining_height(self) -> float:
        return max(0.0, self.content_rect.bottom() - self.y)

    @property
    def has_content(self) -> bool:
        return self.y > self.content_rect.top() + 0.5

    def new_page(self) -> None:
        if self.started and not self.device.newPage():
            raise RuntimeError("Не удалось создать следующую страницу печатного отчёта")
        self.started = True
        self.page_number += 1
        self.y = self.content_rect.top()
        self.painter.fillRect(
            self.page_rect,
            QColor(modern_oilfield_report_profile().palette.page),
        )
        self._draw_page_number()

    def reserve(self, height: float, *, force_new_page: bool = False) -> None:
        if not self.started:
            self.new_page()
        if force_new_page or (height > self.remaining_height and self.has_content):
            self.new_page()

    def advance(self, height: float, spacing: float = 5.0) -> None:
        self.y += height + spacing

    def _draw_page_number(self) -> None:
        label = {
            AppLanguage.RU: "Страница",
            AppLanguage.KK: "Бет",
            AppLanguage.EN: "Page",
        }[self.language]
        visual = modern_oilfield_report_profile()
        footer_top = self.content_rect.bottom() + 2.0
        footer_height = PAGE_FOOTER_HEIGHT - 2.0
        left_footer = QRectF(
            self.page_rect.left() + 2.0,
            footer_top,
            max(1.0, self.page_rect.width() * 0.62 - 4.0),
            footer_height,
        )
        right_footer = QRectF(
            self.page_rect.left() + self.page_rect.width() * 0.62,
            footer_top,
            max(1.0, self.page_rect.width() * 0.38 - 2.0),
            footer_height,
        )
        self.painter.setPen(QColor(visual.palette.text_muted))
        brand_font = print_font(
            visual.typography.footer_pt,
            text=REPORT_BRAND_WORDMARK,
        )
        brand_font.setBold(True)
        self.painter.setFont(brand_font)
        self.painter.drawText(
            left_footer,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            REPORT_BRAND_WORDMARK,
        )
        self.painter.setFont(
            print_font(
                visual.typography.footer_pt,
                text=f"{label} {self.page_number}",
            )
        )
        self.painter.drawText(
            right_footer,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"{label} {self.page_number}",
        )


__all__ = ["PageCanvas"]
