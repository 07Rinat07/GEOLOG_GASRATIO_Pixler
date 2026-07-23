from __future__ import annotations

import pytest

from geoworkbench.tablet.track_lifecycle import TrackLifecycleCoordinator


def test_plan_separates_retained_created_and_removed_tracks() -> None:
    coordinator = TrackLifecycleCoordinator()

    plan = coordinator.plan(("depth", "gas", "rop"), ("depth", "rop", "lithology"))

    assert plan.retained_ids == ("depth", "rop")
    assert plan.create_ids == ("lithology",)
    assert plan.remove_ids == ("gas",)
    assert plan.topology_changed is True
    assert plan.can_reorder_in_place is False


def test_order_only_plan_reuses_existing_entries() -> None:
    coordinator = TrackLifecycleCoordinator()
    entries = {"depth": object(), "gas": object(), "rop": object()}
    plan = coordinator.plan(tuple(entries), ("gas", "rop", "depth"))

    reordered = coordinator.reorder_retained(entries, plan)

    assert tuple(reordered) == ("gas", "rop", "depth")
    assert reordered["gas"] is entries["gas"]
    assert reordered["rop"] is entries["rop"]
    assert reordered["depth"] is entries["depth"]
    assert plan.reordered is True


def test_topology_change_cannot_be_applied_as_order_only_update() -> None:
    coordinator = TrackLifecycleCoordinator()
    plan = coordinator.plan(("depth",), ("depth", "gas"))

    with pytest.raises(ValueError, match="topology changed"):
        coordinator.reorder_retained({"depth": object()}, plan)


@pytest.mark.parametrize(
    "track_ids",
    [("depth", "depth"), ("depth", "")],
)
def test_invalid_track_identity_is_rejected(track_ids: tuple[str, ...]) -> None:
    coordinator = TrackLifecycleCoordinator()

    with pytest.raises(ValueError):
        coordinator.plan((), track_ids)
