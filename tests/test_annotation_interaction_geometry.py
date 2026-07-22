from geoworkbench.tablet.annotation_interaction import (
    keep_annotation_reachable,
    resize_annotation_geometry,
)


def test_resize_from_each_corner_keeps_opposite_corner_fixed() -> None:
    assert resize_annotation_geometry(10, 20, 100, 60, "se", 30, 15) == (
        10,
        20,
        130,
        75,
    )
    assert resize_annotation_geometry(10, 20, 100, 60, "nw", 15, 10) == (
        25,
        30,
        85,
        50,
    )
    assert resize_annotation_geometry(10, 20, 100, 60, "ne", 20, 5) == (
        10,
        25,
        120,
        55,
    )
    assert resize_annotation_geometry(10, 20, 100, 60, "sw", -10, 8) == (
        0,
        20,
        110,
        68,
    )


def test_resize_from_sides_and_minimum_size() -> None:
    assert resize_annotation_geometry(10, 20, 100, 60, "e", -200, 0) == (
        10,
        20,
        48,
        60,
    )
    assert resize_annotation_geometry(10, 20, 100, 60, "w", 200, 0) == (
        62,
        20,
        48,
        60,
    )
    assert resize_annotation_geometry(10, 20, 100, 60, "n", 0, 100) == (
        10,
        52,
        100,
        28,
    )


def test_free_position_keeps_a_draggable_margin_on_canvas() -> None:
    assert keep_annotation_reachable(
        100, 100, -500, -500, 200, 80, 800, 600
    ) == (-280, -160)
    assert keep_annotation_reachable(
        100, 100, 1000, 1000, 200, 80, 800, 600
    ) == (680, 480)
