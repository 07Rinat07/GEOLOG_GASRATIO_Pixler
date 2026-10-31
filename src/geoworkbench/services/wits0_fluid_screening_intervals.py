"""Source-bound, headless coalescing of *observed* WITS fluid-screening spans.

No depth/lag conversion, interpolation, reclassification or reservoir inference
takes place here. Callers supply actual coverage spans on one verified axis.
"""

from __future__ import annotations

import re
from hashlib import sha256

from collections.abc import Iterable
from dataclasses import dataclass, replace

from geoworkbench.acquisition.wits0_parser import (
    Wits0ParsedFrame,
    Wits0SequenceStatus,
)
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
    return _bind_verified_wits0_screening_row(
        session, record, axis=axis, screening=screening
    )


def _bind_verified_wits0_screening_row(
    session: AcquisitionSession,
    record: AcquisitionRecord,
    *,
    axis: Wits0GasContextAxis,
    screening: Wits0FluidScreeningProjection,
) -> Wits0FluidScreeningPoint:
    """Bind an already matched session row without a second list scan."""

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
    current = _bind_verified_wits0_screening_row(
        session, matches[0], axis=point.axis, screening=point.screening
    )
    if current != point:
        raise ValueError("screening point no longer matches its acquisition row")


def snapshot_wits0_fluid_screening_points(
    session: AcquisitionSession,
    points: Iterable[Wits0FluidScreeningPoint],
) -> tuple[Wits0FluidScreeningPoint, ...]:
    """Validate ordered observed points against one current acquisition session.

    Source record identity, typed coordinates and audit text must still match.
    Gaps in acquisition sequence and reverse MD travel remain measured facts;
    this function never invents a coverage span or continuity between points.
    The result is a point-only snapshot, not an atomic acquisition transaction.
    """

    if not isinstance(session, AcquisitionSession):
        raise TypeError("session must use AcquisitionSession")
    records_by_id: dict[str, AcquisitionRecord] = {}
    duplicate_record_ids: set[str] = set()
    for record in session.records:
        if record.record_id in records_by_id:
            duplicate_record_ids.add(record.record_id)
        else:
            records_by_id[record.record_id] = record

    identity = (session.well_id, session.session_id, session.dataset_schema.dataset_id)
    observed: list[Wits0FluidScreeningPoint] = []
    record_ids: set[str] = set()
    last_sequence = 0
    selected_axis: Wits0GasContextAxis | None = None
    for point in points:
        if not isinstance(point, Wits0FluidScreeningPoint):
            raise TypeError("points must use Wits0FluidScreeningPoint")
        if point.source_identity != identity:
            raise ValueError("screening point belongs to another acquisition source")
        if selected_axis is not None and point.axis is not selected_axis:
            raise ValueError("screening points cannot mix depth and elapsed-time axes")
        if point.record_id in record_ids:
            raise ValueError("screening point record IDs must not repeat")
        if point.sequence <= last_sequence:
            raise ValueError("screening point source sequence must increase strictly")
        if point.record_id in duplicate_record_ids or point.record_id not in records_by_id:
            raise ValueError("screening source row is missing or duplicated")
        current = _bind_verified_wits0_screening_row(
            session,
            records_by_id[point.record_id],
            axis=point.axis,
            screening=point.screening,
        )
        if current != point:
            raise ValueError("screening point no longer matches its acquisition row")
        record_ids.add(point.record_id)
        observed.append(point)
        last_sequence = point.sequence
        selected_axis = point.axis
    return tuple(observed)


@dataclass(frozen=True, slots=True)
class Wits0FluidScreeningAuditAnchor:
    """Typed metadata declared by a stored WITS0 acquisition row's audit text."""

    source_identity: tuple[str, str, str]
    record_id: str
    acquisition_sequence: int
    record_no: int
    sequence_status: Wits0SequenceStatus
    raw_sha256: str
    source_sequence_no: int | None


def inspect_wits0_fluid_screening_audit(
    session: AcquisitionSession,
    point: Wits0FluidScreeningPoint,
) -> Wits0FluidScreeningAuditAnchor:
    """Read a current row's canonical audit header, not its raw WITS bytes.

    A digest written in the acquisition audit text is only a *claimed* source
    hash. No source file is opened or hashed here; an audit header does not
    establish measured interval coverage or prove the fluid assessment.
    """

    verify_wits0_fluid_screening_point(session, point)
    fields = point.record_source.split(";")
    if len(fields) < 3:
        raise ValueError("WITS0 audit requires record, sequence-status and raw-sha256")
    record_match = re.fullmatch(r"wits0:record=([0-9]{2})", fields[0])
    if record_match is None:
        raise ValueError("WITS0 audit record number is malformed")
    status_text = fields[1].removeprefix("sequence-status=")
    if status_text == fields[1]:
        raise ValueError("WITS0 audit sequence-status is missing")
    try:
        sequence_status = Wits0SequenceStatus(status_text)
    except ValueError as exc:
        raise ValueError("WITS0 audit sequence-status is invalid") from exc
    hash_text = fields[2].removeprefix("raw-sha256=")
    if hash_text == fields[2] or re.fullmatch(r"[0-9a-fA-F]{64}", hash_text) is None:
        raise ValueError("WITS0 audit raw-sha256 must be a 64-digit hex digest")

    # The acquisition writer may append source-sequence, ref or QC metadata.
    # Never let extra fields override the three canonical header fields.
    reserved = ("wits0:record=", "sequence-status=", "raw-sha256=")
    if any(part.startswith(reserved) for part in fields[3:]):
        raise ValueError("WITS0 audit contains a duplicate canonical field")
    source_sequences = [
        part.removeprefix("source-sequence=")
        for part in fields[3:]
        if part.startswith("source-sequence=")
    ]
    if len(source_sequences) > 1:
        raise ValueError("WITS0 audit source-sequence must be unique")
    source_sequence_no: int | None = None
    if source_sequences:
        value = source_sequences[0]
        if re.fullmatch(r"[0-9]+", value) is None:
            raise ValueError("WITS0 audit source-sequence must be an integer")
        source_sequence_no = int(value)

    return Wits0FluidScreeningAuditAnchor(
        source_identity=point.source_identity,
        record_id=point.record_id,
        acquisition_sequence=point.sequence,
        record_no=int(record_match.group(1)),
        sequence_status=sequence_status,
        raw_sha256=hash_text,
        source_sequence_no=source_sequence_no,
    )


@dataclass(frozen=True, slots=True)
class Wits0FluidScreeningRawFrameMatch:
    """Observed raw bytes matched against one persisted WITS0 audit digest."""

    source_identity: tuple[str, str, str]
    record_id: str
    record_no: int
    raw_sha256: str
    source_sequence_no: int | None


def match_wits0_fluid_screening_raw_frame(
    session: AcquisitionSession,
    point: Wits0FluidScreeningPoint,
    frame: Wits0ParsedFrame,
) -> Wits0FluidScreeningRawFrameMatch:
    """Compare supplied frame bytes and parser metadata with stored WITS0 audit.

    This verifies the *supplied* frame bytes against the stored digest, but
    does not locate them in an original capture directory or independently
    authenticate the parsed metadata. It cannot establish coverage start/end.
    """

    anchor = inspect_wits0_fluid_screening_audit(session, point)
    if not isinstance(frame, Wits0ParsedFrame):
        raise TypeError("frame must use Wits0ParsedFrame")
    if not isinstance(frame.raw_frame, bytes) or not frame.raw_frame:
        raise ValueError("raw_frame must be non-empty bytes")
    digest = sha256(frame.raw_frame).hexdigest()
    if digest != anchor.raw_sha256.lower():
        raise ValueError("WITS0 raw frame SHA-256 differs from acquisition audit")
    if frame.record_no != anchor.record_no:
        raise ValueError("WITS0 raw frame record number differs from audit")
    if frame.sequence_status is not anchor.sequence_status:
        raise ValueError("WITS0 raw frame sequence status differs from audit")
    if frame.sequence_no != anchor.source_sequence_no:
        raise ValueError("WITS0 raw frame source sequence differs from audit")

    return Wits0FluidScreeningRawFrameMatch(
        source_identity=anchor.source_identity,
        record_id=anchor.record_id,
        record_no=anchor.record_no,
        raw_sha256=digest,
        source_sequence_no=anchor.source_sequence_no,
    )


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
    "snapshot_wits0_fluid_screening_points",
    "Wits0FluidScreeningAuditAnchor",
    "inspect_wits0_fluid_screening_audit",
    "Wits0FluidScreeningRawFrameMatch",
    "match_wits0_fluid_screening_raw_frame",
    "Wits0FluidScreeningSample",
    "coalesce_wits0_fluid_screening",
]
