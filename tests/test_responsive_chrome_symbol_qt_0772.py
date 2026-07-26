from __future__ import annotations

# Qt imports intentionally follow the dependency-aware module skip.
# ruff: noqa: E402

import pytest


pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from geoworkbench.project.annotation_schema import (
    AnnotationAnchor,
    AnnotationKind,
    AnnotationRecord,
)
from geoworkbench.tablet.annotation_graphics import (
    TabletAnnotationItem,
    TabletAnnotationOverlay,
)


def _symbol() -> AnnotationRecord:
    return AnnotationRecord(
        annotation_id="symbol-qt",
        kind=AnnotationKind.SYMBOL,
        anchor=AnnotationAnchor.DEPTH,
        text="",
        track_id="gas",
        depth=100.0,
        axis_value=None,
        axis_id=None,
        parameter_mnemonic=None,
        parameter_value=None,
        unit="",
        x_fraction=0.5,
        offset_x=0.0,
        offset_y=0.0,
        width=0.01,
        height=0.01,
        symbol_id="catalog-bit",
    )


def test_tiny_symbol_render_rect_stays_visible_without_changing_geometry(qapp) -> None:
    del qapp
    pixmap = QPixmap(4, 4)
    pixmap.fill()
    item = TabletAnnotationItem(_symbol(), pixmap=pixmap, edit_mode=True)
    image = QImage(32, 32, QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(image)
    try:
        rendered = item.rendered_box_rect(painter)
        device_rect = painter.deviceTransform().mapRect(rendered)
    finally:
        painter.end()

    assert item.box_rect().width() == 0.01
    assert item.box_rect().height() == 0.01
    assert device_rect.width() >= 1.0
    assert device_rect.height() >= 1.0


def test_tiny_symbol_bounds_cover_all_selection_handles(qapp) -> None:
    del qapp
    item = TabletAnnotationItem(_symbol(), edit_mode=True)
    bounds = item.boundingRect()

    assert all(bounds.contains(handle) for handle in item.resize_handle_rects().values())


def test_tiny_symbol_can_move_from_inside_selection_frame(qapp) -> None:
    canvas = QWidget()
    canvas.resize(200, 200)
    overlay = TabletAnnotationOverlay(canvas)
    overlay.set_content_rect(QRectF(0.0, 0.0, 200.0, 200.0))
    overlay.set_entries([(_symbol(), QPointF(100.0, 100.0), None)])
    overlay.set_edit_mode(True)
    try:
        hit = overlay.hit_test(101.0, 101.0)

        assert hit is not None
        assert hit.resize_handle is None
        assert hit.movable is True
        assert overlay.begin_interaction(hit, 101.0, 101.0) is True
    finally:
        overlay.cancel_interaction()
        overlay.close()
        canvas.close()
