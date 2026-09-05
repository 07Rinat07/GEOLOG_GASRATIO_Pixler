from __future__ import annotations

from PySide6.QtCore import QLineF, QRectF, Qt
from PySide6.QtGui import QColor, QPen

from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
    InterpretationReportIdentity,
    default_interpretation_report_identity,
)
from geoworkbench.printing.unicode_support import print_font
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
)
from geoworkbench.services.localization import AppLanguage


_LABELS = {
    AppLanguage.RU: {
        "brand": "GEOLOG GASRATIO@Pixler",
        "project": "Проект",
        "well": "Скважина",
        "field": "Месторождение / площадь",
        "location": "Местоположение",
        "operator": "Оператор / заказчик",
        "contractor": "Сервисная компания",
        "rig": "Буровая / установка",
        "dataset": "Набор данных",
        "interval": "Интервал отчёта",
        "created": "Сформирован",
        "primary": "Основная кривая",
        "threshold": "Порог robust z",
        "document": "Документ",
        "revision": "Ревизия",
        "status": "Статус",
        "date": "Дата отчёта",
        "prepared": "Подготовил",
        "checked": "Проверил",
        "approved": "Утвердил",
        "signature": "Подпись / дата",
        "footer": "Графики, методы и перспективные интервалы приведены на следующих страницах.",
    },
    AppLanguage.KK: {
        "brand": "GEOLOG GASRATIO@Pixler",
        "project": "Жоба",
        "well": "Ұңғыма",
        "field": "Кен орны / алаң",
        "location": "Орналасуы",
        "operator": "Оператор / тапсырыс беруші",
        "contractor": "Сервистік компания",
        "rig": "Бұрғылау қондырғысы",
        "dataset": "Деректер жинағы",
        "interval": "Есеп аралығы",
        "created": "Құрылған",
        "primary": "Негізгі қисық",
        "threshold": "Robust z шегі",
        "document": "Құжат",
        "revision": "Ревизия",
        "status": "Күйі",
        "date": "Есеп күні",
        "prepared": "Дайындаған",
        "checked": "Тексерген",
        "approved": "Бекіткен",
        "signature": "Қолы / күні",
        "footer": "Графиктер, әдістер және перспективалы аралықтар келесі беттерде берілген.",
    },
    AppLanguage.EN: {
        "brand": "GEOLOG GASRATIO@Pixler",
        "project": "Project",
        "well": "Well",
        "field": "Field / area",
        "location": "Location",
        "operator": "Operator / client",
        "contractor": "Service company",
        "rig": "Rig / unit",
        "dataset": "Dataset",
        "interval": "Report interval",
        "created": "Generated",
        "primary": "Primary curve",
        "threshold": "Robust z threshold",
        "document": "Document",
        "revision": "Revision",
        "status": "Status",
        "date": "Report date",
        "prepared": "Prepared by",
        "checked": "Checked by",
        "approved": "Approved by",
        "signature": "Signature / date",
        "footer": "Charts, methods, and prospective intervals are presented on the following pages.",
    },
}


def _value(text: str) -> str:
    return text.strip() or "—"


def render_report_cover(
    canvas: PageCanvas,
    report: HydrocarbonInterpretationReport,
    language: AppLanguage,
    identity: InterpretationReportIdentity | None = None,
) -> None:
    """Draw an industry-style document cover in portrait or landscape."""

    labels = _LABELS[language]
    details = (
        identity
        or default_interpretation_report_identity(report, language)
    ).cleaned()
    painter = canvas.painter
    rect = canvas.content_rect
    compact = rect.width() < 620.0
    short_page = rect.height() < 600.0
    accent = QColor("#174f78")
    accent_dark = QColor("#113b59")
    text_color = QColor("#172033")
    value_color = QColor("#24384c")
    muted = QColor("#526579")
    card_fill = QColor("#f4f8fc")
    card_border = QColor("#9db1c5")
    line_color = QColor("#d6e0ea")

    painter.save()
    try:
        painter.fillRect(rect, QColor("#ffffff"))
        painter.fillRect(
            QRectF(rect.left(), rect.top(), rect.width(), 10.0),
            accent,
        )

        brand_top = rect.top() + (15.0 if short_page else 17.0)
        brand_width = rect.width() * (0.38 if compact else 0.34)
        brand_font = print_font(8.6 if short_page else 9.0, text=labels["brand"])
        brand_font.setBold(True)
        painter.setFont(brand_font)
        painter.setPen(accent)
        painter.drawText(
            QRectF(rect.left() + 6.0, brand_top, brand_width, 22.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            labels["brand"],
        )

        control_top = rect.top() + (42.0 if compact else 14.0)
        control_width = (
            rect.width() - 12.0
            if compact
            else min(360.0, rect.width() * 0.52)
        )
        control_height = 52.0 if short_page else 58.0
        control_left = (
            rect.left() + 6.0
            if compact
            else rect.right() - control_width - 6.0
        )
        control = QRectF(control_left, control_top, control_width, control_height)
        painter.setBrush(card_fill)
        painter.setPen(QPen(card_border, 0.9))
        painter.drawRoundedRect(control, 5.0, 5.0)

        control_items = (
            (labels["document"], _value(details.document_number)),
            (labels["revision"], _value(details.revision)),
            (labels["status"], _value(details.document_status)),
            (labels["date"], _value(details.report_date)),
        )
        column_width = control.width() / 4.0
        for index, (label, value) in enumerate(control_items):
            cell = QRectF(
                control.left() + index * column_width,
                control.top(),
                column_width,
                control.height(),
            )
            if index:
                painter.setPen(QPen(card_border, 0.7))
                painter.drawLine(
                    QLineF(cell.left(), cell.top(), cell.left(), cell.bottom())
                )
            label_font = print_font(
                6.4 if short_page else (6.8 if compact else 7.2),
                text=label,
            )
            label_font.setBold(True)
            painter.setFont(label_font)
            painter.setPen(muted)
            painter.drawText(
                QRectF(
                    cell.left() + 5.0,
                    cell.top() + 4.0,
                    cell.width() - 10.0,
                    15.0,
                ),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                label,
            )
            value_font = print_font(
                7.3 if short_page else (7.6 if compact else 8.0),
                text=value,
            )
            value_font.setBold(True)
            painter.setFont(value_font)
            painter.setPen(text_color)
            painter.drawText(
                QRectF(
                    cell.left() + 5.0,
                    cell.top() + 20.0,
                    cell.width() - 10.0,
                    control.height() - 23.0,
                ),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                value,
            )

        title_gap = 8.0 if short_page else (15.0 if compact else 20.0)
        title_top = control.bottom() + title_gap
        title_height = 42.0 if short_page else (66.0 if compact else 54.0)
        title_size = 20.5 if short_page else (22.0 if compact else 23.5)
        title_font = print_font(title_size, text=details.report_title)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(text_color)
        painter.drawText(
            QRectF(
                rect.left() + 24.0,
                title_top,
                rect.width() - 48.0,
                title_height,
            ),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            _value(details.report_title),
        )

        subtitle_top = title_top + title_height + 2.0
        subtitle_height = 18.0 if short_page else 24.0
        painter.setFont(
            print_font(8.5 if short_page else 9.5, text=details.report_subtitle)
        )
        painter.setPen(muted)
        painter.drawText(
            QRectF(
                rect.left() + 24.0,
                subtitle_top,
                rect.width() - 48.0,
                subtitle_height,
            ),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            _value(details.report_subtitle),
        )

        rows = (
            (labels["project"], details.project_name),
            (labels["well"], details.well_name),
            (labels["field"], details.field_name),
            (labels["location"], details.location),
            (labels["operator"], details.operator_name),
            (labels["contractor"], details.contractor_name),
            (labels["rig"], details.rig_name),
            (labels["dataset"], details.dataset_name),
            (labels["interval"], details.interval),
            (labels["created"], report.generated_at),
            (labels["primary"], report.primary_mnemonic or "—"),
            (labels["threshold"], f"{report.threshold:.2f}"),
        )
        card_top = subtitle_top + subtitle_height + (16.0 if short_page else 10.0)
        card_width = rect.width() * (0.94 if compact else 0.90)
        card_left = rect.center().x() - card_width / 2.0
        card_height = 178.0 if short_page else (326.0 if compact else 224.0)
        card = QRectF(card_left, card_top, card_width, card_height)
        painter.setBrush(card_fill)
        painter.setPen(QPen(card_border, 1.0))
        painter.drawRoundedRect(card, 7.0, 7.0)

        if compact:
            _draw_compact_rows(
                painter,
                card,
                rows,
                text_color=text_color,
                value_color=value_color,
                line_color=line_color,
                font_size=7.8,
            )
        else:
            _draw_wide_rows(
                painter,
                card,
                rows,
                text_color=text_color,
                value_color=value_color,
                line_color=line_color,
                card_border=card_border,
                font_size=7.1 if short_page else 7.8,
            )

        approval_top = card.bottom() + (9.0 if short_page else 14.0)
        approval_height = 60.0 if short_page else (83.0 if compact else 72.0)
        approval = QRectF(card.left(), approval_top, card.width(), approval_height)
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QPen(card_border, 1.0))
        painter.drawRoundedRect(approval, 5.0, 5.0)
        approval_items = (
            (labels["prepared"], details.prepared_by),
            (labels["checked"], details.checked_by),
            (labels["approved"], details.approved_by),
        )
        approval_column = approval.width() / 3.0
        for index, (label, value) in enumerate(approval_items):
            cell = QRectF(
                approval.left() + index * approval_column,
                approval.top(),
                approval_column,
                approval.height(),
            )
            if index:
                painter.setPen(QPen(card_border, 0.8))
                painter.drawLine(
                    QLineF(cell.left(), cell.top(), cell.left(), cell.bottom())
                )
            label_font = print_font(7.1 if short_page else 8.0, text=label)
            label_font.setBold(True)
            painter.setFont(label_font)
            painter.setPen(accent_dark)
            painter.drawText(
                QRectF(
                    cell.left() + 7.0,
                    cell.top() + (5.0 if short_page else 7.0),
                    cell.width() - 14.0,
                    15.0 if short_page else 17.0,
                ),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                label,
            )
            painter.setFont(
                print_font(7.3 if short_page else 8.2, text=value)
            )
            painter.setPen(value_color)
            painter.drawText(
                QRectF(
                    cell.left() + 7.0,
                    cell.top() + (20.0 if short_page else 26.0),
                    cell.width() - 14.0,
                    18.0 if short_page else 24.0,
                ),
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignVCenter
                | Qt.TextFlag.TextWordWrap,
                _value(value),
            )
            painter.setPen(QPen(line_color, 0.8))
            signature_y = cell.bottom() - (16.0 if short_page else 19.0)
            painter.drawLine(
                QLineF(
                    cell.left() + 7.0,
                    signature_y,
                    cell.right() - 7.0,
                    signature_y,
                )
            )
            painter.setFont(
                print_font(6.1 if short_page else 6.7, text=labels["signature"])
            )
            painter.setPen(muted)
            painter.drawText(
                QRectF(
                    cell.left() + 7.0,
                    signature_y + 1.0,
                    cell.width() - 14.0,
                    12.0,
                ),
                Qt.AlignmentFlag.AlignCenter,
                labels["signature"],
            )

        footer_top = approval.bottom() + (7.0 if short_page else 11.0)
        footer_height = max(24.0, rect.bottom() - footer_top - 4.0)
        footer = QRectF(
            rect.left() + 24.0,
            footer_top,
            rect.width() - 48.0,
            footer_height,
        )
        footer_parts = [
            part
            for part in (
                details.confidentiality,
                details.remarks,
                labels["footer"],
            )
            if part.strip()
        ]
        painter.setFont(
            print_font(
                7.1 if short_page else (7.6 if compact else 8.0),
                text=" ".join(footer_parts),
            )
        )
        painter.setPen(muted)
        painter.drawText(
            footer,
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            "\n".join(footer_parts),
        )
    finally:
        painter.restore()

    canvas.y = canvas.content_rect.bottom()


def _draw_compact_rows(
    painter,
    card: QRectF,
    rows: tuple[tuple[str, str], ...],
    *,
    text_color: QColor,
    value_color: QColor,
    line_color: QColor,
    font_size: float,
) -> None:
    label_width = min(142.0, card.width() * 0.34)
    row_left = card.left() + 14.0
    row_width = card.width() - 28.0
    row_height = (card.height() - 18.0) / len(rows)
    label_font = print_font(font_size, text=" ".join(label for label, _ in rows))
    label_font.setBold(True)
    value_font = print_font(
        font_size,
        text=" ".join(_value(value) for _, value in rows),
    )
    row_top = card.top() + 9.0
    for index, (label, value) in enumerate(rows):
        if index:
            painter.setPen(QPen(line_color, 0.7))
            painter.drawLine(
                QLineF(row_left, row_top, row_left + row_width, row_top)
            )
        painter.setFont(label_font)
        painter.setPen(text_color)
        painter.drawText(
            QRectF(row_left, row_top + 2.0, label_width, row_height - 4.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"{label}:",
        )
        painter.setFont(value_font)
        painter.setPen(value_color)
        painter.drawText(
            QRectF(
                row_left + label_width,
                row_top + 2.0,
                row_width - label_width,
                row_height - 4.0,
            ),
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
            | Qt.TextFlag.TextWordWrap,
            _value(value),
        )
        row_top += row_height


def _draw_wide_rows(
    painter,
    card: QRectF,
    rows: tuple[tuple[str, str], ...],
    *,
    text_color: QColor,
    value_color: QColor,
    line_color: QColor,
    card_border: QColor,
    font_size: float,
) -> None:
    pair_count = len(rows) // 2
    pair_height = (card.height() - 16.0) / pair_count
    inner = QRectF(
        card.left() + 12.0,
        card.top() + 8.0,
        card.width() - 24.0,
        card.height() - 16.0,
    )
    column_width = inner.width() / 2.0
    painter.setPen(QPen(card_border, 0.8))
    painter.drawLine(
        QLineF(
            inner.center().x(),
            inner.top(),
            inner.center().x(),
            inner.bottom(),
        )
    )
    label_font = print_font(font_size, text=" ".join(label for label, _ in rows))
    label_font.setBold(True)
    value_font = print_font(
        font_size,
        text=" ".join(_value(value) for _, value in rows),
    )
    for pair_index in range(pair_count):
        row_top = inner.top() + pair_index * pair_height
        if pair_index:
            painter.setPen(QPen(line_color, 0.7))
            painter.drawLine(QLineF(inner.left(), row_top, inner.right(), row_top))
        for column_index in range(2):
            label, value = rows[pair_index * 2 + column_index]
            cell_left = inner.left() + column_index * column_width
            label_width = column_width * 0.37
            painter.setFont(label_font)
            painter.setPen(text_color)
            painter.drawText(
                QRectF(
                    cell_left + 7.0,
                    row_top + 3.0,
                    label_width - 9.0,
                    pair_height - 6.0,
                ),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"{label}:",
            )
            painter.setFont(value_font)
            painter.setPen(value_color)
            painter.drawText(
                QRectF(
                    cell_left + label_width,
                    row_top + 3.0,
                    column_width - label_width - 7.0,
                    pair_height - 6.0,
                ),
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignVCenter
                | Qt.TextFlag.TextWordWrap,
                _value(value),
            )


__all__ = ["render_report_cover"]
