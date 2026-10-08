from __future__ import annotations

from PySide6.QtCore import QLineF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.printing.interpretation_cover_text_layout import cover_text_layout, paint_cover_text
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
    InterpretationReportIdentity,
)
from geoworkbench.printing.report_visual_system import (
    REPORT_BRAND_WORDMARK,
    modern_oilfield_report_profile,
)
from geoworkbench.printing.report_painter_fonts import point_coordinate_font
from geoworkbench.printing.report_document_control import report_document_control, resolved_report_identity
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
)
from geoworkbench.services.localization import AppLanguage


_LABELS = {
    AppLanguage.RU: {
        "brand": REPORT_BRAND_WORDMARK,
        "project": "Проект",
        "well": "Скважина",
        "field": "Месторождение / площадь",
        "location": "Местоположение",
        "operator": "Оператор / заказчик",
        "contractor": "Сервисная компания",
        "rig": "Буровая / установка",
        "dataset": "Набор данных",
        "interval": "Интервал отчёта",
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
        "brand": REPORT_BRAND_WORDMARK,
        "project": "Жоба",
        "well": "Ұңғыма",
        "field": "Кен орны / алаң",
        "location": "Орналасуы",
        "operator": "Оператор / тапсырыс беруші",
        "contractor": "Сервистік компания",
        "rig": "Бұрғылау қондырғысы",
        "dataset": "Деректер жинағы",
        "interval": "Есеп аралығы",
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
        "brand": REPORT_BRAND_WORDMARK,
        "project": "Project",
        "well": "Well",
        "field": "Field / area",
        "location": "Location",
        "operator": "Operator / client",
        "contractor": "Service company",
        "rig": "Rig / unit",
        "dataset": "Dataset",
        "interval": "Report interval",
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
    details = resolved_report_identity(report, identity, language)
    document_control = report_document_control(details, language)
    painter = canvas.painter
    rect = canvas.content_rect
    compact = rect.width() < 620.0
    short_page = rect.height() < 600.0
    visual = modern_oilfield_report_profile()
    palette = visual.palette
    typography = visual.typography
    accent = QColor(palette.accent)
    accent_dark = QColor(palette.accent_dark)
    text_color = QColor(palette.text)
    value_color = QColor(palette.text_secondary)
    muted = QColor(palette.text_muted)
    card_fill = QColor(palette.accent_soft)
    card_border = QColor(palette.border)
    line_color = QColor(palette.border)

    painter.save()
    try:
        painter.fillRect(rect, QColor(palette.page))
        painter.fillRect(
            QRectF(
                rect.left(),
                rect.top(),
                rect.width(),
                visual.layout.accent_bar_height_pt,
            ),
            accent,
        )

        brand_top = rect.top() + (15.0 if short_page else 17.0)
        brand_width = rect.width() * (0.38 if compact else 0.34)
        brand_font = point_coordinate_font(
            typography.caption_pt,
            text=labels["brand"],
            paint_device=painter.device(),
        )
        brand_font.setBold(True)
        painter.setFont(brand_font)
        painter.setPen(accent)
        paint_cover_text(painter,
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
        control_items = document_control.control
        control_cell_width = control_width / len(control_items) - 10.0
        control_label_height = max(15.0, *(
            _wrapped_height(painter, point_coordinate_font(
                typography.caption_pt, text=label, paint_device=painter.device(), bold=True,
            ), label, control_cell_width) for label, _ in control_items
        ))
        control_value_top = control_label_height + 5.0
        control_height = max(control_height, control_value_top + 3.0 + max(
            _wrapped_height(painter, point_coordinate_font(
                typography.body_pt, text=value, paint_device=painter.device(), bold=True,
            ), value, control_cell_width) for _, value in control_items
        ))
        control_left = (
            rect.left() + 6.0
            if compact
            else rect.right() - control_width - 6.0
        )
        control = QRectF(control_left, control_top, control_width, control_height)
        painter.setBrush(card_fill)
        painter.setPen(QPen(card_border, 0.9))
        painter.drawRoundedRect(control, 5.0, 5.0)

        column_width = control.width() / float(len(control_items))
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
            label_font = point_coordinate_font(
                typography.caption_pt,
                text=label,
                paint_device=painter.device(),
            )
            label_font.setBold(True)
            painter.setFont(label_font)
            painter.setPen(muted)
            paint_cover_text(painter,
                QRectF(
                    cell.left() + 5.0,
                    cell.top() + 4.0,
                    cell.width() - 10.0,
                    control_label_height,
                ),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                label,
            )
            value_font = point_coordinate_font(
                typography.body_pt,
                text=value,
                paint_device=painter.device(),
            )
            value_font.setBold(True)
            painter.setFont(value_font)
            painter.setPen(text_color)
            paint_cover_text(painter,
                QRectF(
                    cell.left() + 5.0,
                    cell.top() + control_value_top,
                    cell.width() - 10.0,
                    control.height() - control_value_top - 3.0,
                ),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                value,
            )

        title_gap = 8.0 if short_page else (15.0 if compact else 20.0)
        title_top = control.bottom() + title_gap
        title_height = 42.0 if short_page else (66.0 if compact else 54.0)
        title_size = typography.title_pt
        title_font = point_coordinate_font(
            title_size,
            text=details.report_title,
            paint_device=painter.device(),
        )
        title_font.setBold(True)
        title_height = max(title_height, _wrapped_height(
            painter, title_font, _value(details.report_title), rect.width() - 48.0,
        ))
        painter.setFont(title_font)
        painter.setPen(text_color)
        paint_cover_text(painter,
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
        subtitle_font = point_coordinate_font(
            typography.subtitle_pt,
            text=details.report_subtitle,
            paint_device=painter.device(),
        )
        subtitle_height = max(subtitle_height, _wrapped_height(
            painter, subtitle_font, _value(details.report_subtitle), rect.width() - 48.0,
        ))
        painter.setFont(subtitle_font)
        painter.setPen(muted)
        paint_cover_text(painter,
            QRectF(
                rect.left() + 24.0,
                subtitle_top,
                rect.width() - 48.0,
                subtitle_height,
            ),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            _value(details.report_subtitle),
        )

        rows = document_control.context + (
            (labels["primary"], report.primary_mnemonic or "—"),
            (labels["threshold"], f"{report.threshold:.2f}"),
        )
        card_top = subtitle_top + subtitle_height + (16.0 if short_page else 10.0)
        card_width = rect.width() * (0.94 if compact else 0.90)
        card_left = rect.center().x() - card_width / 2.0
        card_height = 178.0 if short_page else (326.0 if compact else 224.0)
        required_rows = _context_row_heights(painter, card_width, rows, typography.body_pt, compact)
        card_height = max(card_height, sum(required_rows) + (18.0 if compact else 16.0))
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
                font_size=typography.body_pt,
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
                font_size=typography.body_pt,
            )

        approval_top = card.bottom() + (9.0 if short_page else 14.0)
        approval_height = 60.0 if short_page else (83.0 if compact else 72.0)
        approval_items = document_control.approvals
        approval_value_height = max(
            18.0 if short_page else 24.0,
            *(_wrapped_height(
                painter, point_coordinate_font(typography.body_pt, text=value,
                                                paint_device=painter.device()),
                _value(value), card.width() / 3.0 - 14.0,
            ) for _, value in approval_items),
        )
        approval_value_top = 20.0 if short_page else 26.0
        signature_bottom = 16.0 if short_page else 19.0
        approval_height = max(approval_height, approval_value_top + approval_value_height
                              + signature_bottom + 3.0)
        approval = QRectF(card.left(), approval_top, card.width(), approval_height)
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QPen(card_border, 1.0))
        painter.drawRoundedRect(approval, 5.0, 5.0)
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
            label_font = point_coordinate_font(
                typography.caption_pt,
                text=label,
                paint_device=painter.device(),
            )
            label_font.setBold(True)
            painter.setFont(label_font)
            painter.setPen(accent_dark)
            paint_cover_text(painter,
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
                point_coordinate_font(
                    typography.body_pt,
                    text=value,
                    paint_device=painter.device(),
                )
            )
            painter.setPen(value_color)
            paint_cover_text(painter,
                QRectF(
                    cell.left() + 7.0,
                    cell.top() + approval_value_top,
                    cell.width() - 14.0,
                    approval_value_height,
                ),
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignVCenter
                | Qt.TextFlag.TextWordWrap,
                _value(value),
            )
            painter.setPen(QPen(line_color, 0.8))
            signature_y = cell.bottom() - signature_bottom
            painter.drawLine(
                QLineF(
                    cell.left() + 7.0,
                    signature_y,
                    cell.right() - 7.0,
                    signature_y,
                )
            )
            painter.setFont(
                point_coordinate_font(
                    typography.caption_pt,
                    text=labels["signature"],
                    paint_device=painter.device(),
                )
            )
            painter.setPen(muted)
            paint_cover_text(painter,
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
            point_coordinate_font(
                typography.caption_pt,
                text=' '.join(footer_parts),
                paint_device=painter.device(),
            )
        )
        painter.setPen(muted)
        paint_cover_text(painter,
            footer,
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            "\n".join(footer_parts),
        )
    finally:
        painter.restore()

    canvas.y = canvas.content_rect.bottom()


def _wrapped_height(painter: QPainter, font: QFont, text: str, width: float) -> float:
    """Measure the same point-coordinate font and wrapping used for drawing."""
    return cover_text_layout(text, width, font, painter.device()).height


def _context_row_heights(
    painter: QPainter, card_width: float, rows: tuple[tuple[str, str], ...],
    font_size: float, compact: bool,
) -> tuple[float, ...]:
    label_font = point_coordinate_font(font_size, text=' '.join(label for label, _ in rows),
                                       paint_device=painter.device(), bold=True)
    value_font = point_coordinate_font(font_size, text=' '.join(_value(value) for _, value in rows),
                                       paint_device=painter.device())
    if compact:
        label_width = min(142.0, card_width * 0.34)
        value_width = card_width - 28.0 - label_width
        padding = 4.0
    else:
        column_width = (card_width - 24.0) / 2.0
        label_width = column_width * 0.37 - 9.0
        value_width = column_width * 0.63 - 7.0
        padding = 6.0
    measured = tuple(max(_wrapped_height(painter, label_font, f'{label}:', label_width),
                         _wrapped_height(painter, value_font, _value(value), value_width))
                     for label, value in rows)
    if compact:
        return tuple(height + padding for height in measured)
    return tuple(max(measured[index:index + 2]) + padding
                 for index in range(0, len(measured), 2))


def _draw_compact_rows(
    painter: QPainter,
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
    required = _context_row_heights(painter, card.width(), rows, font_size, True)
    spare = (card.height() - 18.0 - sum(required)) / len(required)
    label_font = point_coordinate_font(
        font_size,
        text=" ".join(label for label, _ in rows),
        paint_device=painter.device(),
    )
    label_font.setBold(True)
    value_font = point_coordinate_font(
        font_size,
        text=" ".join(_value(value) for _, value in rows),
        paint_device=painter.device(),
    )
    row_top = card.top() + 9.0
    for index, (label, value) in enumerate(rows):
        row_height = required[index] + spare
        if index:
            painter.setPen(QPen(line_color, 0.7))
            painter.drawLine(
                QLineF(row_left, row_top, row_left + row_width, row_top)
            )
        painter.setFont(label_font)
        painter.setPen(text_color)
        paint_cover_text(painter,
            QRectF(row_left, row_top + 2.0, label_width, row_height - 4.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
            f"{label}:",
        )
        painter.setFont(value_font)
        painter.setPen(value_color)
        paint_cover_text(painter,
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
    painter: QPainter,
    card: QRectF,
    rows: tuple[tuple[str, str], ...],
    *,
    text_color: QColor,
    value_color: QColor,
    line_color: QColor,
    card_border: QColor,
    font_size: float,
) -> None:
    pair_count = (len(rows) + 1) // 2
    required = _context_row_heights(painter, card.width(), rows, font_size, False)
    spare = (card.height() - 16.0 - sum(required)) / len(required)
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
    label_font = point_coordinate_font(
        font_size,
        text=" ".join(label for label, _ in rows),
        paint_device=painter.device(),
    )
    label_font.setBold(True)
    value_font = point_coordinate_font(
        font_size,
        text=" ".join(_value(value) for _, value in rows),
        paint_device=painter.device(),
    )
    row_top = inner.top()
    for pair_index in range(pair_count):
        pair_height = required[pair_index] + spare
        if pair_index:
            painter.setPen(QPen(line_color, 0.7))
            painter.drawLine(QLineF(inner.left(), row_top, inner.right(), row_top))
        for column_index in range(2):
            row_index = pair_index * 2 + column_index
            if row_index >= len(rows):
                continue
            label, value = rows[row_index]
            cell_left = inner.left() + column_index * column_width
            label_width = column_width * 0.37
            painter.setFont(label_font)
            painter.setPen(text_color)
            paint_cover_text(painter,
                QRectF(
                    cell_left + 7.0,
                    row_top + 3.0,
                    label_width - 9.0,
                    pair_height - 6.0,
                ),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
                f"{label}:",
            )
            painter.setFont(value_font)
            painter.setPen(value_color)
            paint_cover_text(painter,
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
        row_top += pair_height


__all__ = ["render_report_cover"]
