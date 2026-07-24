from geoworkbench.ui.interval_overlay_geometry import (
    constrain_overlay_geometry,
    right_anchored_overlay_geometry,
)


def test_right_anchored_overlay_never_crosses_parent_edges() -> None:
    geometry = right_anchored_overlay_geometry(
        parent_width=1920,
        parent_height=1009,
        preferred_width=390,
        preferred_height=880,
    )
    assert geometry.x >= 8
    assert geometry.y >= 8
    assert geometry.right <= 1912
    assert geometry.bottom <= 1001


def test_overlay_shrinks_when_parent_is_smaller_than_normal_minimum() -> None:
    geometry = constrain_overlay_geometry(
        parent_width=300,
        parent_height=240,
        requested_x=1700,
        requested_y=800,
        requested_width=430,
        requested_height=900,
    )
    assert geometry == type(geometry)(x=8, y=8, width=284, height=224)


def test_user_moved_overlay_is_clamped_not_reanchored() -> None:
    geometry = constrain_overlay_geometry(
        parent_width=1200,
        parent_height=800,
        requested_x=120,
        requested_y=95,
        requested_width=360,
        requested_height=600,
    )
    assert geometry.x == 120
    assert geometry.y == 95
    assert geometry.width == 360
    assert geometry.height == 600


def test_negative_and_far_right_positions_are_clamped() -> None:
    left = constrain_overlay_geometry(
        parent_width=1000,
        parent_height=700,
        requested_x=-500,
        requested_y=-100,
        requested_width=350,
        requested_height=500,
    )
    right = constrain_overlay_geometry(
        parent_width=1000,
        parent_height=700,
        requested_x=5000,
        requested_y=5000,
        requested_width=350,
        requested_height=500,
    )
    assert (left.x, left.y) == (8, 8)
    assert right.right == 992
    assert right.bottom == 692


def test_parent_shrink_only_clamps_manual_position_without_right_reanchor() -> None:
    geometry = constrain_overlay_geometry(
        parent_width=760,
        parent_height=520,
        requested_x=420,
        requested_y=210,
        requested_width=360,
        requested_height=420,
    )
    assert geometry.width == 360
    assert geometry.height == 420
    assert geometry.right == 752
    assert geometry.bottom == 512
    assert geometry.x != 760 - 8 - 370
