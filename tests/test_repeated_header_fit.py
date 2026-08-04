from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

import geoworkbench.printing.page_renderer as page_renderer
from geoworkbench.printing.form_column_layout import AdaptiveColumnLayout
from geoworkbench.printing.print_layout import PrintScaleMode
from geoworkbench.printing.tablet_print import TabletPrintSnapshot


def _snapshot(*, content_height: int, header_height: int) -> TabletPrintSnapshot:
    pixmap = QPixmap(200, content_height)
    pixmap.fill(QColor("white"))
    return TabletPrintSnapshot(
        (pixmap,),
        AdaptiveColumnLayout((200,), spacing=0),
        content_height=content_height,
        header_height=header_height,
    )


def test_material_overflow_omits_bottom_header_instead_of_compressing_graph(
    qapp, monkeypatch
) -> None:
    snapshot = _snapshot(content_height=1000, header_height=300)
    body_calls: list[tuple[QRectF, bool]] = []
    header_calls: list[QRectF] = []

    def record_body(_painter, rect, _snapshot, **kwargs) -> None:
        body_calls.append((QRectF(rect), bool(kwargs["show_column_header"])))

    monkeypatch.setattr(page_renderer, "paint_tablet_snapshot", record_body)
    monkeypatch.setattr(
        page_renderer,
        "paint_tablet_header_repeat",
        lambda _painter, rect, *_args, **_kwargs: header_calls.append(QRectF(rect)),
    )

    canvas = QImage(400, 600, QImage.Format.Format_ARGB32)
    canvas.fill(QColor("white"))
    painter = QPainter(canvas)
    page = QRectF(0.0, 0.0, 400.0, 600.0)
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

    assert body_calls == [(page, False)]
    assert header_calls == []


def test_material_overflow_preserves_single_page_top_header(
    qapp, monkeypatch
) -> None:
    snapshot = _snapshot(content_height=1000, header_height=300)
    body_calls: list[bool] = []
    header_calls: list[QRectF] = []

    monkeypatch.setattr(
        page_renderer,
        "paint_tablet_snapshot",
        lambda _painter, _rect, _snapshot, **kwargs: body_calls.append(
            bool(kwargs["show_column_header"])
        ),
    )
    monkeypatch.setattr(
        page_renderer,
        "paint_tablet_header_repeat",
        lambda _painter, rect, *_args, **_kwargs: header_calls.append(QRectF(rect)),
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

    assert body_calls == [True]
    assert header_calls == []


def test_bottom_header_remains_when_graph_and_legend_fit_without_compression(
    qapp, monkeypatch
) -> None:
    snapshot = _snapshot(content_height=300, header_height=80)
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
    try:
        page_renderer._paint_tablet_with_repeated_header(
            painter,
            QRectF(0.0, 0.0, 400.0, 800.0),
            snapshot,
            scale_mode=PrintScaleMode.FIT,
            continuation=None,
            show_column_header=False,
        )
    finally:
        painter.end()

    assert len(body_rects) == 1
    assert len(header_rects) == 1
    assert body_rects[0].height() == 440.0
    assert header_rects[0].bottom() == 800.0
