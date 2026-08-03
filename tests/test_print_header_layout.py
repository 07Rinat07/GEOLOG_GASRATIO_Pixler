from pathlib import Path

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

import geoworkbench.printing.page_renderer as page_renderer
from geoworkbench.printing.document_renderer import (
    PrintDocumentContext,
    PrintDocumentPage,
    PrintDocumentPlan,
    _build_automatic_page_slices,
    _page_target_content_height,
    _should_paint_column_header_at_bottom,
    _should_paint_column_header_at_top,
    _should_paint_full_header,
)
from geoworkbench.printing.form_column_layout import AdaptiveColumnLayout
from geoworkbench.printing.pagination import (
    PrintPageSlice,
    PrintPaginationSettings,
    PrintRangeMode,
)
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


def test_body_only_page_never_crops_wide_form_edges(qapp) -> None:
    track = QPixmap(200, 100)
    track.fill(QColor("white"))
    track_painter = QPainter(track)
    try:
        track_painter.fillRect(QRectF(0.0, 0.0, 200.0, 30.0), QColor("#111827"))
        track_painter.fillRect(QRectF(0.0, 30.0, 100.0, 70.0), QColor("#ef4444"))
        track_painter.fillRect(QRectF(100.0, 30.0, 100.0, 70.0), QColor("#3b82f6"))
    finally:
        track_painter.end()
    snapshot = TabletPrintSnapshot(
        (track,),
        AdaptiveColumnLayout((200,), spacing=0),
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

    # The old height-only scale made this 200 px source about 286 px wide and
    # clipped both outer edges.  A bounded uniform fit keeps both halves visible.
    assert canvas.pixelColor(1, 50) == QColor("#ef4444")
    assert canvas.pixelColor(98, 50) == QColor("#3b82f6")
    assert canvas.pixelColor(50, 10) == QColor("white")


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
            QRectF(10.0, 20.0, 300.0, 500.0),
            scale_mode=PrintScaleMode.FIT,
            show_column_header=False,
            included_track_ids=("gas",),
            grid_print_overrides=(("gas", False),),
        )
    finally:
        painter.end()
        tablet.close()

    assert received["fill_height"] is False
    assert captured_snapshot_options["included_track_ids"] == ("gas",)
    assert captured_snapshot_options["grid_print_overrides"] == {"gas": False}
    assert captured_snapshot_options["show_column_header"] is False
    assert captured_snapshot_options["repeat_column_header_at_bottom"] is False
    assert captured_snapshot_options["page_aspect_ratio"] == pytest.approx(400 / 600)


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


def test_auto_pagination_uses_a_smaller_first_page_capacity() -> None:
    pages = _build_automatic_page_slices(
        pagination=PrintPaginationSettings(range_mode=PrintRangeMode.FULL),
        current_range=(0.0, 50.0),
        full_range=(0.0, 250.0),
        first_units_per_page=60.0,
        regular_units_per_page=100.0,
    )

    assert [(page.start, page.end) for page in pages] == [
        (0.0, 60.0),
        (60.0, 160.0),
        (160.0, 250.0),
    ]
    assert [page.index for page in pages] == [1, 2, 3]
    assert all(page.total == 3 for page in pages)


def test_page_target_height_preserves_header_and_scales_only_body() -> None:
    continuation = PrintContinuationSlice(0.0, 100.0, 1, 1, 1.0)
    first = PrintDocumentPage(
        PrintPageSlice(0.0, 60.0, 1, 3),
        continuation,
        1,
        3,
    )
    partial = PrintDocumentPage(
        PrintPageSlice(160.0, 210.0, 3, 3),
        continuation,
        3,
        3,
    )
    plan = PrintDocumentPlan(
        pages=(first, partial),
        target_content_height_px=1000,
        resolved_units_per_page=100.0,
        tablet_header_height_px=200,
        first_page_target_content_height_px=700,
        first_page_units_per_page=60.0,
    )

    assert _page_target_content_height(plan, first) == 700
    assert _page_target_content_height(plan, partial) == 600


def test_adaptive_layout_uses_canonical_graph_body_height() -> None:
    source = Path(
        "src/geoworkbench/printing/tablet_print.py"
    ).read_text(encoding="utf-8")

    assert "canonical_layout_height - measured_header_height" in source


def test_print_snapshot_header_crop_uses_semantic_header_band() -> None:
    source = Path("src/geoworkbench/printing/tablet_print.py").read_text(encoding="utf-8")

    assert "+ print_header_band" in source
    assert "curve_header_scroll.height()" not in source
