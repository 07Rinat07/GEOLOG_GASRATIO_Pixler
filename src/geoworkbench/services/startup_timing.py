from __future__ import annotations

DEFAULT_SPLASH_MINIMUM_VISIBLE_MS = 3_000


def remaining_splash_delay_ms(*, minimum_visible_ms: int, elapsed_ms: int) -> int:
    """Return the non-negative delay required to honour splash visibility.

    The helper is Qt-independent so startup timing can be verified in headless
    environments. Booleans are rejected explicitly because ``bool`` is a
    subclass of ``int`` in Python and would otherwise silently become 0/1 ms.
    """

    if isinstance(minimum_visible_ms, bool) or not isinstance(minimum_visible_ms, int):
        raise TypeError("minimum_visible_ms must be an integer")
    if isinstance(elapsed_ms, bool) or not isinstance(elapsed_ms, int):
        raise TypeError("elapsed_ms must be an integer")
    if minimum_visible_ms < 0:
        raise ValueError("minimum_visible_ms must be non-negative")
    if elapsed_ms < 0:
        raise ValueError("elapsed_ms must be non-negative")
    return max(0, minimum_visible_ms - elapsed_ms)
