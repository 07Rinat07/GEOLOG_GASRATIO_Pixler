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


def test_create_entries_preserves_order_and_dispose_runs_in_reverse() -> None:
    coordinator = TrackLifecycleCoordinator()
    disposed: list[str] = []

    entries = coordinator.create_entries(
        ("depth", "gas", "rop"),
        identify=lambda track_id: track_id,
        create=lambda track_id: f"rendered:{track_id}",
    )
    released = coordinator.dispose_entries(entries, disposed.append)

    assert tuple(entries) == ("depth", "gas", "rop")
    assert released == ("depth", "gas", "rop")
    assert disposed == ["rendered:rop", "rendered:gas", "rendered:depth"]


def test_dispose_entries_settles_each_entry_before_disposing_the_next() -> None:
    events: list[tuple[str, str]] = []
    coordinator = TrackLifecycleCoordinator(
        settle_disposal=lambda entry: events.append(("settle", str(entry)))
    )
    entries = {
        "depth": "rendered:depth",
        "gas": "rendered:gas",
        "rop": "rendered:rop",
    }

    released = coordinator.dispose_entries(
        entries,
        lambda entry: events.append(("dispose", entry)),
    )

    assert released == ("depth", "gas", "rop")
    assert events == [
        ("dispose", "rendered:rop"),
        ("settle", "rendered:rop"),
        ("dispose", "rendered:gas"),
        ("settle", "rendered:gas"),
        ("dispose", "rendered:depth"),
        ("settle", "rendered:depth"),
    ]


def test_create_entries_rolls_back_partial_build() -> None:
    coordinator = TrackLifecycleCoordinator()
    disposed: list[str] = []

    def create(track_id: str) -> str:
        if track_id == "broken":
            raise RuntimeError("render failed")
        return f"rendered:{track_id}"

    with pytest.raises(RuntimeError, match="render failed"):
        coordinator.create_entries(
            ("depth", "broken"),
            identify=lambda track_id: track_id,
            create=create,
            rollback=disposed.append,
        )

    assert disposed == ["rendered:depth"]


def test_create_entries_settles_rolled_back_entries_before_reraising() -> None:
    events: list[tuple[str, str]] = []
    coordinator = TrackLifecycleCoordinator(
        settle_disposal=lambda entry: events.append(("settle", str(entry)))
    )

    def create(track_id: str) -> str:
        if track_id == "broken":
            raise RuntimeError("render failed")
        return f"rendered:{track_id}"

    with pytest.raises(RuntimeError, match="render failed"):
        coordinator.create_entries(
            ("depth", "broken"),
            identify=lambda track_id: track_id,
            create=create,
            rollback=lambda entry: events.append(("dispose", entry)),
        )

    assert events == [
        ("dispose", "rendered:depth"),
        ("settle", "rendered:depth"),
    ]



def test_disposal_failure_still_settles_before_the_next_track() -> None:
    events: list[str] = []
    entries = {"depth": "depth", "gas": "gas", "rop": "rop"}
    coordinator = TrackLifecycleCoordinator(
        settle_disposal=lambda entry: events.append(f"settle:{entry}")
    )

    def dispose(entry: str) -> None:
        events.append(f"dispose:{entry}")
        if entry == "gas":
            raise RuntimeError("widget cleanup failed after deleteLater")

    def report(track_id: str, exc: BaseException) -> None:
        events.append(f"error:{track_id}:{type(exc).__name__}")

    released = coordinator.dispose_entries(entries, dispose, on_error=report)

    assert released == ("depth", "gas", "rop")
    assert events == [
        "dispose:rop",
        "settle:rop",
        "dispose:gas",
        "error:gas:RuntimeError",
        "settle:gas",
        "dispose:depth",
        "settle:depth",
    ]


def test_failed_settlement_reports_error_without_skipping_remaining_tracks() -> None:
    events: list[str] = []
    entries = {"depth": "depth", "gas": "gas", "rop": "rop"}

    def settle(entry: object) -> None:
        events.append(f"settle:{entry}")
        if entry == "gas":
            raise ValueError("stale QObject wrapper")

    def report(track_id: str, exc: BaseException) -> None:
        events.append(f"error:{track_id}:{type(exc).__name__}")

    coordinator = TrackLifecycleCoordinator(settle_disposal=settle)
    released = coordinator.dispose_entries(
        entries,
        lambda entry: events.append(f"dispose:{entry}"),
        on_error=report,
    )

    assert released == ("depth", "gas", "rop")
    assert events == [
        "dispose:rop",
        "settle:rop",
        "dispose:gas",
        "settle:gas",
        "error:gas:ValueError",
        "dispose:depth",
        "settle:depth",
    ]



def test_partial_create_rollback_failure_keeps_original_error_and_settles_all() -> None:
    events: list[str] = []
    errors: list[tuple[str, str]] = []

    def create(track_id: str) -> str:
        if track_id == "broken":
            raise RuntimeError("render failed")
        return track_id

    def rollback(entry: str) -> None:
        events.append(f"rollback:{entry}")
        if entry == "gas":
            raise ValueError("cleanup failed after deleteLater")

    coordinator = TrackLifecycleCoordinator(
        settle_disposal=lambda entry: events.append(f"settle:{entry}")
    )
    with pytest.raises(RuntimeError, match="render failed"):
        coordinator.create_entries(
            ("depth", "gas", "broken"),
            identify=lambda track_id: track_id,
            create=create,
            rollback=rollback,
            on_rollback_error=lambda track_id, exc: errors.append(
                (track_id, type(exc).__name__)
            ),
        )

    assert events == [
        "rollback:gas",
        "settle:gas",
        "rollback:depth",
        "settle:depth",
    ]
    assert errors == [("gas", "ValueError")]


def test_partial_create_settlement_failure_still_rolls_back_prior_tracks() -> None:
    events: list[str] = []
    errors: list[tuple[str, str]] = []

    def create(track_id: str) -> str:
        if track_id == "broken":
            raise RuntimeError("render failed")
        return track_id

    def settle(entry: object) -> None:
        events.append(f"settle:{entry}")
        if entry == "gas":
            raise ValueError("stale Qt widget wrapper")

    coordinator = TrackLifecycleCoordinator(settle_disposal=settle)
    with pytest.raises(RuntimeError, match="render failed"):
        coordinator.create_entries(
            ("depth", "gas", "broken"),
            identify=lambda track_id: track_id,
            create=create,
            rollback=lambda entry: events.append(f"rollback:{entry}"),
            on_rollback_error=lambda track_id, exc: errors.append(
                (track_id, type(exc).__name__)
            ),
        )

    assert events == [
        "rollback:gas",
        "settle:gas",
        "rollback:depth",
        "settle:depth",
    ]
    assert errors == [("gas", "ValueError")]
