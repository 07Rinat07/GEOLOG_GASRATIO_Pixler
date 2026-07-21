from geoworkbench.domain.text_presentation import (
    rotated_text_alignment,
    text_graphics_anchor,
)


def test_vertical_bottom_to_top_anchors_whole_label_inside_interval() -> None:
    assert text_graphics_anchor("vertical_bottom_to_top", "top") == (1.0, 0.5)
    assert text_graphics_anchor("vertical_bottom_to_top", "center") == (0.5, 0.5)
    assert text_graphics_anchor("vertical_bottom_to_top", "bottom") == (0.0, 0.5)
    assert rotated_text_alignment("vertical_bottom_to_top", "top") == "right"
    assert rotated_text_alignment("vertical_bottom_to_top", "bottom") == "left"


def test_vertical_top_to_bottom_anchors_whole_label_inside_interval() -> None:
    assert text_graphics_anchor("vertical_top_to_bottom", "top") == (0.0, 0.5)
    assert text_graphics_anchor("vertical_top_to_bottom", "center") == (0.5, 0.5)
    assert text_graphics_anchor("vertical_top_to_bottom", "bottom") == (1.0, 0.5)
    assert rotated_text_alignment("vertical_top_to_bottom", "top") == "left"
    assert rotated_text_alignment("vertical_top_to_bottom", "bottom") == "right"


def test_horizontal_anchor_uses_original_vertical_axis() -> None:
    assert text_graphics_anchor("horizontal", "top") == (0.5, 0.0)
    assert text_graphics_anchor("horizontal", "center") == (0.5, 0.5)
    assert text_graphics_anchor("horizontal", "bottom") == (0.5, 1.0)
