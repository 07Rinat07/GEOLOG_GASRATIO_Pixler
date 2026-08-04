from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

import geoworkbench.printing.page_renderer as page_renderer
from geoworkbench.printing.form_column_layout import AdaptiveColumnLayout
from geoworkbench.printing.print_layout import PrintScaleMode
from geoworkbench.printing.tablet_print import TabletPrintSnapshot


def test_short_final_page_anchors_repeated_header_to_bottom(qapp, monkeypatch) -> None:
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
    assert body_rects[0].top() == page.top()
    assert header_rects[0].bottom() == page.bottom()
    assert body_rects[0].bottom() < header_rects[0].top()
