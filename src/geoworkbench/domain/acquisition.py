from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from math import isfinite
from typing import TypeAlias

from geoworkbench.domain.models import (
    CurveMetadata,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
)
from geoworkbench.domain.operational_events import OperationalEvent, parse_operational_timestamp


ACQUISITION_SCHEMA_VERSION = 1


class AcquisitionSessionState(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class AcquisitionRecordKind(StrEnum):
    DATA_ROW = "data_row"
    EVENT_UPSERT = "event_upsert"
    EVENT_DELETE = "event_delete"


@dataclass(frozen=True, slots=True)
class AcquisitionIndexSchema:
    index_id: str
    mnemonic: str
    index_type: IndexType
    role: IndexRole
    unit: str | None = None
    confidence: float = 1.0
    evidence: tuple[str, ...] = ()
    datetime_format: str | None = None
    timezone: str | None = None

    def __post_init__(self) -> None:
        _required_text(self.index_id, "index_id")
        _required_text(self.mnemonic, "mnemonic")
        if not isinstance(self.index_type, IndexType):
            raise ValueError("index_type должен использовать IndexType")
        if not isinstance(self.role, IndexRole):
            raise ValueError("role должен использовать IndexRole")
        _optional_text(self.unit, "unit")
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)):
            raise ValueError("confidence должен быть числом")
        if not isfinite(float(self.confidence)) or not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence должен находиться в диапазоне 0–1")
        if not isinstance(self.evidence, tuple) or not all(
            isinstance(item, str) for item in self.evidence
        ):
            raise ValueError("evidence должен быть tuple строк")
        _optional_text(self.datetime_format, "datetime_format")
        _optional_text(self.timezone, "timezone")

    @classmethod
    def from_index(cls, index: DatasetIndex) -> AcquisitionIndexSchema:
        return cls(
            index_id=index.index_id,
            mnemonic=index.mnemonic,
            index_type=index.index_type,
            role=index.role,
            unit=index.unit,
            confidence=index.confidence,
            evidence=index.evidence,
            datetime_format=index.datetime_format,
            timezone=index.timezone,
        )


@dataclass(frozen=True, slots=True)
class AcquisitionCurveSchema:
    metadata: CurveMetadata

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, CurveMetadata):
            raise ValueError("metadata должна использовать CurveMetadata")
        _required_text(self.metadata.curve_id, "curve_id")


@dataclass(frozen=True, slots=True)
class AcquisitionDatasetSchema:
    dataset_id: str
    name: str
    kind: DatasetKind
    depth_domain: DepthDomain
    indexes: tuple[AcquisitionIndexSchema, ...]
    active_index_id: str
    curves: tuple[AcquisitionCurveSchema, ...]
    schema_version: int = ACQUISITION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _required_text(self.dataset_id, "dataset_id")
        _required_text(self.name, "name")
        if not isinstance(self.kind, DatasetKind):
            raise ValueError("kind должен использовать DatasetKind")
        if not isinstance(self.depth_domain, DepthDomain):
            raise ValueError("depth_domain должен использовать DepthDomain")
        if self.schema_version != ACQUISITION_SCHEMA_VERSION:
            raise ValueError("Неподдерживаемая версия acquisition dataset schema")
        if not self.indexes:
            raise ValueError("Acquisition dataset schema требует хотя бы один индекс")
        index_ids = [item.index_id for item in self.indexes]
        curve_ids = [item.metadata.curve_id for item in self.curves]
        if len(set(index_ids)) != len(index_ids):
            raise ValueError("Индексы acquisition schema не должны повторяться")
        if len(set(curve_ids)) != len(curve_ids):
            raise ValueError("Кривые acquisition schema не должны повторяться")
        if self.active_index_id not in set(index_ids):
            raise ValueError("active_index_id отсутствует в acquisition schema")
        if any(item.metadata.source_dataset_id != self.dataset_id for item in self.curves):
            raise ValueError("Кривая acquisition schema относится к другому dataset")


@dataclass(frozen=True, slots=True)
class AcquisitionDataRowPayload:
    index_values: tuple[tuple[str, float | int], ...]
    curve_values: tuple[tuple[str, float | None], ...]

    def __post_init__(self) -> None:
        _validate_pairs(self.index_values, "index_values")
        _validate_pairs(self.curve_values, "curve_values")
        if len({key for key, _value in self.index_values}) != len(self.index_values):
            raise ValueError("index_values не должны содержать повторяющиеся ID")
        if len({key for key, _value in self.curve_values}) != len(self.curve_values):
            raise ValueError("curve_values не должны содержать повторяющиеся ID")
        for _index_id, value in self.index_values:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("Значение индекса должно быть числом")
            if not isfinite(float(value)):
                raise ValueError("Значение индекса должно быть конечным")
        for _curve_id, value in self.curve_values:
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("Значение кривой должно быть числом или None")
            if not isfinite(float(value)):
                raise ValueError("Значение кривой должно быть конечным")

    def indexes_dict(self) -> dict[str, float | int]:
        return dict(self.index_values)

    def curves_dict(self) -> dict[str, float | None]:
        return dict(self.curve_values)


@dataclass(frozen=True, slots=True)
class AcquisitionEventUpsertPayload:
    event: OperationalEvent
    expected_revision: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.event, OperationalEvent):
            raise ValueError("event должен использовать OperationalEvent")
        if self.expected_revision is None:
            if self.event.revision != 1:
                raise ValueError("Новое событие acquisition должно иметь revision=1")
            return
        if (
            isinstance(self.expected_revision, bool)
            or not isinstance(self.expected_revision, int)
            or self.expected_revision < 1
        ):
            raise ValueError("expected_revision должен быть положительным целым числом")
        if self.event.revision != self.expected_revision + 1:
            raise ValueError("Revision replacement должна быть expected_revision + 1")


@dataclass(frozen=True, slots=True)
class AcquisitionEventDeletePayload:
    event_id: str
    expected_revision: int

    def __post_init__(self) -> None:
        _required_text(self.event_id, "event_id")
        if (
            isinstance(self.expected_revision, bool)
            or not isinstance(self.expected_revision, int)
            or self.expected_revision < 1
        ):
            raise ValueError("expected_revision должен быть положительным целым числом")


AcquisitionRecordPayload: TypeAlias = (
    AcquisitionDataRowPayload
    | AcquisitionEventUpsertPayload
    | AcquisitionEventDeletePayload
)

_PAYLOAD_TYPE_BY_KIND: dict[AcquisitionRecordKind, type[AcquisitionRecordPayload]] = {
    AcquisitionRecordKind.DATA_ROW: AcquisitionDataRowPayload,
    AcquisitionRecordKind.EVENT_UPSERT: AcquisitionEventUpsertPayload,
    AcquisitionRecordKind.EVENT_DELETE: AcquisitionEventDeletePayload,
}


@dataclass(frozen=True, slots=True)
class AcquisitionRecord:
    record_id: str
    sequence: int
    kind: AcquisitionRecordKind
    payload: AcquisitionRecordPayload
    received_at: str
    source: str

    def __post_init__(self) -> None:
        _required_text(self.record_id, "record_id")
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 1
        ):
            raise ValueError("sequence должен быть положительным целым числом")
        if not isinstance(self.kind, AcquisitionRecordKind):
            raise ValueError("kind должен использовать AcquisitionRecordKind")
        expected = _PAYLOAD_TYPE_BY_KIND[self.kind]
        if not isinstance(self.payload, expected):
            raise ValueError("Payload acquisition record не соответствует kind")
        object.__setattr__(self, "received_at", canonical_acquisition_timestamp(self.received_at))
        _required_text(self.source, "source")


@dataclass(frozen=True, slots=True)
class AcquisitionCheckpoint:
    checkpoint_id: str
    sequence: int
    row_count: int
    dataset_digest: str
    events_digest: str
    audit_digest: str
    created_at: str

    def __post_init__(self) -> None:
        _required_text(self.checkpoint_id, "checkpoint_id")
        for value, name in ((self.sequence, "sequence"), (self.row_count, "row_count")):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} должен быть неотрицательным целым числом")
        for value, name in (
            (self.dataset_digest, "dataset_digest"),
            (self.events_digest, "events_digest"),
            (self.audit_digest, "audit_digest"),
        ):
            if not isinstance(value, str) or len(value) != 64:
                raise ValueError(f"{name} должен быть SHA-256 hex digest")
            try:
                int(value, 16)
            except ValueError as exc:
                raise ValueError(f"{name} должен быть SHA-256 hex digest") from exc
        object.__setattr__(self, "created_at", canonical_acquisition_timestamp(self.created_at))


@dataclass(slots=True)
class AcquisitionSession:
    session_id: str
    well_id: str
    dataset_schema: AcquisitionDatasetSchema
    records: list[AcquisitionRecord] = field(default_factory=list)
    checkpoints: list[AcquisitionCheckpoint] = field(default_factory=list)
    state: AcquisitionSessionState = AcquisitionSessionState.OPEN
    closed_at: str | None = None
    final_audit_digest: str | None = None
    schema_version: int = ACQUISITION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _required_text(self.session_id, "session_id")
        _required_text(self.well_id, "well_id")
        if self.schema_version != ACQUISITION_SCHEMA_VERSION:
            raise ValueError("Неподдерживаемая версия acquisition session schema")
        if not isinstance(self.dataset_schema, AcquisitionDatasetSchema):
            raise ValueError("dataset_schema имеет неверный тип")
        if not isinstance(self.state, AcquisitionSessionState):
            raise ValueError("state должен использовать AcquisitionSessionState")
        expected_sequence = 1
        record_ids: set[str] = set()
        for record in self.records:
            if not isinstance(record, AcquisitionRecord):
                raise ValueError("records должен содержать AcquisitionRecord")
            if record.sequence != expected_sequence:
                raise ValueError("Acquisition records должны иметь непрерывную sequence")
            if record.record_id in record_ids:
                raise ValueError("record_id acquisition session не должен повторяться")
            if isinstance(record.payload, AcquisitionDataRowPayload):
                expected_indexes = {item.index_id for item in self.dataset_schema.indexes}
                expected_curves = {
                    item.metadata.curve_id for item in self.dataset_schema.curves
                }
                if set(record.payload.indexes_dict()) != expected_indexes:
                    raise ValueError("Data row не соответствует acquisition indexes")
                if set(record.payload.curves_dict()) != expected_curves:
                    raise ValueError("Data row не соответствует acquisition curves")
            if isinstance(record.payload, AcquisitionEventUpsertPayload):
                if record.payload.event.well_id != self.well_id:
                    raise ValueError("Operational event acquisition относится к другой скважине")
            record_ids.add(record.record_id)
            expected_sequence += 1
        checkpoint_ids: set[str] = set()
        previous_sequence = -1
        checkpoint_signature_by_sequence: dict[int, tuple[int, str, str, str]] = {}
        for checkpoint in self.checkpoints:
            if not isinstance(checkpoint, AcquisitionCheckpoint):
                raise ValueError("checkpoints должен содержать AcquisitionCheckpoint")
            if checkpoint.checkpoint_id in checkpoint_ids:
                raise ValueError("checkpoint_id не должен повторяться")
            if checkpoint.sequence < previous_sequence or checkpoint.sequence > len(self.records):
                raise ValueError("Checkpoint sequence выходит за границы acquisition session")
            signature = (
                checkpoint.row_count,
                checkpoint.dataset_digest,
                checkpoint.events_digest,
                checkpoint.audit_digest,
            )
            previous_signature = checkpoint_signature_by_sequence.get(checkpoint.sequence)
            if previous_signature is not None and previous_signature != signature:
                raise ValueError("Checkpoints одной sequence должны иметь одинаковые fingerprints")
            checkpoint_signature_by_sequence[checkpoint.sequence] = signature
            checkpoint_ids.add(checkpoint.checkpoint_id)
            previous_sequence = checkpoint.sequence
        if self.state is AcquisitionSessionState.OPEN:
            if self.closed_at is not None or self.final_audit_digest is not None:
                raise ValueError("Открытая acquisition session не должна иметь close metadata")
        else:
            if self.closed_at is None or self.final_audit_digest is None:
                raise ValueError("Закрытая acquisition session требует close metadata")
            self.closed_at = canonical_acquisition_timestamp(self.closed_at)
            _validate_digest(self.final_audit_digest, "final_audit_digest")
            if not self.checkpoints or self.checkpoints[-1].sequence != len(self.records):
                raise ValueError("Закрытая acquisition session требует финальный checkpoint")
            if self.checkpoints[-1].audit_digest != self.final_audit_digest:
                raise ValueError("final_audit_digest не совпадает с финальным checkpoint")

    @property
    def last_sequence(self) -> int:
        return len(self.records)

    def checkpoint_by_id(self, checkpoint_id: str) -> AcquisitionCheckpoint:
        for checkpoint in self.checkpoints:
            if checkpoint.checkpoint_id == checkpoint_id:
                return checkpoint
        raise KeyError(f"Неизвестный acquisition checkpoint: {checkpoint_id}")


def canonical_acquisition_timestamp(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Timestamp должен быть непустой строкой")
    parsed = parse_operational_timestamp(value.strip())
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def acquisition_timestamp_to_ns(value: str) -> int:
    parsed = parse_operational_timestamp(value).astimezone(timezone.utc)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = parsed - epoch
    whole_seconds = delta.days * 86_400 + delta.seconds
    return whole_seconds * 1_000_000_000 + delta.microseconds * 1_000


def _validate_digest(value: object, name: str) -> None:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{name} должен быть SHA-256 hex digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{name} должен быть SHA-256 hex digest") from exc


def _required_text(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} должен быть непустой строкой")


def _optional_text(value: object, name: str) -> None:
    if value is not None:
        _required_text(value, name)


def _validate_pairs(value: object, name: str) -> None:
    if not isinstance(value, tuple):
        raise ValueError(f"{name} должен быть tuple пар")
    for item in value:
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValueError(f"{name} должен содержать пары (id, value)")
        _required_text(item[0], f"{name}.id")
