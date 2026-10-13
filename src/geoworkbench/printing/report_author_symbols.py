"""Author-selected vector symbols; no geological classification semantics."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF

from geoworkbench.domain.annotation_style import AnnotationStyle
from geoworkbench.domain.report_author_symbols import AuthorSymbolId
from geoworkbench.services.localization import AppLanguage


@dataclass(frozen=True, slots=True)
class AuthorSymbolSpec:
    symbol_id: AuthorSymbolId
    labels: tuple[str, str, str]

    def label(self, language: AppLanguage) -> str:
        return self.labels[{AppLanguage.RU: 0, AppLanguage.KK: 1, AppLanguage.EN: 2}[language]]


AUTHOR_SYMBOLS = (
    AuthorSymbolSpec(AuthorSymbolId.CIRCLE, ("Круг", "Шеңбер", "Circle")),
    AuthorSymbolSpec(AuthorSymbolId.SQUARE, ("Квадрат", "Шаршы", "Square")),
    AuthorSymbolSpec(AuthorSymbolId.DIAMOND, ("Ромб", "Ромб", "Diamond")),
    AuthorSymbolSpec(AuthorSymbolId.TRIANGLE, ("Треугольник", "Үшбұрыш", "Triangle")),
    AuthorSymbolSpec(AuthorSymbolId.CROSS, ("Крест", "Айқыш", "Cross")),
)


def paint_author_symbol(
    painter: QPainter, rect: QRectF, symbol_id: AuthorSymbolId, style: AnnotationStyle
) -> None:
    """Paint in caller coordinates with the existing annotation colour/line style."""
    symbol = AuthorSymbolId(symbol_id)
    if not all(isfinite(value) for value in (rect.x(), rect.y(), rect.width(), rect.height())):
        raise ValueError("Author symbol rectangle must be finite")
    if rect.width() <= 0 or rect.height() <= 0:
        return
    # Keep non-square supplied boxes from distorting catalogue symbols.
    side = min(rect.width(), rect.height())
    box = QRectF(rect.center().x() - side / 2, rect.center().y() - side / 2, side, side)
    painter.save()
    try:
        painter.setClipRect(rect, Qt.ClipOperation.IntersectClip)
        painter.setPen(
            QPen(
                QColor(style.border_color),
                style.border_width,
                {
                    "solid": Qt.PenStyle.SolidLine,
                    "dash": Qt.PenStyle.DashLine,
                    "dot": Qt.PenStyle.DotLine,
                }.get(style.border_style, Qt.PenStyle.SolidLine),
            )
        )
        fill = QColor(style.fill_color)
        fill.setAlphaF(style.fill_opacity)
        painter.setBrush(fill)
        if symbol is AuthorSymbolId.CIRCLE:
            painter.drawEllipse(box)
        elif symbol is AuthorSymbolId.SQUARE:
            painter.drawRect(box)
        elif symbol is AuthorSymbolId.DIAMOND:
            painter.drawPolygon(
                QPolygonF(
                    [
                        QPointF(box.center().x(), box.top()),
                        QPointF(box.right(), box.center().y()),
                        QPointF(box.center().x(), box.bottom()),
                        QPointF(box.left(), box.center().y()),
                    ]
                )
            )
        elif symbol is AuthorSymbolId.TRIANGLE:
            painter.drawPolygon(
                QPolygonF(
                    [QPointF(box.center().x(), box.top()), box.bottomRight(), box.bottomLeft()]
                )
            )
        else:
            painter.drawLine(box.topLeft(), box.bottomRight())
            painter.drawLine(box.bottomLeft(), box.topRight())
    finally:
        painter.restore()
