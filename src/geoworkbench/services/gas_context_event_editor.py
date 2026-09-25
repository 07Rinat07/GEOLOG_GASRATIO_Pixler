from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from geoworkbench.domain.gas_context_events import (
    GasContextEvent,
    GasContextEventType,
    GasContextRegistry,
    InterpretationImpact,
)
from geoworkbench.project.session import ProjectSession


class GasContextEventEditorError(RuntimeError):
    """Raised when the editor cannot bind to an active well."""


class GasContextEventEditorController:
    """Transactional editor boundary for one well's gas-context registry.

    UI mutations are applied to an immutable working registry first. The active
    project is changed only by :meth:`commit`, so closing the dialog with
    Cancel cannot leave a partially edited registry behind.
    """

    def __init__(self, session: ProjectSession) -> None:
        self.session = session
        well = session.current_well
        if well is None:
            raise GasContextEventEditorError(
                "Для редактирования газовых событий сначала выберите скважину"
            )
        self._well_id = well.well_id
        dataset = session.current_dataset
        self._depth_domain = dataset.depth_domain if dataset is not None else None
        self._initial = GasContextRegistry(tuple(well.gas_context_events))
        self._working = self._initial

    @property
    def changed(self) -> bool:
        return self._working.events != self._initial.events

    @property
    def registry(self) -> GasContextRegistry:
        return self._working

    def list_events(self) -> tuple[GasContextEvent, ...]:
        return tuple(
            sorted(
                self._working.events,
                key=lambda item: (
                    item.top_depth,
                    item.bottom_depth,
                    item.event_type.value,
                    item.event_id,
                ),
            )
        )

    def get(self, event_id: str) -> GasContextEvent:
        for event in self._working.events:
            if event.event_id == event_id:
                return event
        raise KeyError(event_id)

    def add(
        self,
        *,
        event_type: GasContextEventType,
        top_depth: float,
        bottom_depth: float,
        impact: InterpretationImpact | None = None,
        confirmed: bool = True,
        reported_total_gas: float | None = None,
        reported_unit: str | None = None,
        comment: str = "",
        source: str = "manual",
    ) -> GasContextEvent:
        if self._depth_domain is None:
            raise GasContextEventEditorError(
                "Для нового газового события сначала выберите набор данных с системой координат"
            )
        event = GasContextEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            top_depth=top_depth,
            bottom_depth=bottom_depth,
            depth_domain=self._depth_domain,
            impact=impact,
            confirmed=confirmed,
            reported_total_gas=reported_total_gas,
            reported_unit=reported_unit,
            comment=comment,
            source=source,
        )
        self._working = self._working.add(event)
        return event

    def update(
        self,
        event_id: str,
        *,
        event_type: GasContextEventType,
        top_depth: float,
        bottom_depth: float,
        impact: InterpretationImpact | None = None,
        confirmed: bool = True,
        reported_total_gas: float | None = None,
        reported_unit: str | None = None,
        comment: str = "",
    ) -> GasContextEvent:
        current = self.get(event_id)
        replacement = replace(
            current,
            event_type=event_type,
            top_depth=top_depth,
            bottom_depth=bottom_depth,
            depth_domain=current.depth_domain or self._depth_domain,
            impact=impact,
            confirmed=confirmed,
            reported_total_gas=reported_total_gas,
            reported_unit=reported_unit,
            comment=comment,
        )
        self._working = self._working.replace(replacement)
        return replacement

    def duplicate(self, event_id: str) -> GasContextEvent:
        current = self.get(event_id)
        duplicate = replace(current, event_id=str(uuid4()))
        self._working = self._working.add(duplicate)
        return duplicate

    def remove(self, event_id: str) -> GasContextEvent:
        current = self.get(event_id)
        self._working = self._working.remove(event_id)
        return current

    def commit(self) -> bool:
        well = self.session.project.wells.get(self._well_id)
        if well is None or self.session.current_well_id != self._well_id:
            raise GasContextEventEditorError(
                "Активная скважина изменилась во время редактирования газовых событий"
            )
        if not self.changed:
            return False
        # Revalidate the complete collection before replacing persisted state.
        validated = GasContextRegistry(tuple(self._working.events))
        well.gas_context_events = list(validated.events)
        self._initial = validated
        self._working = validated
        self.session.dirty = True
        return True

    def reset(self) -> None:
        self._working = self._initial


__all__ = [
    "GasContextEventEditorController",
    "GasContextEventEditorError",
]
