from geoworkbench.tablet.header_geometry import (
    CURVE_HEADER_BOTTOM_CLEARANCE,
    CURVE_HEADER_MAX_VISIBLE_ROWS,
    CURVE_HEADER_ROW_HEIGHT,
    align_curve_header_band_height,
    curve_header_content_height,
    curve_header_overflows,
    curve_header_viewport_height,
)


def test_dense_header_viewport_contains_only_complete_rows() -> None:
    assert CURVE_HEADER_ROW_HEIGHT == 58
    assert CURVE_HEADER_MAX_VISIBLE_ROWS == 6
    assert curve_header_viewport_height(7) == 6 * CURVE_HEADER_ROW_HEIGHT
    assert curve_header_viewport_height(12) == 6 * CURVE_HEADER_ROW_HEIGHT
    assert curve_header_overflows(7) is True


def test_header_content_keeps_last_row_above_graph_boundary() -> None:
    assert curve_header_content_height(7) == (
        7 * CURVE_HEADER_ROW_HEIGHT + CURVE_HEADER_BOTTOM_CLEARANCE
    )
    assert curve_header_content_height(0) == 0


def test_synchronized_header_height_never_cuts_a_row_in_half() -> None:
    assert align_curve_header_band_height(360) == 348
    assert align_curve_header_band_height(320) == 290
    assert align_curve_header_band_height(174) == 174
    assert align_curve_header_band_height(0) == 0
