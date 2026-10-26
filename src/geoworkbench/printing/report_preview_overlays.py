"""Paint PDF-preview author marks and export them without touching source PDF data.

The same Qt painter is used for on-screen proof and export overlays. Unicode
text is rasterized as a transparent PDF overlay, avoiding the Helvetica-only
glyph limitations of PyMuPDF's standard PDF fonts.
"""

from __future__ import annotations

from collections import defaultdict
import os
from pathlib import Path
import tempfile

import pymupdf as fitz
from PySide6.QtCore import QBuffer, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QImageWriter, QPainter, QPen, QPolygonF

from geoworkbench.services.report_preview_marks import (
    PreviewMark,
    PreviewMarkKind,
    PreviewOverlay,
)


def paint_preview_marks(
    painter: QPainter,
    rect: QRectF,
    marks: tuple[PreviewMark, ...],
) -> None:
    """Draw normalized-page overlay marks into a Qt paint rectangle."""
    painter.save()
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        scale = max(rect.width() / 595.0, 0.1)
        for mark in marks:
            x = rect.x() + mark.x * rect.width()
            y = rect.y() + mark.y * rect.height()
            if mark.kind is PreviewMarkKind.FREEHAND:
                painter.setPen(QPen(
                    QColor("#1565c0"), max(1.5, 1.8 * scale),
                    Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                ))
                polygon = QPolygonF([
                    QPointF(rect.x() + px * rect.width(), rect.y() + py * rect.height())
                    for px, py in mark.points
                ])
                painter.drawPolyline(polygon)
                continue
            color = "#c2410c" if mark.kind is PreviewMarkKind.COMMENT else "#174ea6"
            painter.setPen(QColor(color))
            font = painter.font()
            font.setPixelSize(max(8, round(12.0 * scale)))
            painter.setFont(font)
            text_box = QRectF(
                x, y, max(1.0, rect.right() - x),
                max(1.0, rect.bottom() - y),
            )
            painter.drawText(
                text_box,
                Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap,
                mark.text,
            )
    finally:
        painter.restore()


def write_annotated_preview_pdf(
    source_pdf: Path,
    output_pdf: Path,
    overlay: PreviewOverlay,
) -> None:
    """Copy the production PDF with page-space marks; leave input unchanged.

    The caller must supply a different output path. Pages with no marks retain
    the original page contents without rasterization.
    """
    source = Path(source_pdf)
    output = Path(output_pdf)
    if source.resolve() == output.resolve():
        raise ValueError("The source PDF cannot be overwritten with a preview overlay")
    if not isinstance(overlay, PreviewOverlay):
        raise ValueError("Invalid preview overlay")
    with fitz.open(source) as document:
        by_page: dict[int, list[PreviewMark]] = defaultdict(list)
        for mark in overlay.marks:
            if mark.page >= len(document):
                raise ValueError("A preview mark references a missing PDF page")
            by_page[mark.page].append(mark)
        for index, marks in by_page.items():
            page = document[index]
            width = max(1, round(page.rect.width * 2))
            height = max(1, round(page.rect.height * 2))
            image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            try:
                paint_preview_marks(
                    painter, QRectF(0, 0, width, height), tuple(marks),
                )
            finally:
                painter.end()
            buffer = QBuffer()
            if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
                raise OSError("Cannot allocate the preview overlay PNG buffer")
            if not QImageWriter(buffer, b"PNG").write(image):
                raise OSError("Cannot render the preview overlay PNG")
            page.insert_image(page.rect, stream=buffer.data().data(), overlay=True)
        # Export is transactional: do not truncate a previously saved report
        # if rasterization or MuPDF fails mid-write.
        handle, temporary_name = tempfile.mkstemp(
            prefix=".geolog-preview-", suffix=".pdf", dir=output.parent,
        )
        os.close(handle)
        temporary = Path(temporary_name)
        try:
            document.save(temporary, garbage=3, deflate=True)
            os.replace(temporary, output)
        finally:
            temporary.unlink(missing_ok=True)
