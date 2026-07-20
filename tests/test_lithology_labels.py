from geoworkbench.tablet.lithology_labels import lithology_label_is_visible


def test_lithology_label_visibility_depends_on_projected_height() -> None:
    assert lithology_label_is_visible(100.0, 110.0, 0.0, 200.0, 400, minimum_pixels=16)
    assert not lithology_label_is_visible(100.0, 101.0, 0.0, 200.0, 400, minimum_pixels=16)
    assert not lithology_label_is_visible(300.0, 310.0, 0.0, 200.0, 400, minimum_pixels=16)
