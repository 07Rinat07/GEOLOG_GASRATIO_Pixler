from PySide6.QtCore import QRect, QSize

from geoworkbench.ui.window_geometry import (
    adaptive_minimum_size,
    adaptive_window_geometry,
    constrain_window_geometry,
    fit_window_to_screen,
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



class _FakeScreen:
    def __init__(self, available: QRect) -> None:
        self._available = QRect(available)

    def availableGeometry(self) -> QRect:
        return QRect(self._available)


class _FakeWindow:
    def __init__(self, available: QRect) -> None:
        self._screen = _FakeScreen(available)
        self._geometry = QRect()
        self.minimum = QSize()

    def screen(self):
        return self._screen

    def parentWidget(self):
        return None

    def setMinimumSize(self, width: int, height: int) -> None:
        self.minimum = QSize(width, height)

    def setGeometry(self, rect: QRect) -> None:
        self._geometry = QRect(rect)

    def geometry(self) -> QRect:
        return QRect(self._geometry)

    def resize(self, size: QSize) -> None:
        self._geometry.setSize(size)


def test_fit_window_clamps_desktop_minimum_to_small_laptop_work_area() -> None:
    available = QRect(0, 0, 1280, 680)
    window = _FakeWindow(available)

    result = fit_window_to_screen(
        window,  # type: ignore[arg-type]
        preferred=QSize(1500, 900),
        minimum=QSize(1050, 650),
    )

    assert available.contains(result)
    assert window.geometry() == result
    assert window.minimum.width() <= result.width()
    assert window.minimum.height() <= result.height()
    assert result.height() < available.height()



def test_adaptive_minimum_can_shrink_below_480_logical_pixels() -> None:
    available = QRect(0, 0, 900, 430)

    minimum = adaptive_minimum_size(
        available,
        requested=QSize(640, 480),
        margin=12,
    )

    assert minimum.width() == 640
    assert minimum.height() == 406
    assert minimum.width() <= available.width()
    assert minimum.height() < 480
