from __future__ import annotations

import pytest

from geoworkbench.tablet.camera import TabletCamera


def test_camera_clamps_pan_to_domain() -> None:
    camera = TabletCamera(0.0, 1000.0, 100.0, 300.0)
    assert camera.pan(-500.0) == pytest.approx((0.0, 200.0))
    assert camera.pan(2000.0) == pytest.approx((800.0, 1000.0))


def test_camera_zoom_keeps_cursor_anchor_stationary() -> None:
    camera = TabletCamera(0.0, 1000.0, 100.0, 300.0)
    top, bottom = camera.zoom(0.5, anchor=150.0)
    assert (top, bottom) == pytest.approx((125.0, 225.0))
    assert (150.0 - top) / (bottom - top) == pytest.approx(0.25)


def test_camera_home_end_and_go_to_preserve_span() -> None:
    camera = TabletCamera(0.0, 1000.0, 100.0, 300.0)
    assert camera.home() == pytest.approx((0.0, 200.0))
    assert camera.end() == pytest.approx((800.0, 1000.0))
    assert camera.go_to(500.0) == pytest.approx((400.0, 600.0))


def test_camera_domain_change_can_reset_to_full_range() -> None:
    camera = TabletCamera(0.0, 100.0, 20.0, 40.0)
    camera.set_domain(1000.0, 2000.0, preserve_window=False)
    assert camera.range == pytest.approx((1000.0, 2000.0))


def test_recommended_initial_depth_window_keeps_long_well_readable() -> None:
    from geoworkbench.tablet.camera import recommended_initial_range

    assert recommended_initial_range(47.2, 1622.4, unit="m") == pytest.approx(
        (47.2, 247.2)
    )


def test_recommended_initial_window_keeps_small_dataset_full() -> None:
    from geoworkbench.tablet.camera import recommended_initial_range

    assert recommended_initial_range(1000.0, 1220.0, unit="m") == pytest.approx(
        (1000.0, 1220.0)
    )


def test_recommended_time_window_respects_axis_units() -> None:
    from geoworkbench.tablet.camera import recommended_initial_span

    assert recommended_initial_span(10_000.0, is_time=True, unit="s") == 1800.0
    assert recommended_initial_span(300.0, is_time=True, unit="min") == 30.0
    assert recommended_initial_span(5.0, is_time=True, unit="h") == 0.5
