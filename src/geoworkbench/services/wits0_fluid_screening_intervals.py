"""Source-bound, headless coalescing of *observed* WITS fluid-screening spans.

No depth/lag conversion, interpolation, reclassification or reservoir inference
takes place here. Callers supply actual coverage spans on one verified axis.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace

from geoworkbench.domain.acquisition import (
    AcquisitionDataRowPayload,
    AcquisitionRecord,
    AcquisitionRecordKind,
    AcquisitionSession,
)
from geoworkbench.domain.models import DepthDomain, IndexRole, IndexType
from geoworkbench.services.wits0_fluid_screening import Wits0FluidScreeningProjection
from geoworkbench.services.wits0_manual_gas_context import (
    Wits0GasContextAxis,
    validate_gas_context_query,
)


def _validate_source_axis(source_key: str, axis: Wits0GasContextAxis) -> None:
    if not isinstance(source_key, str) or not source_key.strip():
        raise ValueError("source_key must be non-empty text")
    if not isinstance(axis, Wits0GasContextAxis):
        raise ValueError("axis must be Wits0GasContextAxis")


@dataclass(frozen=True, slots=True)
class Wits0FluidScreeningPoint:
    """One verified WITS0 acquisition row, NOT an inferred coverage interval."""

    source_identity: tuple[str, str, str]  # well, session, dataset
    record_id: str
    record_source: str
    sequence: int
    axis: Wits0GasContextAxis
    position: float
    screening: Wits0FluidScreeningProjection

    def __post_init__(self) -> None:
        if (
            not isinstance(self.source_identity, tuple)
            or len(self.source_identity) != 3
            or any(
                not isinstance(item, str) or not item.strip()
                for item in self.source_identity
            )
        ):
            raise ValueError(
                "source_identity must identify the well, session and dataset"
            )
        if not isinstance(self.record_id, str) or not self.record_id.strip():
            raise ValueError("record_id must be non-empty text")
        if not isinstance(self.record_source, str) or not self.record_source.startswith(
            "wits0:record="
        ):
            raise ValueError("record_source must identify a WITS0 acquisition row")
        if type(self.sequence) is not int or self.sequence < 1:
            raise ValueError("sequence must be a positive Python integer")
        validate_gas_context_query(axis=self.axis, value=self.position)
        if not isinstance(self.screening, Wits0FluidScreeningProjection):
            raise TypeError("screening must use Wits0FluidScreeningProjection")


def bind_wits0_fluid_screening_point(
    session: AcquisitionSession,
    record: AcquisitionRecord,
    *,
    axis: Wits0GasContextAxis,
    screening: Wits0FluidScreeningProjection,
) -> Wits0FluidScreeningPoint:
    """Bind a provisional label to an actual stored WITS0 row and its typed index.

    Only the selected record's existing coordinate is exposed. A single WITS0
    row does not prove a start/end coverage span; callers must not coalesce
    these points into intervals without independently verified coverage.
    """

    if not isinstance(session, AcquisitionSession) or not isinstance(
        record, AcquisitionRecord
    ):
        raise TypeError("session and record must use acquisition domain types")
    if not isinstance(axis, Wits0GasContextAxis):
        raise ValueError("axis must be Wits0GasContextAxis")
    if not isinstance(screening, Wits0FluidScreeningProjection):
        raise TypeError("screening must use Wits0FluidScreeningProjection")
    if not any(item is record for item in session.records):
        raise ValueError("record must belong to the supplied acquisition session")
    if record.kind is not AcquisitionRecordKind.DATA_ROW or not isinstance(
        record.payload, AcquisitionDataRowPayload
    ):
        raise ValueError("screening requires an acquisition data row")
    if not record.source.startswith("wits0:record="):
        raise ValueError("screening requires a WITS0 acquisition row")

    schema = session.dataset_schema
    index = next(
        (item for item in schema.indexes if item.index_id == schema.active_index_id),
        None,
    )
    if index is None:
        raise ValueError("active acquisition index is missing")
    if axis is Wits0GasContextAxis.DEPTH:
        compatible = (
            schema.depth_domain is DepthDomain.MD
            and index.index_type is IndexType.MD
            and index.role is IndexRole.DEPTH
            and index.unit == "m"
        )
    else:
        compatible = (
            schema.depth_domain is DepthDomain.TIME
            and index.index_type is IndexType.RELATIVE_TIME
            and index.role is IndexRole.TIME
            and index.unit == "s"
        )
    if not compatible:
        raise ValueError("acquisition index is not verified for the requested axis/unit")
    values = record.payload.indexes_dict()
    if schema.active_index_id not in values:
        raise ValueError("record is missing the verified active index")
    position = validate_gas_context_query(
        axis=axis, value=values[schema.active_index_id]
    )
    return Wits0FluidScreeningPoint(
        source_identity=(session.well_id, session.session_id, schema.dataset_id),
        record_id=record.record_id,
        record_source=record.source,
        sequence=record.sequence,
        axis=axis,
        position=position,
        screening=screening,
    )


def verify_wits0_fluid_screening_point(
    session: AcquisitionSession,
    point: Wits0FluidScreeningPoint,
) -> None:
    """Fail closed when the recorded WITS0 point no longer matches its source.

    This validates source-row identity, audit text and the active coordinate at
    the moment of the call. It does NOT certify the caller-supplied fluid label,
    acquire an atomic source snapshot or establish any coverage start/end.
    """

    if not isinstance(session, AcquisitionSession):
        raise TypeError("session must use AcquisitionSession")
    if not isinstance(point, Wits0FluidScreeningPoint):
        raise TypeError("point must use Wits0FluidScreeningPoint")
    current_identity = (
        session.well_id,
        session.session_id,
        session.dataset_schema.dataset_id,
    )
    if point.source_identity != current_identity:
        raise ValueError("screening point belongs to another acquisition source")
    matches = [
        record for record in session.records if record.record_id == point.record_id
    ]
    if len(matches) != 1:
        raise ValueError("screening source row is missing or duplicated")
    current = bind_wits0_fluid_screening_point(
        session, matches[0], axis=point.axis, screening=point.screening
    )
    if current != point:
        raise ValueError("screening point no longer matches its acquisition row")


@dataclass(frozen=True, slots=True)
class Wits0FluidScreeningSample:
    """One measured coverage span; depth is MD metres, elapsed time is seconds."""

    source_key: str
    axis: Wits0GasContextAxis
    start: float
    end: float
    sequence: int
    screening: Wits0FluidScreeningProjection

    def __post_init__(self) -> None:
        _validate_source_axis(self.source_key, self.axis)
        start = validate_gas_context_query(axis=self.axis, value=self.start)
        end = validate_gas_context_query(axis=self.axis, value=self.end)
        if end <= start:
            raise ValueError("screening coverage end must be greater than start")
        if type(self.sequence) is not int or self.sequence < 1:
            raise ValueError("sequence must be a positive Python integer")
        if not isinstance(self.screening, Wits0FluidScreeningProjection):
            raise TypeError("screening must use Wits0FluidScreeningProjection")


@dataclass(frozen=True, slots=True)
class Wits0FluidScreeningInterval:
    """Adjacent source observations with identical provisional interpretation."""

    source_key: str
    axis: Wits0GasContextAxis
    start: float
    end: float
    first_sequence: int
    last_sequence: int
    screening: Wits0FluidScreeningProjection

    @property
    def sample_count(self) -> int:
        return self.last_sequence - self.first_sequence + 1


def coalesce_wits0_fluid_screening(
    samples: Iterable[Wits0FluidScreeningSample],
    *,
    source_key: str,
    axis: Wits0GasContextAxis,
) -> tuple[Wits0FluidScreeningInterval, ...]:
    """Join only touching, consecutive observations from the *same* verified source.

    An explicit source/axis contract prevents mixing acquisition sessions or
    MD with elapsed time. Gaps and skipped source sequences remain separate;
    overlap, reordering, or a foreign source/axis fail closed. Equality is exact:
    no tolerance silently fills an unobserved span.
    """

    _validate_source_axis(source_key, axis)
    intervals: list[Wits0FluidScreeningInterval] = []
    last_end: float | None = None
    last_sequence = 0
    for sample in samples:
        if not isinstance(sample, Wits0FluidScreeningSample):
            raise TypeError("samples must use Wits0FluidScreeningSample")
        if sample.source_key != source_key or sample.axis is not axis:
            raise ValueError("screening sample does not match the requested source and axis")
        if sample.sequence <= last_sequence:
            raise ValueError("screening source sequences must increase strictly")
        if last_end is not None and sample.start < last_end:
            raise ValueError("screening coverage must be ordered and non-overlapping")

        if (
            intervals
            and sample.start == last_end
            and sample.sequence == last_sequence + 1
            and sample.screening == intervals[-1].screening
        ):
            intervals[-1] = replace(
                intervals[-1],
                end=sample.end,
                last_sequence=sample.sequence,
            )
        else:
            intervals.append(
                Wits0FluidScreeningInterval(
                    source_key=source_key,
                    axis=axis,
                    start=sample.start,
                    end=sample.end,
                    first_sequence=sample.sequence,
                    last_sequence=sample.sequence,
                    screening=sample.screening,
                )
            )
        last_end = sample.end
        last_sequence = sample.sequence

    return tuple(intervals)


__all__ = [
    "Wits0FluidScreeningInterval",
    "Wits0FluidScreeningPoint",
    "bind_wits0_fluid_screening_point",
    "verify_wits0_fluid_screening_point",
    "Wits0FluidScreeningSample",
    "coalesce_wits0_fluid_screening",
]
