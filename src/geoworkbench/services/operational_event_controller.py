from __future__ import annotations

from dataclasses import replace

from geoworkbench.domain.models import Well
from geoworkbench.domain.operational_events import OperationalEvent, operational_event_sort_key
from geoworkbench.services.operational_event_qc import OperationalEventQcEvaluator


class OperationalEventConflictError(RuntimeError):
    """Raised when an event revision or identity changed outside the controller."""


class OperationalEventController:
    """Single mutation boundary for serialized operational events of one well."""

    def __init__(
        self,
        well: Well,
        *,
        qc_evaluator: OperationalEventQcEvaluator | None = None,
    ) -> None:
        self.well = well
        self._qc_evaluator = qc_evaluator or OperationalEventQcEvaluator()
        self._validate_collection()
        self._recalculate_qc()

    def create(self, event: OperationalEvent) -> OperationalEvent:
        self._validate_well(event)
        if event.event_id in self.well.operational_events:
            raise OperationalEventConflictError(f"Событие уже существует: {event.event_id}")
        if event.revision != 1:
            raise OperationalEventConflictError("Новое событие должно иметь revision=1")
        self.well.operational_events[event.event_id] = replace(event, qc_flags=())
        self._recalculate_qc()
        return self.well.operational_events[event.event_id]

    def update(
        self,
        event_id: str,
        replacement: OperationalEvent,
        *,
        expected_revision: int,
    ) -> OperationalEvent:
        current = self._required_event(event_id)
        if current.revision != expected_revision:
            raise OperationalEventConflictError(
                f"Revision conflict для {event_id}: expected {expected_revision}, "
                f"actual {current.revision}"
            )
        if replacement.event_id != event_id:
            raise OperationalEventConflictError("event_id нельзя изменять")
        self._validate_well(replacement)
        updated = replace(
            replacement,
            revision=current.revision + 1,
            qc_flags=(),
        )
        self.well.operational_events[event_id] = updated
        self._recalculate_qc()
        return self.well.operational_events[event_id]

    def remove(self, event_id: str, *, expected_revision: int | None = None) -> OperationalEvent:
        current = self._required_event(event_id)
        if expected_revision is not None and current.revision != expected_revision:
            raise OperationalEventConflictError(
                f"Revision conflict для {event_id}: expected {expected_revision}, "
                f"actual {current.revision}"
            )
        del self.well.operational_events[event_id]
        self._recalculate_qc()
        return current

    def get(self, event_id: str) -> OperationalEvent:
        return self._required_event(event_id)

    def list_events(self) -> tuple[OperationalEvent, ...]:
        return tuple(sorted(self.well.operational_events.values(), key=operational_event_sort_key))

    def _required_event(self, event_id: str) -> OperationalEvent:
        try:
            return self.well.operational_events[event_id]
        except KeyError as exc:
            raise KeyError(f"Неизвестное operational event: {event_id}") from exc

    def _validate_collection(self) -> None:
        for event_id, event in self.well.operational_events.items():
            if event_id != event.event_id:
                raise OperationalEventConflictError(
                    f"Ключ события {event_id} не совпадает с event_id {event.event_id}"
                )
            self._validate_well(event)

    def _validate_well(self, event: OperationalEvent) -> None:
        if event.well_id != self.well.well_id:
            raise OperationalEventConflictError(
                f"Событие {event.event_id} относится к другой скважине: {event.well_id}"
            )

    def _recalculate_qc(self) -> None:
        evaluated = self._qc_evaluator.evaluate(self.well.operational_events.values())
        self.well.operational_events = {
            event_id: replace(event, qc_flags=evaluated[event_id])
            for event_id, event in sorted(self.well.operational_events.items())
        }
