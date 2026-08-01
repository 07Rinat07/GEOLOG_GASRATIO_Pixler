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
    tablet_header_gap_height,
    tablet_print_layout_height,
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


def test_repeated_header_preserves_source_aspect_ratio(qapp) -> None:
    header = QPixmap(200, 100)
    header.fill(QColor("#3b82f6"))
    snapshot = TabletPrintSnapshot(
        (header,),
        AdaptiveColumnLayout((200,), spacing=0),
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

    # A 200×80 source header rendered into 400×40 must remain 100×40 and
    # centered. Filling all 400 pixels would reproduce the squashed PDF header.
    assert canvas.pixelColor(1, 20) == QColor("white")
    assert canvas.pixelColor(200, 20) == QColor("#3b82f6")
    assert canvas.pixelColor(398, 20) == QColor("white")


def test_tablet_body_can_hide_the_captured_column_header_without_font_stretch(qapp) -> None:
    track = QPixmap(100, 100)
    track.fill(QColor("#3b82f6"))
    track_painter = QPainter(track)
    try:
        track_painter.fillRect(QRectF(0.0, 0.0, 100.0, 30.0), QColor("#ef4444"))
        track_painter.fillRect(QRectF(40.0, 50.0, 20.0, 20.0), QColor("#22c55e"))
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
    green = QColor("#22c55e")
    green_pixels = [
        (x, y)
        for y in range(canvas.height())
        for x in range(canvas.width())
        if canvas.pixelColor(x, y) == green
    ]
    assert green_pixels
    green_width = max(x for x, _y in green_pixels) - min(x for x, _y in green_pixels) + 1
    green_height = max(y for _x, y in green_pixels) - min(y for _x, y in green_pixels) + 1
    assert abs(green_width - green_height) <= 1


def test_body_only_layout_excludes_hidden_header_height() -> None:
    assert tablet_print_layout_height(
        300,
        80,
        show_column_header=True,
        repeat_column_header_at_bottom=False,
    ) == 300
    assert tablet_print_layout_height(
        300,
        80,
        show_column_header=False,
        repeat_column_header_at_bottom=False,
    ) == 220
    assert tablet_print_layout_height(
        300,
        80,
        show_column_header=False,
        repeat_column_header_at_bottom=True,
    ) == 220 + 80 + tablet_header_gap_height(300)


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
    assert captured_snapshot_options["show_column_header"] is False
    assert captured_snapshot_options["repeat_column_header_at_bottom"] is False


def test_repeated_header_composition_uses_one_uniform_scale(qapp, monkeypatch) -> None:
    pixmap = QPixmap(200, 300)
    pixmap.fill(QColor("#3b82f6"))
    snapshot = TabletPrintSnapshot(
        (pixmap,),
        AdaptiveColumnLayout((200,), spacing=0),
        content_height=300,
        header_height=80,
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
    total_height = tablet_print_layout_height(
        300,
        80,
        show_column_header=False,
        repeat_column_header_at_bottom=True,
    )
    canvas = QImage(400, total_height * 2, QImage.Format.Format_ARGB32)
    canvas.fill(QColor("white"))
    painter = QPainter(canvas)
    try:
        page_renderer._paint_tablet_with_repeated_header(
            painter,
            QRectF(0.0, 0.0, 400.0, float(total_height * 2)),
            snapshot,
            scale_mode=PrintScaleMode.FIT,
            continuation=None,
            show_column_header=False,
        )
    finally:
        painter.end()

    assert len(body_rects) == 1
    assert len(header_rects) == 1
    body = body_rects[0]
    footer_header = header_rects[0]
    assert body.width() / body.height() == 200 / 220
    assert footer_header.width() / footer_header.height() == 200 / 80
    assert body.top() == 0.0
    assert footer_header.bottom() == float(total_height * 2)


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
    assert header_rects[0].top() >= 0.0
    assert body_rects[0].top() > header_rects[0].bottom()
    assert header_rects[1].top() > body_rects[0].bottom()
    assert header_rects[1].bottom() <= 600.0
    assert header_rects[0].height() == header_rects[1].height()
