from __future__ import annotations

from math import pi, sin

from PySide6.QtCore import QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import (
    QColor,
    QHideEvent,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QShowEvent,
)
from PySide6.QtWidgets import QWidget


class DrillingAnimation(QWidget):
    """Lightweight vector rig animation used by the splash and home page."""

    def __init__(self, *, dark: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.dark = dark
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._advance)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setMinimumSize(180, 110)

    @property
    def phase(self) -> float:
        return self._phase

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802
        self._timer.stop()
        super().hideEvent(event)

    def _advance(self) -> None:
        self._phase = (self._phase + 0.035) % 1.0
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        width = float(self.width())
        height = float(self.height())
        if width < 2 or height < 2:
            return

        navy = QColor("#dcecff") if self.dark else QColor("#164e7a")
        steel = QColor("#80bce8") if self.dark else QColor("#256b9b")
        gold = QColor("#f5b942") if self.dark else QColor("#d89318")
        ground = QColor("#25445e") if self.dark else QColor("#dbe8f1")
        strata = (
            (QColor("#b7793f"), 0.80),
            (QColor("#d8a54c"), 0.86),
            (QColor("#87533a"), 0.92),
        )

        if self.dark:
            glow = QLinearGradient(0, 0, width, height)
            glow.setColorAt(0.0, QColor(20, 68, 104, 35))
            glow.setColorAt(1.0, QColor(245, 185, 66, 18))
            painter.fillRect(self.rect(), glow)

        horizon = height * 0.74
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(ground)
        painter.drawRoundedRect(QRectF(0, horizon, width, height - horizon), 6, 6)

        for color, ratio in strata:
            path = QPainterPath(QPointF(0, height * ratio))
            for step in range(1, 13):
                x = width * step / 12
                y = height * ratio + sin(step * 0.85 + self._phase * 2 * pi) * height * 0.012
                path.lineTo(x, y)
            painter.setPen(QPen(color, max(1.4, height * 0.012)))
            painter.drawPath(path)

        centre = width * 0.56
        mast_top = QPointF(centre, height * 0.09)
        left_foot = QPointF(centre - width * 0.17, horizon)
        right_foot = QPointF(centre + width * 0.17, horizon)
        rig_pen = QPen(navy, max(1.8, width * 0.008))
        rig_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(rig_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(mast_top, left_foot)
        painter.drawLine(mast_top, right_foot)
        painter.drawLine(left_foot, right_foot)

        levels = 6
        for level in range(1, levels + 1):
            fraction = level / (levels + 1)
            y = mast_top.y() + (horizon - mast_top.y()) * fraction
            half = width * 0.17 * fraction
            left = QPointF(centre - half, y)
            right = QPointF(centre + half, y)
            painter.setPen(QPen(steel, max(1.0, width * 0.004)))
            painter.drawLine(left, right)
            previous_y = mast_top.y() + (horizon - mast_top.y()) * (fraction - 1 / (levels + 1))
            previous_half = width * 0.17 * max(0.0, fraction - 1 / (levels + 1))
            painter.drawLine(QPointF(centre - previous_half, previous_y), right)
            painter.drawLine(QPointF(centre + previous_half, previous_y), left)

        platform_y = height * 0.55
        painter.setPen(QPen(navy, max(2.0, height * 0.018)))
        painter.drawLine(QPointF(width * 0.29, platform_y), QPointF(width * 0.83, platform_y))
        painter.setPen(QPen(gold, max(1.5, height * 0.012)))
        painter.drawLine(
            QPointF(width * 0.31, platform_y - height * 0.035),
            QPointF(width * 0.81, platform_y - height * 0.035),
        )

        hook_y = height * (0.27 + 0.025 * sin(self._phase * 2 * pi))
        painter.setPen(QPen(gold, max(1.5, width * 0.006)))
        painter.drawLine(QPointF(mast_top.x(), mast_top.y() + 4), QPointF(centre, hook_y))
        painter.setBrush(gold)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(centre, hook_y), 4.0, 4.0)

        bit_y = height * 0.92
        painter.setPen(QPen(navy, max(1.5, width * 0.005)))
        painter.drawLine(QPointF(centre, hook_y + 4), QPointF(centre, bit_y - 5))
        wobble = sin(self._phase * 8 * pi) * width * 0.012
        bit = QPolygonF(
            [
                QPointF(centre - 7 + wobble, bit_y - 5),
                QPointF(centre + 7 + wobble, bit_y - 5),
                QPointF(centre + wobble, bit_y + 4),
            ]
        )
        painter.setBrush(gold)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(bit)

        pulse = (self._phase * 2.0) % 1.0
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(gold.red(), gold.green(), gold.blue(), int(170 * (1 - pulse))), 1.5))
        painter.drawEllipse(QPointF(centre, bit_y), 6 + pulse * 22, 3 + pulse * 8)
