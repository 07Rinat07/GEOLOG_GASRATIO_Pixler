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
    assert CURVE_HEADER_ROW_HEIGHT == 44
    assert CURVE_HEADER_MAX_VISIBLE_ROWS == 6
    expected = (
        CURVE_HEADER_MAX_VISIBLE_ROWS * CURVE_HEADER_ROW_HEIGHT
        + CURVE_HEADER_BOTTOM_CLEARANCE
    )
    assert curve_header_viewport_height(7) == expected
    assert curve_header_viewport_height(12) == expected
    assert curve_header_overflows(7) is True


def test_header_content_keeps_last_row_above_graph_boundary() -> None:
    assert curve_header_content_height(7) == (
        7 * CURVE_HEADER_ROW_HEIGHT + CURVE_HEADER_BOTTOM_CLEARANCE
    )
    assert curve_header_content_height(0) == 0


def test_synchronized_header_height_never_cuts_a_row_in_half() -> None:
    expected_by_request = {
        360: 8 * CURVE_HEADER_ROW_HEIGHT + CURVE_HEADER_BOTTOM_CLEARANCE,
        320: 8 * CURVE_HEADER_ROW_HEIGHT + CURVE_HEADER_BOTTOM_CLEARANCE,
        174: 4 * CURVE_HEADER_ROW_HEIGHT + CURVE_HEADER_BOTTOM_CLEARANCE,
        0: 0,
    }

    for requested, expected in expected_by_request.items():
        aligned = align_curve_header_band_height(requested)
        assert aligned == expected
        if aligned:
            assert aligned >= requested
            assert (
                aligned - CURVE_HEADER_BOTTOM_CLEARANCE
            ) % CURVE_HEADER_ROW_HEIGHT == 0


def test_complete_header_band_height_is_idempotent() -> None:
    for rows in range(1, 9):
        complete_height = (
            rows * CURVE_HEADER_ROW_HEIGHT + CURVE_HEADER_BOTTOM_CLEARANCE
        )
        assert align_curve_header_band_height(complete_height) == complete_height
