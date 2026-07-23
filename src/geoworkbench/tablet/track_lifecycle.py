from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, TypeVar


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class TrackLifecyclePlan:
    """Difference between rendered and requested track topology."""

    ordered_ids: tuple[str, ...]
    retained_ids: tuple[str, ...]
    create_ids: tuple[str, ...]
    remove_ids: tuple[str, ...]
    reordered: bool

    @property
    def topology_changed(self) -> bool:
        return bool(self.create_ids or self.remove_ids)

    @property
    def can_reorder_in_place(self) -> bool:
        return not self.topology_changed


class TrackLifecycleCoordinator:
    """Plan track creation, disposal and stable in-place ordering.

    The coordinator is deliberately independent of Qt. Widget construction and
    destruction remain explicit adapter operations in ``TabletView``, while
    identity and ordering rules can be verified without creating a window.
    """

    def plan(
        self,
        existing_ids: tuple[str, ...],
        requested_ids: tuple[str, ...],
    ) -> TrackLifecyclePlan:
        self._validate_ids(existing_ids, "existing")
        self._validate_ids(requested_ids, "requested")
        existing = set(existing_ids)
        requested = set(requested_ids)
        retained = tuple(track_id for track_id in requested_ids if track_id in existing)
        created = tuple(track_id for track_id in requested_ids if track_id not in existing)
        removed = tuple(track_id for track_id in existing_ids if track_id not in requested)
        return TrackLifecyclePlan(
            ordered_ids=requested_ids,
            retained_ids=retained,
            create_ids=created,
            remove_ids=removed,
            reordered=existing_ids != requested_ids and existing == requested,
        )

    def reorder_retained(
        self,
        entries: Mapping[str, T],
        plan: TrackLifecyclePlan,
    ) -> dict[str, T]:
        if not plan.can_reorder_in_place:
            raise ValueError("Track topology changed; create or remove entries first")
        missing = [track_id for track_id in plan.ordered_ids if track_id not in entries]
        if missing:
            raise KeyError(missing[0])
        return {track_id: entries[track_id] for track_id in plan.ordered_ids}

    @staticmethod
    def _validate_ids(track_ids: tuple[str, ...], label: str) -> None:
        if any(not isinstance(track_id, str) or not track_id.strip() for track_id in track_ids):
            raise ValueError(f"{label} track ids must be non-empty strings")
        if len(set(track_ids)) != len(track_ids):
            raise ValueError(f"{label} track ids must be unique")
