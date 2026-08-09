from __future__ import annotations

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

import geoworkbench.printing.page_renderer as page_renderer
from geoworkbench.printing.form_column_layout import AdaptiveColumnLayout
from geoworkbench.printing.print_layout import PrintScaleMode
from geoworkbench.printing.tablet_print import (
    TabletPrintError,
    TabletPrintSnapshot,
    tablet_header_gap_height,
)


def test_short_final_page_keeps_repeated_header_next_to_graph(qapp, monkeypatch) -> None:
    pixmap = QPixmap(200, 300)
    pixmap.fill(QColor("white"))
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

    canvas = QImage(400, 800, QImage.Format.Format_ARGB32)
    canvas.fill(QColor("white"))
    painter = QPainter(canvas)
    page = QRectF(0.0, 0.0, 400.0, 800.0)
    try:
        page_renderer._paint_tablet_with_repeated_header(
            painter,
            page,
            snapshot,
            scale_mode=PrintScaleMode.FIT,
            continuation=None,
            show_column_header=False,
        )
    finally:
        painter.end()

    assert len(body_rects) == 1
    assert len(header_rects) == 1
    graph_rect = body_rects[0]
    legend_rect = header_rects[0]
    assert graph_rect.top() == page.top()
    assert legend_rect.bottom() < page.bottom()
    horizontal_scale = page.width() / snapshot.layout.total_width
    assert legend_rect.top() - graph_rect.bottom() == (
        tablet_header_gap_height(snapshot.content_height) * horizontal_scale
    )
    assert not graph_rect.intersects(legend_rect)


def test_final_page_never_hides_overflow_by_narrowing_the_form(qapp) -> None:
    pixmap = QPixmap(200, 300)
    pixmap.fill(QColor("white"))
    snapshot = TabletPrintSnapshot(
        (pixmap,),
        AdaptiveColumnLayout((200,), spacing=0),
        content_height=300,
        header_height=80,
    )
    canvas = QImage(400, 500, QImage.Format.Format_ARGB32)
    canvas.fill(QColor("white"))
    painter = QPainter(canvas)
    try:
        with pytest.raises(TabletPrintError, match="автоматический интервал"):
            page_renderer._paint_tablet_with_repeated_header(
                painter,
                QRectF(0.0, 0.0, 400.0, 500.0),
                snapshot,
                scale_mode=PrintScaleMode.FIT,
                continuation=None,
                show_column_header=False,
            )
    finally:
        painter.end()
