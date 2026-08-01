from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

from geoworkbench.printing.document_renderer import (
    PrintDocumentContext,
    PrintDocumentPage,
    _should_paint_column_header_at_bottom,
    _should_paint_full_header,
)
from geoworkbench.printing.form_column_layout import AdaptiveColumnLayout
from geoworkbench.printing.pagination import PrintPageSlice
from geoworkbench.printing.print_job import (
    PrintHeaderPlacement,
    PrintJobSettings,
    PrintOutputFormat,
)
from geoworkbench.printing.print_layout import PrintContinuationSlice, PrintScaleMode
from geoworkbench.printing.tablet_print import TabletPrintSnapshot, paint_tablet_header_repeat


def _page(vertical_index: int, vertical_total: int) -> PrintDocumentPage:
    return PrintDocumentPage(
        PrintPageSlice(0.0, 50.0, vertical_index, vertical_total),
        PrintContinuationSlice(0.0, 200.0, 1, 1, 1.0),
        vertical_index,
        vertical_total,
    )


def test_bottom_column_header_is_only_added_after_last_vertical_interval() -> None:
    job = PrintJobSettings(
        output_format=PrintOutputFormat.PRINTER,
        repeat_column_header_at_bottom=True,
    )

    assert not _should_paint_column_header_at_bottom(job, _page(1, 2))
    assert _should_paint_column_header_at_bottom(job, _page(2, 2))


def test_full_document_header_placement_is_explicit() -> None:
    context = PrintDocumentContext(
        "Tablet",
        header_template=object(),  # type: ignore[arg-type]
        session=object(),  # type: ignore[arg-type]
    )
    first_only = PrintJobSettings(
        output_format=PrintOutputFormat.PRINTER,
        header_placement=PrintHeaderPlacement.FIRST_PAGE,
    )
    every_page = PrintJobSettings(
        output_format=PrintOutputFormat.PRINTER,
        header_placement=PrintHeaderPlacement.EVERY_PAGE,
    )

    assert _should_paint_full_header(first_only, _page(1, 2), context)
    assert not _should_paint_full_header(first_only, _page(2, 2), context)
    assert _should_paint_full_header(every_page, _page(2, 2), context)


def test_landscape_bottom_header_uses_the_full_available_width(qapp) -> None:
    left = QPixmap(100, 100)
    left.fill(QColor("#ef4444"))
    right = QPixmap(100, 100)
    right.fill(QColor("#3b82f6"))
    snapshot = TabletPrintSnapshot(
        (left, right),
        AdaptiveColumnLayout((100, 100), spacing=0),
        content_height=300,
        header_height=80,
    )
    canvas = QImage(400, 40, QImage.Format.Format_ARGB32)
    canvas.fill(QColor("white"))
    painter = QPainter(canvas)
    try:
        paint_tablet_header_repeat(
            painter,
            QRectF(0.0, 0.0, 400.0, 40.0),
            snapshot,
            scale_mode=PrintScaleMode.FIT,
        )
    finally:
        painter.end()

    assert canvas.pixelColor(1, 20) == QColor("#ef4444")
    assert canvas.pixelColor(398, 20) == QColor("#3b82f6")
