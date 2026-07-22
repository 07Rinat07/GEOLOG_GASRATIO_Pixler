from PySide6.QtCore import QRect, QSize

from geoworkbench.ui.window_geometry import (
    adaptive_window_geometry,
    constrain_window_geometry,
)


def test_adaptive_geometry_stays_inside_small_laptop_work_area() -> None:
    available = QRect(0, 0, 1366, 728)

    result = adaptive_window_geometry(available, preferred=QSize(1440, 900))

    assert available.contains(result)
    assert result.width() < available.width()
    assert result.height() < available.height()
    assert result.center() == available.center()


def test_adaptive_geometry_handles_monitor_with_negative_coordinates() -> None:
    available = QRect(-1920, 40, 1920, 1040)

    result = adaptive_window_geometry(available)

    assert available.contains(result)
    assert result.left() < 0
    assert result.center() == available.center()


def test_constrain_geometry_moves_and_shrinks_window_into_work_area() -> None:
    available = QRect(100, 50, 1024, 700)
    outside = QRect(900, 600, 1400, 900)

    result = constrain_window_geometry(outside, available, margin=12)

    assert available.contains(result)
    assert result.left() >= available.left() + 12
    assert result.top() >= available.top() + 12
    assert result.right() <= available.right() - 12
    assert result.bottom() <= available.bottom() - 12
