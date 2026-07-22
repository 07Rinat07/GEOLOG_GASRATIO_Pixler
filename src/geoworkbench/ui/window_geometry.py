from __future__ import annotations

from PySide6.QtCore import QRect, QSize


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
