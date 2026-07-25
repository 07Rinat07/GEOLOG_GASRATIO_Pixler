from geoworkbench.tablet.annotation_layout import LayoutRect, image_content_target


def test_catalog_symbol_uses_complete_resized_box_for_free_stretch() -> None:
    destination = LayoutRect(10, 20, 240, 60)

    assert image_content_target(
        100,
        100,
        destination,
        preserve_aspect=False,
    ) == destination


def test_normal_image_still_preserves_original_aspect_ratio() -> None:
    target = image_content_target(
        100,
        100,
        LayoutRect(10, 20, 240, 60),
        preserve_aspect=True,
    )

    assert target == LayoutRect(100, 20, 60, 60)
