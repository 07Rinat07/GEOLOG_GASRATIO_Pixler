from geoworkbench.ui.interval_overlay_geometry import (
    OverlayRect,
    calculate_interval_statistics_overlay_geometry,
)


def test_overlay_stays_inside_full_hd_screen_when_main_window_is_too_wide() -> None:
    geometry = calculate_interval_statistics_overlay_geometry(
        main_window=OverlayRect(1920, 23, 2058, 1009),
        available_screen=OverlayRect(1920, 0, 1920, 1040),
        preferred_width=390,
        preferred_height=720,
    )

    assert geometry.x >= 1930
    assert geometry.y >= 10
    assert geometry.right <= 3830
    assert geometry.bottom <= 1030


def test_overlay_can_overlap_main_window_without_expanding_it() -> None:
    main = OverlayRect(0, 0, 1366, 728)
    geometry = calculate_interval_statistics_overlay_geometry(
        main_window=main,
        available_screen=main,
        preferred_width=380,
        preferred_height=680,
    )

    assert geometry.width <= main.width
    assert geometry.height <= main.height
    assert geometry.x > main.x
    assert geometry.right <= main.right
    assert geometry.bottom <= main.bottom


def test_overlay_shrinks_on_very_small_work_area() -> None:
    geometry = calculate_interval_statistics_overlay_geometry(
        main_window=OverlayRect(0, 0, 640, 420),
        available_screen=OverlayRect(0, 0, 640, 420),
        preferred_width=390,
        preferred_height=720,
    )

    assert geometry.width == 390
    assert geometry.height == 400
    assert geometry.x >= 10
    assert geometry.y >= 10
    assert geometry.right <= 630
    assert geometry.bottom <= 410
