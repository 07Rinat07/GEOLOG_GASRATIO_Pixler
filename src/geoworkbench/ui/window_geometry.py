from __future__ import annotations

from PySide6.QtCore import QRect, QSize
from PySide6.QtWidgets import QApplication, QWidget


def adaptive_window_geometry(
    available: QRect,
    *,
    preferred: QSize = QSize(1440, 900),
    margin: int = 18,
) -> QRect:
    """Return a centred window rectangle fully contained in a screen work area."""

    if available.width() <= 0 or available.height() <= 0:
        return QRect(0, 0, 1280, 800)

    safe_margin = max(0, min(margin, (available.width() - 1) // 2, (available.height() - 1) // 2))
    safe = available.adjusted(safe_margin, safe_margin, -safe_margin, -safe_margin)
    width = min(preferred.width(), max(1, int(safe.width() * 0.96)))
    height = min(preferred.height(), max(1, int(safe.height() * 0.94)))
    x = safe.x() + (safe.width() - width) // 2
    y = safe.y() + (safe.height() - height) // 2
    return QRect(x, y, width, height)


def adaptive_minimum_size(
    available: QRect,
    *,
    requested: QSize = QSize(640, 480),
    margin: int = 12,
) -> QSize:
    """Clamp a requested top-level minimum to the monitor work area.

    Qt screen geometry is expressed in logical pixels.  At 150–175% Windows
    scaling a laptop can expose fewer than 480 logical vertical pixels, so a
    desktop-only minimum must never exceed the available work area.
    """

    if available.width() <= 0 or available.height() <= 0:
        return QSize(max(1, requested.width()), max(1, requested.height()))

    horizontal_margin = max(0, min(margin, (available.width() - 1) // 2))
    vertical_margin = max(0, min(margin, (available.height() - 1) // 2))
    width_cap = max(1, available.width() - 2 * horizontal_margin)
    height_cap = max(1, available.height() - 2 * vertical_margin)
    return QSize(
        min(max(1, requested.width()), width_cap),
        min(max(1, requested.height()), height_cap),
    )


def constrain_window_geometry(rect: QRect, available: QRect, *, margin: int = 8) -> QRect:
    """Clamp an existing window rectangle to a monitor, including negative coordinates."""

    if available.width() <= 0 or available.height() <= 0:
        return QRect(rect)

    safe_margin = max(0, min(margin, (available.width() - 1) // 2, (available.height() - 1) // 2))
    safe = available.adjusted(safe_margin, safe_margin, -safe_margin, -safe_margin)
    width = min(max(1, rect.width()), safe.width())
    height = min(max(1, rect.height()), safe.height())
    x = min(max(rect.x(), safe.left()), safe.right() - width + 1)
    y = min(max(rect.y(), safe.top()), safe.bottom() - height + 1)
    return QRect(x, y, width, height)


def fit_window_to_screen(
    window: QWidget,
    *,
    preferred: QSize,
    minimum: QSize = QSize(480, 320),
    margin: int = 12,
) -> QRect:
    """Fit a top-level widget inside the current monitor work area.

    availableGeometry() excludes task bars and docks and is already expressed
    in Qt logical pixels, so this remains correct under Windows HiDPI scaling.
    The requested minimum is clamped too, so a desktop-only minimum cannot
    push action buttons below a laptop work area.
    """

    parent = window.parentWidget()
    screen = parent.screen() if parent is not None else window.screen()
    if screen is None:
        screen = QApplication.primaryScreen()
    if screen is None:
        window.resize(preferred)
        return QRect(window.geometry())

    target = adaptive_window_geometry(
        screen.availableGeometry(),
        preferred=preferred,
        margin=margin,
    )
    window.setMinimumSize(
        min(max(1, minimum.width()), target.width()),
        min(max(1, minimum.height()), target.height()),
    )
    window.setGeometry(target)
    return target
