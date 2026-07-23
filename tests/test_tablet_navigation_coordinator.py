from __future__ import annotations

import pytest

from geoworkbench.tablet.navigation_coordinator import (
    NavigationCommand,
    TabletNavigationCoordinator,
)


def test_keyboard_commands_preserve_span_and_clamp_to_domain() -> None:
    navigation = TabletNavigationCoordinator()
    bounds = (0.0, 1000.0)
    current = (100.0, 300.0)

    assert navigation.navigate(
        bounds, current, NavigationCommand.PAGE_DOWN
    ) == pytest.approx((280.0, 480.0))
    assert navigation.navigate(bounds, current, NavigationCommand.HOME) == pytest.approx(
        (0.0, 200.0)
    )
    assert navigation.navigate(bounds, current, NavigationCommand.END) == pytest.approx(
        (800.0, 1000.0)
    )


def test_first_scroll_from_full_depth_domain_opens_readable_window() -> None:
    navigation = TabletNavigationCoordinator()

    assert navigation.scroll((0.0, 1000.0), (0.0, 1000.0), 1.0) == pytest.approx(
        (5.0, 55.0)
    )
    assert navigation.scroll((0.0, 1000.0), (0.0, 1000.0), -1.0) == pytest.approx(
        (945.0, 995.0)
    )


def test_zoom_keeps_requested_axis_anchor_stationary() -> None:
    navigation = TabletNavigationCoordinator()

    result = navigation.zoom(
        (0.0, 1000.0),
        (100.0, 300.0),
        0.5,
        anchor=150.0,
    )

    assert result == pytest.approx((125.0, 225.0))


@pytest.mark.parametrize(
    ("operation", "message"),
    [
        (lambda item: item.scroll((0.0, 1.0), (0.0, 1.0), 0.0), "steps"),
        (lambda item: item.zoom((0.0, 1.0), (0.0, 1.0), 0.0), "factor"),
        (lambda item: item.pan((0.0, 1.0), (0.0, 1.0), float("nan")), "delta"),
    ],
)
def test_invalid_navigation_commands_fail_at_headless_boundary(operation, message) -> None:
    navigation = TabletNavigationCoordinator()

    with pytest.raises(ValueError, match=message):
        operation(navigation)
