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

def test_navigation_control_state_projects_partial_viewport_to_scrollbar() -> None:
    navigation = TabletNavigationCoordinator()

    state = navigation.control_state((0.0, 1000.0), (100.0, 300.0))

    assert state.enabled
    assert state.visible_span == pytest.approx(200.0)
    assert state.data_span == pytest.approx(1000.0)
    assert state.scrollbar_maximum == 1_000_000
    assert state.scrollbar_value == 125_000
    assert state.scrollbar_page_step == 200_000
    assert state.scrollbar_single_step == 20_000


def test_navigation_control_state_collapses_scrollbar_for_full_domain() -> None:
    navigation = TabletNavigationCoordinator()

    state = navigation.control_state((0.0, 1000.0), (0.0, 1000.0))

    assert state.enabled
    assert state.scrollbar_maximum == 0
    assert state.scrollbar_value == 0
    assert state.scrollbar_page_step == 1
    assert state.scrollbar_single_step == 1


def test_navigation_control_state_is_disabled_without_a_resolved_range() -> None:
    navigation = TabletNavigationCoordinator()

    assert not navigation.control_state(None, (0.0, 1.0)).enabled
    assert not navigation.control_state((0.0, 1.0), None).enabled


def test_scrollbar_projection_round_trips_visible_range_and_clamps_value() -> None:
    navigation = TabletNavigationCoordinator()
    bounds = (0.0, 1000.0)
    current = (100.0, 300.0)
    state = navigation.control_state(bounds, current)

    restored = navigation.range_from_scrollbar(
        bounds,
        current,
        state.scrollbar_value,
        state.scrollbar_maximum,
    )
    clamped = navigation.range_from_scrollbar(
        bounds,
        current,
        state.scrollbar_maximum + 500,
        state.scrollbar_maximum,
    )

    assert restored == pytest.approx(current)
    assert clamped == pytest.approx((800.0, 1000.0))


def test_scrollbar_projection_rejects_non_positive_maximum() -> None:
    navigation = TabletNavigationCoordinator()

    with pytest.raises(ValueError, match="maximum"):
        navigation.range_from_scrollbar((0.0, 100.0), (10.0, 20.0), 5, 0)

