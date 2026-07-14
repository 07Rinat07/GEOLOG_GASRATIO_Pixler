from PySide6.QtCore import Qt

from geoworkbench.tablet.lithology_patterns import lithology_brush, supported_pattern_keys


def test_lithology_brush_uses_pattern_and_safe_color_fallback(qapp) -> None:
    patterned = lithology_brush("#e7cf8b", "sandstone_bricks")
    fallback = lithology_brush("not-a-color", "unknown")

    assert patterned.style() is Qt.BrushStyle.BDiagPattern
    assert patterned.color().name() == "#e7cf8b"
    assert fallback.style() is Qt.BrushStyle.SolidPattern
    assert fallback.color().name() == "#b0b0b0"
    assert "sandstone_bricks" in supported_pattern_keys()
