from __future__ import annotations

from PySide6.QtCore import QLineF, QRectF, Qt
from PySide6.QtGui import QColor, QPen

from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.printing.unicode_support import print_font
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
)
from geoworkbench.services.localization import AppLanguage


_LABELS = {
    AppLanguage.RU: {
        "brand": "GEOLOG GASRATIO@Pixler",
        "title": "Отчёт по интерпретации газового каротажа",
        "subtitle": "Автоматизированный аналитический отчёт",
        "project": "Проект",
        "well": "Скважина",
        "dataset": "Набор данных",
        "created": "Сформирован",
        "primary": "Основная кривая",
        "threshold": "Порог robust z",
        "footer": (
            "Графики, методы, перспективные интервалы и ограничения методики "
            "приведены на следующих страницах."
        ),
    },
    AppLanguage.KK: {
        "brand": "GEOLOG GASRATIO@Pixler",
        "title": "Газ каротажын интерпретациялау есебі",
        "subtitle": "Автоматтандырылған талдамалық есеп",
        "project": "Жоба",
        "well": "Ұңғыма",
        "dataset": "Деректер жинағы",
        "created": "Құрылған",
        "primary": "Негізгі қисық",
        "threshold": "Robust z шегі",
        "footer": (
            "Графиктер, әдістер, перспективалы аралықтар және әдістеме "
            "шектеулері келесі беттерде берілген."
        ),
    },
    AppLanguage.EN: {
        "brand": "GEOLOG GASRATIO@Pixler",
        "title": "Mud-gas interpretation report",
        "subtitle": "Automated analytical report",
        "project": "Project",
        "well": "Well",
        "dataset": "Dataset",
        "created": "Generated",
        "primary": "Primary curve",
        "threshold": "Robust z threshold",
        "footer": (
            "Charts, methods, prospective intervals, and methodology limitations "
            "are presented on the following pages."
        ),
    },
}


def render_report_cover(
    canvas: PageCanvas,
    report: HydrocarbonInterpretationReport,
    language: AppLanguage,
) -> None:
    """Draw a balanced title page that works in portrait and landscape."""

    labels = _LABELS[language]
    painter = canvas.painter
    rect = canvas.content_rect
    compact = rect.width() < 620.0
    accent = QColor("#174f78")
    text_color = QColor("#172033")
    muted = QColor("#526579")
    card_fill = QColor("#f4f8fc")
    card_border = QColor("#9db1c5")

    painter.save()
    try:
        painter.fillRect(rect, QColor("#ffffff"))
        painter.fillRect(
            QRectF(rect.left(), rect.top(), rect.width(), 10.0),
            accent,
        )

        painter.setPen(accent)
        brand_font = print_font(9.0, text=labels["brand"])
        brand_font.setBold(True)
        painter.setFont(brand_font)
        painter.drawText(
            QRectF(rect.left() + 6.0, rect.top() + 21.0, rect.width() - 12.0, 20.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            labels["brand"],
        )

        title_top = rect.top() + (68.0 if compact else 52.0)
        title_height = 78.0 if compact else 62.0
        title_font = print_font(23.0 if compact else 23.5, text=labels["title"])
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(text_color)
        painter.drawText(
            QRectF(
                rect.left() + 28.0,
                title_top,
                rect.width() - 56.0,
                title_height,
            ),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            labels["title"],
        )

        subtitle_top = title_top + title_height + 4.0
        painter.setFont(print_font(10.0, text=labels["subtitle"]))
        painter.setPen(muted)
        painter.drawText(
            QRectF(rect.left(), subtitle_top, rect.width(), 22.0),
            Qt.AlignmentFlag.AlignCenter,
            labels["subtitle"],
        )

        card_width = min(rect.width() * (0.88 if compact else 0.72), 640.0)
        card_height = 270.0 if compact else 242.0
        card_left = rect.center().x() - card_width / 2.0
        card_top = subtitle_top + (43.0 if compact else 32.0)
        card = QRectF(card_left, card_top, card_width, card_height)
        painter.setBrush(card_fill)
        painter.setPen(QPen(card_border, 1.0))
        painter.drawRoundedRect(card, 8.0, 8.0)

        rows = (
            (labels["project"], report.project_name, 34.0),
            (labels["well"], report.well_name, 34.0),
            (labels["dataset"], report.dataset_name, 58.0 if compact else 42.0),
            (labels["created"], report.generated_at, 34.0),
            (labels["primary"], report.primary_mnemonic or "—", 34.0),
            (labels["threshold"], f"{report.threshold:.2f}", 34.0),
        )
        label_width = 138.0 if compact else 155.0
        row_left = card.left() + 20.0
        row_width = card.width() - 40.0
        row_top = card.top() + 13.0
        label_font = print_font(9.0, text=" ".join(label for label, _, _ in rows))
        label_font.setBold(True)
        value_font = print_font(9.0, text=" ".join(value for _, value, _ in rows))

        for index, (label, value, row_height) in enumerate(rows):
            if index:
                painter.setPen(QPen(QColor("#d6e0ea"), 0.8))
                painter.drawLine(
                    QLineF(row_left, row_top, row_left + row_width, row_top)
                )
            painter.setFont(label_font)
            painter.setPen(text_color)
            painter.drawText(
                QRectF(row_left, row_top + 4.0, label_width, row_height - 8.0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"{label}:",
            )
            painter.setFont(value_font)
            painter.setPen(QColor("#24384c"))
            painter.drawText(
                QRectF(
                    row_left + label_width,
                    row_top + 4.0,
                    row_width - label_width,
                    row_height - 8.0,
                ),
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignVCenter
                | Qt.TextFlag.TextWordWrap,
                value,
            )
            row_top += row_height

        footer_rect = QRectF(
            rect.left() + 35.0,
            max(card.bottom() + 22.0, rect.bottom() - 68.0),
            rect.width() - 70.0,
            38.0,
        )
        painter.setFont(print_font(8.5, text=labels["footer"]))
        painter.setPen(muted)
        painter.drawText(
            footer_rect,
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            labels["footer"],
        )
    finally:
        painter.restore()

    canvas.y = canvas.content_rect.bottom()


__all__ = ["render_report_cover"]
