from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import QLabel, QStyle, QStyleOption

from geoworkbench.domain.text_presentation import (
    normalize_text_orientation,
    normalize_text_vertical_position,
    rotated_text_alignment,
    text_angle,
)


class OrientedTextLabel(QLabel):
    """QLabel-compatible caption with 0/±90° orientation and vertical anchoring.

    The widget keeps the normal QLabel API (`setText`, tooltips and event filters)
    so the tablet header drag/resize interaction remains unchanged.
    """

    def __init__(
        self,
        text: str = "",
        parent=None,
        *,
        orientation: str = "horizontal",
        position: str = "center",
    ) -> None:
        super().__init__(text, parent)
        self._orientation = normalize_text_orientation(orientation)
        self._position = normalize_text_vertical_position(position)
        self.setWordWrap(True)
        self._apply_horizontal_alignment()

    @property
    def orientation(self) -> str:
        return self._orientation

    @property
    def vertical_position(self) -> str:
        return self._position

    def set_text_presentation(self, orientation: str, position: str) -> None:
        normalized_orientation = normalize_text_orientation(orientation)
        normalized_position = normalize_text_vertical_position(position)
        if (
            normalized_orientation == self._orientation
            and normalized_position == self._position
        ):
            return
        self._orientation = normalized_orientation
        self._position = normalized_position
        self._apply_horizontal_alignment()
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        hint = super().sizeHint()
        if self._orientation == "horizontal":
            return hint
        return QSize(max(36, hint.height()), max(72, hint.width()))

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt API
        hint = super().minimumSizeHint()
        if self._orientation == "horizontal":
            return hint
        return QSize(max(24, hint.height()), max(56, hint.width()))

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        if self._orientation == "horizontal":
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        option = QStyleOption()
        option.initFrom(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, option, painter, self)

        content = QRectF(self.contentsRect()).adjusted(5.0, 3.0, -5.0, -3.0)
        if content.width() <= 0.0 or content.height() <= 0.0:
            return
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.setFont(self.font())
        painter.translate(content.center())
        painter.rotate(text_angle(self._orientation))
        rotated = QRectF(
            -content.height() / 2.0,
            -content.width() / 2.0,
            content.height(),
            content.width(),
        )
        horizontal = {
            "left": Qt.AlignmentFlag.AlignLeft,
            "center": Qt.AlignmentFlag.AlignHCenter,
            "right": Qt.AlignmentFlag.AlignRight,
        }[rotated_text_alignment(self._orientation, self._position)]
        painter.drawText(
            rotated,
            horizontal | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
            self.text(),
        )

    def _apply_horizontal_alignment(self) -> None:
        vertical = {
            "top": Qt.AlignmentFlag.AlignTop,
            "center": Qt.AlignmentFlag.AlignVCenter,
            "bottom": Qt.AlignmentFlag.AlignBottom,
        }[self._position]
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter | vertical)
