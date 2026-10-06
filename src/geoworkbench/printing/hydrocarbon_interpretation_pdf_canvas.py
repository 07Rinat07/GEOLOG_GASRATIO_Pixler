from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPageLayout, QPainter

from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import (
    PAGE_FOOTER_HEIGHT,
)
from geoworkbench.domain.report_composition import ReportLayoutProfile
from geoworkbench.printing.report_visual_system import (
    REPORT_BRAND_WORDMARK,
    report_visual_profile,
)
from geoworkbench.printing.report_document_control import ReportDocumentControl, compact_report_footer
from geoworkbench.printing.unicode_support import print_font
from geoworkbench.services.localization import AppLanguage


class PageCanvas:
    def __init__(
        self,
        device: Any,
        painter: QPainter,
        language: AppLanguage,
        *,
        layout_profile: ReportLayoutProfile = ReportLayoutProfile.MODERN_OILFIELD,
        document_control: ReportDocumentControl | None = None,
    ) -> None:
        self.device = device
        self.painter = painter
        self.language = language
        self.visual = report_visual_profile(layout_profile)
        self.footer_details = compact_report_footer(document_control)
        self.footer_height = PAGE_FOOTER_HEIGHT + (14.0 if self.footer_details else 0.0)
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
            -self.footer_height,
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
            QColor(self.visual.palette.page),
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
        visual = self.visual
        footer_top = self.content_rect.bottom() + 2.0
        region = QRectF(self.page_rect.left(), footer_top, self.page_rect.width(), self.footer_height - 2.0)
        self.painter.save()
        try:
            self.painter.setClipRect(region, Qt.ClipOperation.IntersectClip)
            self.painter.setPen(QColor(visual.palette.text_muted))
            page_text = f"{label} {self.page_number}"
            page_font = self._footer_font(page_text)
            metrics = QFontMetricsF(page_font, self.painter.device())
            width = max(0.0, region.width() - 4.0)
            page_width = min(width * 0.4, metrics.horizontalAdvance(page_text) + 4.0)
            left_footer = QRectF(region.left() + 2.0, footer_top, max(0.0, width - page_width - 4.0), 12.0)
            right_footer = QRectF(region.right() - 2.0 - page_width, footer_top, page_width, 12.0)
            brand_font = self._footer_font(REPORT_BRAND_WORDMARK)
            brand_font.setBold(True)
            self._draw_footer_text(left_footer, REPORT_BRAND_WORDMARK, brand_font)
            self._draw_footer_text(right_footer, page_text, page_font, right=True)
            if self.footer_details:
                details_rect = QRectF(region.left() + 2.0, footer_top + 14.0, width, 12.0)
                self._draw_footer_text(details_rect, self.footer_details, self._footer_font(self.footer_details))
        finally:
            self.painter.restore()

    def _footer_font(self, text: str) -> QFont:
        font = print_font(self.visual.typography.footer_pt, text=text)
        # Canvas coordinates are points; the renderer scales the painter for DPI.
        # Compensate device font sizing to avoid applying that scale twice.
        font.setPointSizeF(self.visual.typography.footer_pt * 72.0 / self.device.logicalDpiY())
        font.setStyleStrategy(QFont.StyleStrategy.PreferDefault)
        return font

    def _draw_footer_text(self, rect: QRectF, text: str, font: QFont, *, right: bool = False) -> None:
        self.painter.setFont(font)
        metrics = QFontMetricsF(font, self.painter.device())
        compact = metrics.elidedText(text, Qt.TextElideMode.ElideRight, max(0.0, rect.width()))
        self.painter.drawText(
            rect,
            (Qt.AlignmentFlag.AlignRight if right else Qt.AlignmentFlag.AlignLeft) | Qt.AlignmentFlag.AlignVCenter,
            compact,
        )


__all__ = ["PageCanvas"]
