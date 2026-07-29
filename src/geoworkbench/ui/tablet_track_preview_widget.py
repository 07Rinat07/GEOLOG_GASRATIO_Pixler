from __future__ import annotations

from copy import deepcopy
from math import pi, sin

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from geoworkbench.domain.text_presentation import text_angle
from geoworkbench.tablet.models import CurveLineStyle, CurveStyle, TrackDefinition


class TabletTrackPreviewWidget(QWidget):
    """Live, data-independent preview of a tablet track and its printable header."""

    def __init__(self, track: TrackDefinition, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._track = deepcopy(track)
        self.setMinimumSize(300, 360)
        self.setObjectName("tablet-track-live-preview")

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        return QSize(430, 700)

    def set_track(self, track: TrackDefinition) -> None:
        self._track = deepcopy(track)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.fillRect(self.rect(), QColor("#20242b"))

        margin = 18.0
        page = QRectF(
            margin,
            margin,
            max(40.0, self.width() - margin * 2.0),
            max(80.0, self.height() - margin * 2.0),
        )
        painter.fillRect(page, QColor("#ffffff"))
        painter.setPen(QPen(QColor("#475569"), 1.0))
        painter.drawRect(page)

        header_height = min(max(120.0, page.height() * 0.31), 230.0)
        group_height = 28.0 if self._track.group_title else 0.0
        title_height = 58.0
        curve_count = max(1, len(self._track.curve_mnemonics))
        curve_row_height = max(18.0, min(32.0, (header_height - group_height - title_height) / curve_count))

        y = page.top()
        if self._track.group_title:
            group_rect = QRectF(page.left(), y, page.width(), group_height)
            painter.fillRect(group_rect, QColor("#eef2f7"))
            painter.setPen(QColor("#0f172a"))
            font = QFont(painter.font())
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(group_rect.adjusted(6, 0, -6, 0), Qt.AlignmentFlag.AlignCenter, self._track.group_title)
            painter.setPen(QPen(QColor("#94a3b8"), 0.8))
            painter.drawRect(group_rect)
            y += group_height

        title_rect = QRectF(page.left(), y, page.width(), title_height)
        painter.fillRect(title_rect, QColor("#f8fafc"))
        painter.setPen(QPen(QColor("#64748b"), 0.8))
        painter.drawRect(title_rect)
        self._draw_oriented_title(painter, title_rect, self._track.title)
        y += title_height

        for mnemonic in self._track.curve_mnemonics or [""]:
            display = self._track.curve_display_settings(mnemonic) if mnemonic else None
            style = self._track.curve_style(mnemonic) if mnemonic else CurveStyle()
            row = QRectF(page.left(), y, page.width(), curve_row_height)
            painter.fillRect(row, QColor("#ffffff"))
            painter.setPen(QPen(QColor("#cbd5e1"), 0.7))
            painter.drawRect(row)
            if display is not None:
                caption = display.display_name or mnemonic
                value_range = (
                    "AUTO"
                    if display.automatic_range
                    else f"{display.x_min:g} … {display.x_max:g}"
                )
                painter.setPen(QColor(display.header_text_color))
                painter.drawText(row.adjusted(6, 0, -74, 0), Qt.AlignmentFlag.AlignVCenter, caption)
                painter.setPen(QColor("#475569"))
                painter.drawText(row.adjusted(row.width() - 110, 0, -6, 0), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, value_range)
                underline = display.header_line_color or style.color
                painter.setPen(self._curve_pen(style, underline, 1.0))
                painter.drawLine(row.left() + 4, row.bottom() - 2, row.right() - 4, row.bottom() - 2)
            y += curve_row_height
            if y >= page.top() + header_height:
                break

        body_top = page.top() + header_height
        body = QRectF(page.left(), body_top, page.width(), max(20.0, page.bottom() - body_top))
        painter.fillRect(body, QColor("#ffffff"))
        self._draw_grid(painter, body)
        self._draw_curves(painter, body)
        painter.setPen(QPen(QColor("#475569"), 0.9))
        painter.drawRect(body)

    def _draw_oriented_title(self, painter: QPainter, rect: QRectF, text: str) -> None:
        painter.save()
        painter.setPen(QColor("#0f172a"))
        font = QFont(painter.font())
        font.setBold(True)
        font.setPointSizeF(max(7.0, min(12.0, rect.height() / 5.0)))
        painter.setFont(font)
        orientation = self._track.title_orientation
        if orientation == "horizontal":
            painter.drawText(rect.adjusted(6, 4, -6, -4), Qt.AlignmentFlag.AlignCenter, text)
        else:
            painter.translate(rect.center())
            painter.rotate(text_angle(orientation))
            rotated = QRectF(-rect.height() / 2.0, -rect.width() / 2.0, rect.height(), rect.width())
            painter.drawText(rotated.adjusted(4, 4, -4, -4), Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    def _draw_grid(self, painter: QPainter, body: QRectF) -> None:
        if not (self._track.grid_x or self._track.grid_y):
            return
        alpha = int(max(0.0, min(1.0, self._track.grid_alpha)) * 255)
        major = QColor(100, 116, 139, alpha)
        minor = QColor(148, 163, 184, max(30, alpha // 2))
        if self._track.grid_x:
            divisions = max(1, self._track.grid_major_divisions)
            for index in range(1, divisions):
                x = body.left() + body.width() * index / divisions
                painter.setPen(QPen(major, 0.8))
                painter.drawLine(x, body.top(), x, body.bottom())
            minor_divisions = max(divisions, divisions * max(1, self._track.grid_minor_divisions))
            for index in range(1, minor_divisions):
                if index % max(1, self._track.grid_minor_divisions) == 0:
                    continue
                x = body.left() + body.width() * index / minor_divisions
                painter.setPen(QPen(minor, 0.45))
                painter.drawLine(x, body.top(), x, body.bottom())
        if self._track.grid_y:
            for index in range(1, 10):
                y = body.top() + body.height() * index / 10.0
                painter.setPen(QPen(major if index % 5 == 0 else minor, 0.7))
                painter.drawLine(body.left(), y, body.right(), y)

    def _draw_curves(self, painter: QPainter, body: QRectF) -> None:
        mnemonics = self._track.curve_mnemonics[:8]
        for curve_index, mnemonic in enumerate(mnemonics):
            style = self._track.curve_style(mnemonic) or CurveStyle()
            path = QPainterPath()
            samples = 72
            for sample in range(samples):
                ratio = sample / max(1, samples - 1)
                y = body.top() + ratio * body.height()
                phase = curve_index * 0.73
                value = 0.50 + 0.34 * sin(ratio * pi * (2.2 + curve_index * 0.18) + phase)
                value += 0.07 * sin(ratio * pi * 11.0 + phase)
                x = body.left() + max(0.03, min(0.97, value)) * body.width()
                if sample == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            painter.setPen(self._curve_pen(style, style.color, 0.8))
            painter.drawPath(path)

    @staticmethod
    def _curve_pen(style: CurveStyle, color: str, width_scale: float) -> QPen:
        pen = QPen(QColor(color), max(0.7, style.width * width_scale))
        pen.setStyle(
            {
                CurveLineStyle.SOLID: Qt.PenStyle.SolidLine,
                CurveLineStyle.DASH: Qt.PenStyle.DashLine,
                CurveLineStyle.DOT: Qt.PenStyle.DotLine,
                CurveLineStyle.DASH_DOT: Qt.PenStyle.DashDotLine,
            }[style.line_style]
        )
        return pen
