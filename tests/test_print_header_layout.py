from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

import geoworkbench.printing.page_renderer as page_renderer
from geoworkbench.printing.document_renderer import (
    PrintDocumentContext,
    PrintDocumentPage,
    _should_paint_column_header_at_bottom,
    _should_paint_column_header_at_top,
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
from geoworkbench.printing.tablet_print import (
    TabletPrintSnapshot,
    paint_tablet_header_repeat,
    paint_tablet_snapshot,
)
from geoworkbench.tablet.tablet_view import TabletView


def _page(
    vertical_index: int,
    vertical_total: int,
    continuation_index: int = 1,
    continuation_total: int = 1,
) -> PrintDocumentPage:
    page_index = (vertical_index - 1) * continuation_total + continuation_index
    return PrintDocumentPage(
        PrintPageSlice(0.0, 50.0, vertical_index, vertical_total),
        PrintContinuationSlice(
            float((continuation_index - 1) * 200),
            float(continuation_index * 200),
            continuation_index,
            continuation_total,
            1.0,
        ),
        page_index,
        vertical_total * continuation_total,
    )


def test_bottom_column_header_is_only_added_after_last_vertical_interval() -> None:
    job = PrintJobSettings(
        output_format=PrintOutputFormat.PRINTER,
        repeat_column_header_at_bottom=True,
    )

    assert not _should_paint_column_header_at_bottom(job, _page(1, 2))
    assert _should_paint_column_header_at_bottom(job, _page(2, 2))


def test_bottom_column_header_is_added_to_each_final_depth_continuation() -> None:
    job = PrintJobSettings(
        output_format=PrintOutputFormat.PRINTER,
        repeat_column_header_at_bottom=True,
    )

    assert _should_paint_column_header_at_bottom(job, _page(2, 2, 1, 2))
    assert _should_paint_column_header_at_bottom(job, _page(2, 2, 2, 2))
    assert not _should_paint_column_header_at_bottom(job, _page(1, 2, 2, 2))


def test_column_header_is_always_at_document_start() -> None:
    assert _should_paint_column_header_at_top(_page(1, 2))
    assert not _should_paint_column_header_at_top(_page(2, 2))


def test_end_column_header_can_be_disabled_without_removing_top_header() -> None:
    job = PrintJobSettings(
        output_format=PrintOutputFormat.PRINTER,
        repeat_column_header_at_bottom=False,
    )

    assert _should_paint_column_header_at_top(_page(1, 2))
    assert not _should_paint_column_header_at_bottom(job, _page(2, 2))


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


def test_tablet_body_can_hide_the_captured_column_header(qapp) -> None:
    track = QPixmap(100, 100)
    track.fill(QColor("#3b82f6"))
    track_painter = QPainter(track)
    try:
        track_painter.fillRect(QRectF(0.0, 0.0, 100.0, 30.0), QColor("#ef4444"))
    finally:
        track_painter.end()
    snapshot = TabletPrintSnapshot(
        (track,),
        AdaptiveColumnLayout((100,), spacing=0),
        content_height=100,
        header_height=30,
    )
    canvas = QImage(100, 100, QImage.Format.Format_ARGB32)
    canvas.fill(QColor("white"))
    painter = QPainter(canvas)
    try:
        paint_tablet_snapshot(
            painter,
            QRectF(0.0, 0.0, 100.0, 100.0),
            snapshot,
            show_column_header=False,
            fill_height=True,
        )
    finally:
        painter.end()

    assert canvas.pixelColor(50, 1) == QColor("#3b82f6")
    assert canvas.pixelColor(50, 98) == QColor("#3b82f6")


def test_hidden_top_header_makes_adaptive_tablet_fill_the_page(qapp, monkeypatch) -> None:
    tablet = TabletView()
    tablet.resize(400, 300)
    monkeypatch.setattr(TabletView, "printable_tracks", lambda _self: (object(),))
    snapshot = object()
    captured_snapshot_options: dict[str, object] = {}

    def capture_snapshot(*_args, **kwargs):
        captured_snapshot_options.update(kwargs)
        return snapshot

    monkeypatch.setattr(page_renderer, "capture_tablet_print_snapshot", capture_snapshot)
    received: dict[str, object] = {}

    def record_paint(*_args, **kwargs) -> None:
        received.update(kwargs)

    monkeypatch.setattr(page_renderer, "paint_tablet_snapshot", record_paint)
    canvas = QImage(400, 600, QImage.Format.Format_ARGB32)
    canvas.fill(QColor("white"))
    painter = QPainter(canvas)
    try:
        page_renderer.paint_widget_page(
            tablet,
            painter,
            QRectF(0.0, 0.0, 400.0, 600.0),
            scale_mode=PrintScaleMode.FIT,
            show_column_header=False,
            included_track_ids=("gas",),
            grid_print_overrides=(("gas", False),),
        )
    finally:
        painter.end()
        tablet.close()

    assert received["fill_height"] is True
    assert captured_snapshot_options["included_track_ids"] == ("gas",)
    assert captured_snapshot_options["grid_print_overrides"] == {"gas": False}


def test_end_header_supplements_instead_of_replacing_the_start_header(
    qapp, monkeypatch
) -> None:
    pixmap = QPixmap(100, 100)
    pixmap.fill(QColor("#3b82f6"))
    snapshot = TabletPrintSnapshot(
        (pixmap,),
        AdaptiveColumnLayout((100,), spacing=0),
        content_height=100,
        header_height=20,
    )
    body_rects: list[QRectF] = []
    header_rects: list[QRectF] = []
    monkeypatch.setattr(
        page_renderer,
        "paint_tablet_snapshot",
        lambda _painter, rect, *_args, **_kwargs: body_rects.append(QRectF(rect)),
    )
    monkeypatch.setattr(
        page_renderer,
        "paint_tablet_header_repeat",
        lambda _painter, rect, *_args, **_kwargs: header_rects.append(QRectF(rect)),
    )
    canvas = QImage(400, 600, QImage.Format.Format_ARGB32)
    canvas.fill(QColor("white"))
    painter = QPainter(canvas)
    try:
        page_renderer._paint_tablet_with_repeated_header(
            painter,
            QRectF(0.0, 0.0, 400.0, 600.0),
            snapshot,
            scale_mode=PrintScaleMode.FIT,
            continuation=None,
            show_column_header=True,
        )
    finally:
        painter.end()

    assert len(header_rects) == 2
    assert header_rects[0].top() == 0.0
    assert body_rects[0].top() > header_rects[0].bottom()
    assert header_rects[1].top() > body_rects[0].bottom()
    assert header_rects[1].bottom() == 600.0
