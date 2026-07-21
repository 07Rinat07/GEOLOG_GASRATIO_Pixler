from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter

from geoworkbench.domain.text_presentation import (
    normalize_text_orientation,
    normalize_text_vertical_position,
    text_angle,
    text_position_fraction,
)


def vertical_alignment_flag(position: str | None) -> Qt.AlignmentFlag:
    normalized = normalize_text_vertical_position(position)
    return {
        "top": Qt.AlignmentFlag.AlignTop,
        "center": Qt.AlignmentFlag.AlignVCenter,
        "bottom": Qt.AlignmentFlag.AlignBottom,
    }[normalized]


def draw_oriented_text(
    painter: QPainter,
    rect: QRectF,
    text: str,
    *,
    orientation: str = "horizontal",
    position: str = "center",
    horizontal_alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignHCenter,
    word_wrap: bool = True,
    padding_x: float = 0.5,
    padding_y: float = 0.2,
) -> None:
    """Draw text at 0/±90° while preserving top/centre/bottom anchoring."""

    if not text or rect.width() <= 0.0 or rect.height() <= 0.0:
        return
    normalized_orientation = normalize_text_orientation(orientation)
    normalized_position = normalize_text_vertical_position(position)
    target = rect.adjusted(padding_x, padding_y, -padding_x, -padding_y)
    if target.width() <= 0.0 or target.height() <= 0.0:
        return
    flags = horizontal_alignment | vertical_alignment_flag(normalized_position)
    if word_wrap:
        flags |= Qt.TextFlag.TextWordWrap

    painter.save()
    painter.setClipRect(rect)
    if normalized_orientation == "horizontal":
        painter.drawText(target, flags, text)
    else:
        anchor_y = target.top() + target.height() * text_position_fraction(normalized_position)
        painter.translate(target.center().x(), anchor_y)
        painter.rotate(text_angle(normalized_orientation))
        rotated_rect = QRectF(
            -target.height() / 2.0,
            -target.width() / 2.0,
            target.height(),
            target.width(),
        )
        rotated_flags = Qt.AlignmentFlag.AlignCenter
        if word_wrap:
            rotated_flags |= Qt.TextFlag.TextWordWrap
        painter.drawText(rotated_rect, rotated_flags, text)
    painter.restore()


def column_heading_height(columns: object) -> float:
    """Return the common print heading band required by column title rotation."""

    try:
        values = list(columns)  # type: ignore[arg-type]
    except TypeError:
        return 12.0
    for column in values:
        properties = getattr(column, "properties", {})
        if isinstance(properties, dict) and properties.get("title_orientation") in {
            "vertical_bottom_to_top",
            "vertical_top_to_bottom",
        }:
            return 24.0
    return 12.0
