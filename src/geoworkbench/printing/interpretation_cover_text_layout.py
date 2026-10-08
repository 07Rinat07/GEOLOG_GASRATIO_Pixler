from __future__ import annotations

from dataclasses import dataclass
from math import ceil, isfinite

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFont, QFontMetricsF, QPaintDevice, QPainter, QTextLayout, QTextOption


@dataclass(frozen=True, slots=True)
class CoverTextLayout:
    lines: tuple[str, ...]
    line_height: float

    @property
    def height(self) -> float:
        return len(self.lines) * self.line_height


def cover_text_layout(text: str, width: float, font: QFont,
                      paint_device: QPaintDevice | None) -> CoverTextLayout:
    """Wrap complete cover text with a physical pitch that also fits Windows glyphs."""
    if not isfinite(width) or width <= 0:
        raise ValueError('Cover text width must be finite and positive')
    metrics = QFontMetricsF(font, paint_device) if paint_device is not None else QFontMetricsF(font)
    pitch = float(ceil(max(metrics.height(), metrics.lineSpacing()) + 2.0))
    lines: list[str] = []
    for paragraph in text.split('\n'):
        if not paragraph:
            lines.append('')
            continue
        layout = QTextLayout(paragraph, font, paint_device)
        option = QTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        layout.setTextOption(option)
        encoded = paragraph.encode('utf-16-le')
        layout.beginLayout()
        try:
            while True:
                line = layout.createLine()
                if not line.isValid():
                    break
                line.setLineWidth(width)
                start, end = line.textStart(), line.textStart() + line.textLength()
                lines.append(encoded[start * 2:end * 2].decode('utf-16-le').strip())
        finally:
            layout.endLayout()
    return CoverTextLayout(tuple(lines), pitch)


def paint_cover_text(painter: QPainter, rect: QRectF,
                     flags: Qt.AlignmentFlag | Qt.TextFlag, text: str) -> None:
    """Draw the measured lines individually instead of Qt's automatic line advance."""
    layout = cover_text_layout(text, rect.width(), painter.font(), painter.device())
    top = rect.top()
    if int(flags) & int(Qt.AlignmentFlag.AlignVCenter):
        top += (rect.height() - layout.height) / 2.0
    elif int(flags) & int(Qt.AlignmentFlag.AlignBottom):
        top += rect.height() - layout.height
    horizontal = Qt.AlignmentFlag(int(flags) & int(Qt.AlignmentFlag.AlignHorizontal_Mask))
    for index, line in enumerate(layout.lines):
        painter.drawText(QRectF(rect.left(), top + index * layout.line_height,
                                rect.width(), layout.line_height),
                         horizontal | Qt.AlignmentFlag.AlignVCenter, line)
