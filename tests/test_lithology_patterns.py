import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter

from geoworkbench.tablet.lithology_patterns import (
    lithology_brush,
    masterlog_lithology_brush,
    supported_pattern_keys,
)


def test_lithology_brush_uses_pattern_and_safe_color_fallback(qapp) -> None:
    patterned = lithology_brush("#e7cf8b", "sandstone_bricks")
    fallback = lithology_brush("not-a-color", "unknown")

    assert patterned.style() is Qt.BrushStyle.TexturePattern
    assert not patterned.textureImage().isNull()
    assert fallback.style() is Qt.BrushStyle.SolidPattern
    assert fallback.color().name() == "#b0b0b0"
    assert "sandstone_bricks" in supported_pattern_keys()


def test_masterlog_bitmap_brush_cancels_canvas_scale(qapp) -> None:
    image = QImage(200, 200, QImage.Format.Format_ARGB32_Premultiplied)
    image.setDotsPerMeterX(round(96 / 0.0254))
    image.setDotsPerMeterY(round(96 / 0.0254))
    painter = QPainter(image)
    painter.scale(4.0, 8.0)

    brush = masterlog_lithology_brush(painter, "#ffffff", "sandstone_bricks")
    painter.end()

    assert brush.style() is Qt.BrushStyle.TexturePattern
    assert brush.transform().m11() == pytest.approx(0.25, rel=0.01)
    assert brush.transform().m22() == pytest.approx(0.125, rel=0.01)
