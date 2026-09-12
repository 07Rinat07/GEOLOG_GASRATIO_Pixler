from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum

from geoworkbench.domain.models import CanvasObject, Well
from geoworkbench.project.session import ProjectSession


class CanvasObjectTransferError(ValueError):
    """Raised when an authored canvas transfer cannot be reviewed or applied safely."""


class CanvasObjectCollisionPolicy(StrEnum):
    """Explicit policy for object-ID collisions in the destination well."""

    ERROR = "error"
    SKIP = "skip"
    RENAME = "rename"


class CanvasObjectTransferAction(StrEnum):
    COPY = "copy"
    SKIP = "skip"
    RENAME = "rename"


@dataclass(frozen=True, slots=True)
class CanvasObjectTransferItem:
    source_object_id: str
    target_object_id: str
    object_type: str
    action: CanvasObjectTransferAction


@dataclass(frozen=True, slots=True)
class CanvasObjectTransferPlan:
    """Immutable review summary for one source-well to target-well transfer."""

    source_well_id: str
    target_well_id: str
    source_well_revision: int
    target_well_revision: int
    collision_policy: CanvasObjectCollisionPolicy
    items: tuple[CanvasObjectTransferItem, ...]

    @property
    def copy_count(self) -> int:
        return sum(item.action is not CanvasObjectTransferAction.SKIP for item in self.items)

    @property
    def skipped_count(self) -> int:
        return sum(item.action is CanvasObjectTransferAction.SKIP for item in self.items)

    @property
    def collision_count(self) -> int:
        return sum(
            item.action in {CanvasObjectTransferAction.SKIP, CanvasObjectTransferAction.RENAME}
            for item in self.items
        )


@dataclass(frozen=True, slots=True)
class CanvasObjectTransferOutcome:
    plan: CanvasObjectTransferPlan
    copied_object_ids: tuple[str, ...]
    skipped_object_ids: tuple[str, ...]


class CanvasObjectTransferController:
    """Preview and atomically copy authored canvas objects between wells.

    ``CanvasObject`` is well-level authored state. The transfer deliberately does
    not infer a dataset mapping or rewrite track/parameter references. A preview
    authorizes one exact source/target canvas state and is consumed on every apply
    attempt, including no-op and failure paths.
    """

    def __init__(self, session: ProjectSession) -> None:
        self.session = session
        self._plan: CanvasObjectTransferPlan | None = None
        self._source_snapshot: tuple[CanvasObject, ...] | None = None
        self._target_snapshot: tuple[CanvasObject, ...] | None = None
        self._selected_snapshot: tuple[CanvasObject, ...] | None = None

    def available_source_wells(self, target_well_id: str) -> tuple[Well, ...]:
        self._well(target_well_id)
        return tuple(
            sorted(
                (
                    well
                    for well in self.session.project.wells.values()
                    if well.well_id != target_well_id and well.canvas_objects
                ),
                key=lambda well: (well.name.casefold(), well.well_id),
            )
        )

    def analyze(
        self,
        source_well_id: str,
        target_well_id: str,
        *,
        object_ids: tuple[str, ...] | None = None,
        collision_policy: CanvasObjectCollisionPolicy = CanvasObjectCollisionPolicy.ERROR,
    ) -> CanvasObjectTransferPlan:
        """Build a non-mutating transfer plan for all or explicitly selected objects."""

        self.reset_state()
        source = self._well(source_well_id)
        target = self._well(target_well_id)
        if source is target:
            raise CanvasObjectTransferError("Источник и приёмник рисунков должны быть разными скважинами")
        if not isinstance(collision_policy, CanvasObjectCollisionPolicy):
            raise CanvasObjectTransferError("Неизвестная политика конфликта рисунков")

        source_by_id = self._unique_objects(source, label="источнике")
        target_by_id = self._unique_objects(target, label="приёмнике")
        selected = self._select_source_objects(source, source_by_id, object_ids)
        occupied = set(target_by_id)
        items: list[CanvasObjectTransferItem] = []

        for item in selected:
            target_id = item.object_id
            action = CanvasObjectTransferAction.COPY
            if target_id in occupied:
                if collision_policy is CanvasObjectCollisionPolicy.ERROR:
                    raise CanvasObjectTransferError(
                        f"Рисунок с ID уже существует в скважине-приёмнике: {target_id}"
                    )
                if collision_policy is CanvasObjectCollisionPolicy.SKIP:
                    action = CanvasObjectTransferAction.SKIP
                else:
                    target_id = _next_copy_id(target_id, occupied)
                    action = CanvasObjectTransferAction.RENAME
            if action is not CanvasObjectTransferAction.SKIP:
                occupied.add(target_id)
            items.append(
                CanvasObjectTransferItem(
                    source_object_id=item.object_id,
                    target_object_id=target_id,
                    object_type=item.object_type,
                    action=action,
                )
            )

        plan = CanvasObjectTransferPlan(
            source_well_id=source.well_id,
            target_well_id=target.well_id,
            source_well_revision=source.content_revision,
            target_well_revision=target.content_revision,
            collision_policy=collision_policy,
            items=tuple(items),
        )
        self._plan = plan
        self._source_snapshot = _snapshot(source.canvas_objects)
        self._target_snapshot = _snapshot(target.canvas_objects)
        self._selected_snapshot = _snapshot(selected)
        return plan

    def apply(self, plan: CanvasObjectTransferPlan) -> CanvasObjectTransferOutcome:
        """Apply exactly one reviewed plan without overwriting destination objects."""

        try:
            if (
                self._plan != plan
                or self._source_snapshot is None
                or self._target_snapshot is None
                or self._selected_snapshot is None
            ):
                raise CanvasObjectTransferError("Сначала повторно просмотрите перенос рисунков")

            source = self._well(plan.source_well_id)
            target = self._well(plan.target_well_id)
            if (
                source.content_revision != plan.source_well_revision
                or _snapshot(source.canvas_objects) != self._source_snapshot
            ):
                raise CanvasObjectTransferError(
                    "Рисунки или ревизия скважины-источника изменились; повторите просмотр"
                )
            if (
                target.content_revision != plan.target_well_revision
                or _snapshot(target.canvas_objects) != self._target_snapshot
            ):
                raise CanvasObjectTransferError(
                    "Рисунки или ревизия скважины-приёмника изменились; повторите просмотр"
                )

            selected_by_id = {item.object_id: item for item in self._selected_snapshot}
            copies: list[CanvasObject] = []
            skipped: list[str] = []
            for item in plan.items:
                source_object = selected_by_id.get(item.source_object_id)
                if source_object is None:
                    raise CanvasObjectTransferError(
                        f"Рисунок из подтверждённого плана отсутствует: {item.source_object_id}"
                    )
                if item.action is CanvasObjectTransferAction.SKIP:
                    skipped.append(item.source_object_id)
                    continue
                copied = deepcopy(source_object)
                copied.object_id = item.target_object_id
                copies.append(copied)

            original_objects = list(target.canvas_objects)
            original_revision = target.content_revision
            original_dirty = self.session.dirty
            try:
                if copies:
                    target.canvas_objects.extend(copies)
                    target.content_revision += 1
                    self.session.dirty = True
            except Exception:
                target.canvas_objects[:] = original_objects
                target.content_revision = original_revision
                self.session.dirty = original_dirty
                raise

            return CanvasObjectTransferOutcome(
                plan=plan,
                copied_object_ids=tuple(item.object_id for item in copies),
                skipped_object_ids=tuple(skipped),
            )
        finally:
            self.reset_state()

    def reset_state(self) -> None:
        self._plan = None
        self._source_snapshot = None
        self._target_snapshot = None
        self._selected_snapshot = None

    def _well(self, well_id: str) -> Well:
        if not isinstance(well_id, str) or not well_id.strip():
            raise CanvasObjectTransferError("ID скважины не должен быть пустым")
        try:
            return self.session.project.wells[well_id]
        except KeyError as exc:
            raise CanvasObjectTransferError(f"Скважина не найдена: {well_id}") from exc

    @staticmethod
    def _unique_objects(well: Well, *, label: str) -> dict[str, CanvasObject]:
        by_id: dict[str, CanvasObject] = {}
        for item in well.canvas_objects:
            if not isinstance(item, CanvasObject):
                raise CanvasObjectTransferError(
                    f"Некорректный объект пользовательского слоя в {label}"
                )
            object_id = item.object_id.strip() if isinstance(item.object_id, str) else ""
            if not object_id:
                raise CanvasObjectTransferError(f"Пустой ID рисунка в {label}")
            if object_id in by_id:
                raise CanvasObjectTransferError(
                    f"Неоднозначный ID рисунка в {label}: {object_id}"
                )
            by_id[object_id] = item
        return by_id

    @staticmethod
    def _select_source_objects(
        source: Well,
        source_by_id: dict[str, CanvasObject],
        object_ids: tuple[str, ...] | None,
    ) -> tuple[CanvasObject, ...]:
        if object_ids is None:
            selected = tuple(source.canvas_objects)
        else:
            if not isinstance(object_ids, tuple):
                raise CanvasObjectTransferError("Список рисунков должен быть tuple")
            if len(set(object_ids)) != len(object_ids):
                raise CanvasObjectTransferError("Список рисунков содержит повторяющиеся ID")
            missing = [object_id for object_id in object_ids if object_id not in source_by_id]
            if missing:
                raise CanvasObjectTransferError(
                    "Рисунок отсутствует в скважине-источнике: " + ", ".join(missing)
                )
            requested = set(object_ids)
            selected = tuple(item for item in source.canvas_objects if item.object_id in requested)
        if not selected:
            raise CanvasObjectTransferError("В скважине-источнике нет выбранных рисунков")
        return selected


def _snapshot(items: list[CanvasObject] | tuple[CanvasObject, ...]) -> tuple[CanvasObject, ...]:
    return tuple(deepcopy(item) for item in items)


def _next_copy_id(source_id: str, occupied: set[str]) -> str:
    candidate = f"{source_id}-copy"
    suffix = 2
    while candidate in occupied:
        candidate = f"{source_id}-copy-{suffix}"
        suffix += 1
    return candidate
