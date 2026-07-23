from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from geoworkbench.domain.models import Dataset, IndexRole, IndexType, Well
from geoworkbench.domain.operational_events import (
    OperationalEvent,
    OperationalEventKind,
    parse_operational_timestamp,
)
from geoworkbench.services.report_definition import (
    ReportBoundary,
    ReportSectionKind,
    ResolvedReportDefinition,
)


class OperationalEventReportError(RuntimeError):
    """Raised when events cannot be projected onto a resolved report index."""


@dataclass(frozen=True, slots=True)
class OperationalEventReportRecord:
    event: OperationalEvent
    index_value: ReportBoundary


@dataclass(frozen=True, slots=True)
class ResolvedOperationalEventReport:
    definition_id: str
    index_id: str
    start: ReportBoundary
    end: ReportBoundary
    records: tuple[OperationalEventReportRecord, ...]

    @property
    def event_ids(self) -> tuple[str, ...]:
        return tuple(record.event.event_id for record in self.records)


def resolve_operational_event_report(
    well: Well,
    dataset: Dataset,
    resolved: ResolvedReportDefinition,
) -> ResolvedOperationalEventReport:
    """Select events using the exact already-resolved ReportDefinition interval."""

    if dataset.dataset_id != resolved.definition.dataset_id:
        raise OperationalEventReportError("ResolvedReportDefinition относится к другому dataset")
    try:
        index = dataset.indexes[resolved.interval.index_id]
    except KeyError as exc:
        raise OperationalEventReportError("Индекс resolved report не найден в dataset") from exc

    included_kinds = _included_event_kinds(resolved)
    if not included_kinds:
        return ResolvedOperationalEventReport(
            definition_id=resolved.definition.definition_id,
            index_id=index.index_id,
            start=resolved.interval.start,
            end=resolved.interval.end,
            records=(),
        )

    start_key = _boundary_key(index.index_type, resolved.interval.start)
    end_key = _boundary_key(index.index_type, resolved.interval.end)
    records: list[OperationalEventReportRecord] = []
    for event in well.operational_events.values():
        if event.kind not in included_kinds:
            continue
        index_value = _event_index_value(event, index.index_type, index.role)
        if index_value is None:
            continue
        event_key = _boundary_key(index.index_type, index_value)
        if start_key <= event_key <= end_key:
            records.append(OperationalEventReportRecord(event, index_value))
    records.sort(
        key=lambda item: (
            _boundary_key(index.index_type, item.index_value),
            item.event.event_id,
        )
    )
    return ResolvedOperationalEventReport(
        definition_id=resolved.definition.definition_id,
        index_id=index.index_id,
        start=resolved.interval.start,
        end=resolved.interval.end,
        records=tuple(records),
    )


def _included_event_kinds(resolved: ResolvedReportDefinition) -> set[OperationalEventKind]:
    result: set[OperationalEventKind] = set()
    for section in resolved.definition.sections:
        if not section.enabled:
            continue
        if section.kind is ReportSectionKind.DRILLING:
            result.add(OperationalEventKind.DRILLING)
            continue
        if section.kind is not ReportSectionKind.EVENTS:
            continue
        options = dict(section.options)
        raw_kinds = options.get("event_kinds")
        if raw_kinds is None:
            result.update(OperationalEventKind)
            continue
        for raw_kind in raw_kinds.split(","):
            normalized = raw_kind.strip()
            if not normalized:
                continue
            try:
                result.add(OperationalEventKind(normalized))
            except ValueError as exc:
                raise OperationalEventReportError(
                    f"Неизвестный event kind в ReportDefinition: {normalized}"
                ) from exc
    return result


def _event_index_value(
    event: OperationalEvent,
    index_type: IndexType,
    index_role: IndexRole,
) -> ReportBoundary | None:
    if index_type is IndexType.DATETIME:
        if event.measured_at is None:
            return None
        timestamp = parse_operational_timestamp(event.measured_at).replace(tzinfo=None)
        return timestamp.isoformat(timespec="microseconds")
    if index_role is IndexRole.DEPTH:
        return event.depth_m
    if index_role is IndexRole.TIME:
        return event.elapsed_time_s
    return None


def _boundary_key(index_type: IndexType, value: ReportBoundary) -> int | float:
    if index_type is IndexType.DATETIME:
        return int(np.datetime64(str(value), "ns").astype(np.int64))
    return float(value)
