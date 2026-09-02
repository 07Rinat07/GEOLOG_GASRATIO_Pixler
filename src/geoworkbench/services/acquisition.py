from __future__ import annotations

from collections import deque
from copy import deepcopy
from itertools import islice
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
from typing import Any, Iterable, Sequence

import numpy as np

from geoworkbench.domain.acquisition import (
    AcquisitionCheckpoint,
    AcquisitionDataRowPayload,
    AcquisitionDatasetSchema,
    AcquisitionEventDeletePayload,
    AcquisitionEventUpsertPayload,
    AcquisitionIndexSchema,
    AcquisitionRecord,
    AcquisitionRecordKind,
    AcquisitionSession,
    AcquisitionSessionState,
    canonical_acquisition_timestamp,
)
from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetIndex,
    IndexRole,
    IndexType,
    Well,
)
from geoworkbench.services.operational_event_controller import OperationalEventController
from geoworkbench.services.operational_event_qc import (
    OperationalEventQcEvaluator,
    OperationalEventQcPolicy,
)
from geoworkbench.catalogs.sensors import normalize_sensor_key
from geoworkbench.services.las_parameter_resolver import infer_canonical_mnemonic
from geoworkbench.services.semantic_channels import default_semantic_channel_dictionary
from geoworkbench.services.text_normalization import clean_display_text, clean_mnemonic


class AcquisitionError(RuntimeError):
    """Base error for append-only acquisition operations."""


class AcquisitionConflictError(AcquisitionError):
    """Raised when source sequence, schema, state, or checkpoint does not match."""


class AcquisitionBackpressureError(AcquisitionError):
    """Raised when the bounded pending buffer is full."""


class AcquisitionReplayError(AcquisitionError):
    """Raised when deterministic replay diverges from the recorded source."""


DEFAULT_ACQUISITION_BATCH_SIZE = 64
MIN_ACQUISITION_BUFFER_CAPACITY = 64


@dataclass(frozen=True, slots=True)
class AcquisitionApplyResult:
    sequence: int
    rows_appended: int
    events_upserted: int
    events_deleted: int
    dataset_digest: str
    events_digest: str
    audit_digest: str
    record_chain_digest: str = ""
    batch_end_sequence: int | None = None
    digest_mode: str = "projection"


@dataclass(frozen=True, slots=True)
class AcquisitionReplayResult:
    session_id: str
    records_replayed: int
    rows_appended: int
    events_upserted: int
    events_deleted: int
    dataset_digest: str
    events_digest: str
    audit_digest: str


@dataclass(frozen=True, slots=True)
class _DatasetBufferCheckpoint:
    size: int
    curve_versions: tuple[tuple[str, int], ...]


class _DatasetAppendBuffer:
    """Geometrically growing acquisition arrays with logical-length rollback."""

    def __init__(self, dataset: Dataset, schema: AcquisitionDatasetSchema) -> None:
        _validate_dataset_schema(dataset, schema)
        self.dataset = dataset
        self.schema = schema
        self.size = len(dataset.depth)
        self.capacity = _geometric_capacity(self.size)
        self.reallocations = 0
        self._index_buffers: dict[str, np.ndarray[Any, Any]] = {}
        self._curve_buffers: dict[str, np.ndarray[Any, Any]] = {}
        for index_schema in schema.indexes:
            source = dataset.indexes[index_schema.index_id].values
            dtype = (
                np.dtype("datetime64[ns]")
                if index_schema.index_type is IndexType.DATETIME
                else np.dtype(np.float64)
            )
            buffer = np.empty(self.capacity, dtype=dtype)
            if self.size:
                buffer[: self.size] = np.asarray(source, dtype=dtype)
            self._index_buffers[index_schema.index_id] = buffer
        for curve_schema in schema.curves:
            curve_id = curve_schema.metadata.curve_id
            buffer = np.empty(self.capacity, dtype=np.float64)
            if self.size:
                buffer[: self.size] = np.asarray(
                    dataset.curves[curve_id].values, dtype=np.float64
                )
            self._curve_buffers[curve_id] = buffer
        self._publish()

    def checkpoint(self) -> _DatasetBufferCheckpoint:
        return _DatasetBufferCheckpoint(
            self.size,
            tuple(
                (curve_id, self.dataset.curves[curve_id].version)
                for curve_id in self._curve_buffers
            ),
        )

    def append_many(self, payloads: Sequence[AcquisitionDataRowPayload]) -> None:
        if not payloads:
            return
        start = self.size
        end = start + len(payloads)
        self._ensure_capacity(end)
        index_rows = [payload.indexes_dict() for payload in payloads]
        curve_rows = [payload.curves_dict() for payload in payloads]
        for index_schema in self.schema.indexes:
            raw_values = [row[index_schema.index_id] for row in index_rows]
            if index_schema.index_type is IndexType.DATETIME:
                if any(
                    isinstance(value, bool) or not isinstance(value, int)
                    for value in raw_values
                ):
                    raise AcquisitionConflictError("DATETIME acquisition index требует Unix ns")
                values = np.asarray(raw_values, dtype=np.int64).astype("datetime64[ns]")
            else:
                values = np.asarray(raw_values, dtype=np.float64)
            self._index_buffers[index_schema.index_id][start:end] = values
        for curve_schema in self.schema.curves:
            curve_id = curve_schema.metadata.curve_id
            curve_values: list[float] = []
            for row in curve_rows:
                raw_value = row[curve_id]
                curve_values.append(np.nan if raw_value is None else float(raw_value))
            values = np.asarray(curve_values, dtype=np.float64)
            self._curve_buffers[curve_id][start:end] = values
            self.dataset.curves[curve_id].version += len(payloads)
        self.size = end
        self._publish()

    def rollback(self, checkpoint: _DatasetBufferCheckpoint) -> None:
        if checkpoint.size < 0 or checkpoint.size > self.capacity:
            raise AcquisitionConflictError("Некорректный logical rollback acquisition buffer")
        self.size = checkpoint.size
        for curve_id, version in checkpoint.curve_versions:
            self.dataset.curves[curve_id].version = version
        self._publish()

    def _ensure_capacity(self, required: int) -> None:
        if required <= self.capacity:
            return
        capacity = self.capacity
        while capacity < required:
            capacity *= 2
        for key, previous in tuple(self._index_buffers.items()):
            expanded = np.empty(capacity, dtype=previous.dtype)
            expanded[: self.size] = previous[: self.size]
            self._index_buffers[key] = expanded
        for key, previous in tuple(self._curve_buffers.items()):
            expanded = np.empty(capacity, dtype=previous.dtype)
            expanded[: self.size] = previous[: self.size]
            self._curve_buffers[key] = expanded
        self.capacity = capacity
        self.reallocations += 1

    def _publish(self) -> None:
        for index_id, buffer in self._index_buffers.items():
            self.dataset.indexes[index_id].values = buffer[: self.size]
        for curve_id, buffer in self._curve_buffers.items():
            self.dataset.curves[curve_id].values = buffer[: self.size]
        active = self.dataset.active_index
        if active.role is IndexRole.DEPTH:
            self.dataset.depth = np.asarray(active.values, dtype=np.float64)
        else:
            self.dataset.depth = np.arange(self.size, dtype=np.float64)


def _geometric_capacity(size: int) -> int:
    capacity = MIN_ACQUISITION_BUFFER_CAPACITY
    while capacity < max(1, size):
        capacity *= 2
    return capacity


def _chain_seed(session: AcquisitionSession, kind: str) -> str:
    return _sha256_payload(
        {
            "kind": f"acquisition-{kind}-chain-v1",
            "session_id": session.session_id,
            "well_id": session.well_id,
            "schema": asdict(session.dataset_schema),
        }
    )


def _encoded_record(record: AcquisitionRecord) -> bytes:
    return json.dumps(
        _json_compatible(asdict(record)),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _chain_step(previous_digest: str, kind: str, encoded_record: bytes) -> str:
    material = bytes.fromhex(previous_digest) + kind.encode("ascii") + b"\0" + encoded_record
    return sha256(material).hexdigest()


class AcquisitionController:
    """Single append-only mutation boundary for one persisted acquisition session."""

    def __init__(
        self,
        well: Well,
        session: AcquisitionSession,
        *,
        max_pending_records: int = 256,
        qc_policy: OperationalEventQcPolicy | None = None,
    ) -> None:
        if well.well_id != session.well_id:
            raise AcquisitionConflictError("Acquisition session относится к другой скважине")
        if (
            isinstance(max_pending_records, bool)
            or not isinstance(max_pending_records, int)
            or max_pending_records < 1
        ):
            raise ValueError("max_pending_records должен быть положительным целым числом")
        existing = well.acquisition_sessions.get(session.session_id)
        if existing is not None and existing is not session:
            raise AcquisitionConflictError(
                f"Acquisition session уже существует: {session.session_id}"
            )
        other_sessions = set(well.acquisition_sessions) - {session.session_id}
        if other_sessions:
            raise AcquisitionConflictError(
                "Одна скважина может иметь только одну acquisition source session"
            )
        if existing is None and not session.records and well.operational_events:
            raise AcquisitionConflictError(
                "Новая acquisition session требует чистую operational event projection"
            )
        self.well = well
        self.session = session
        self.max_pending_records = max_pending_records
        self._pending: deque[AcquisitionRecord] = deque()
        # Keep an incremental identity index. Rebuilding a set from the complete
        # append-only record history on every live frame would make long sessions
        # progressively slower (O(n²) over the session lifetime).
        self._known_record_ids: set[str] = {
            item.record_id for item in session.records
        }
        self._qc_evaluator = OperationalEventQcEvaluator(qc_policy or OperationalEventQcPolicy())
        created_dataset = session.dataset_schema.dataset_id not in well.datasets
        events_snapshot = dict(well.operational_events)
        try:
            self._event_controller = OperationalEventController(
                well,
                qc_evaluator=self._qc_evaluator,
            )
            self._ensure_dataset()
            self._dataset_buffer = _DatasetAppendBuffer(
                self.dataset, self.session.dataset_schema
            )
            self._record_chain_digest = _chain_seed(self.session, "record")
            self._dataset_chain_digest = _chain_seed(self.session, "dataset")
            self._events_chain_digest = _chain_seed(self.session, "events")
            for persisted_record in self.session.records:
                self._advance_incremental_chains(persisted_record)
            self._validate_persisted_projection()
        except Exception:
            well.operational_events = events_snapshot
            if created_dataset:
                well.datasets.pop(session.dataset_schema.dataset_id, None)
            raise
        well.acquisition_sessions[session.session_id] = session

    @property
    def dataset(self) -> Dataset:
        return self.well.datasets[self.session.dataset_schema.dataset_id]

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def remaining_capacity(self) -> int:
        return self.max_pending_records - len(self._pending)

    @property
    def buffer_capacity(self) -> int:
        return self._dataset_buffer.capacity

    @property
    def buffer_reallocations(self) -> int:
        return self._dataset_buffer.reallocations

    @property
    def record_chain_digest(self) -> str:
        return self._record_chain_digest

    @property
    def dataset_chain_digest(self) -> str:
        return self._dataset_chain_digest

    @property
    def events_chain_digest(self) -> str:
        return self._events_chain_digest

    def enqueue(self, record: AcquisitionRecord) -> None:
        self.enqueue_many((record,))

    def enqueue_many(self, records: Iterable[AcquisitionRecord]) -> None:
        """Atomically enqueue a contiguous record batch without partial buffer mutation."""

        self._require_open()
        materialized = tuple(records)
        if not materialized:
            return
        if len(materialized) > self.remaining_capacity:
            raise AcquisitionBackpressureError(
                "Acquisition buffer capacity exceeded: "
                f"pending={len(self._pending)}, incoming={len(materialized)}, "
                f"capacity={self.max_pending_records}"
            )
        expected_sequence = self.session.last_sequence + len(self._pending) + 1
        incoming_ids: set[str] = set()
        for offset, record in enumerate(materialized):
            expected = expected_sequence + offset
            if record.sequence != expected:
                raise AcquisitionConflictError(
                    f"Acquisition sequence conflict: expected {expected}, "
                    f"actual {record.sequence}"
                )
            if (
                record.record_id in self._known_record_ids
                or record.record_id in incoming_ids
            ):
                raise AcquisitionConflictError(
                    f"Acquisition record уже существует: {record.record_id}"
                )
            self._validate_record_schema(record)
            incoming_ids.add(record.record_id)
        self._pending.extend(materialized)
        self._known_record_ids.update(incoming_ids)

    def append(self, record: AcquisitionRecord) -> AcquisitionApplyResult:
        self.enqueue(record)
        results = self.drain(limit=1, batch_size=1)
        return results[0]

    def append_many(
        self,
        records: Iterable[AcquisitionRecord],
        *,
        batch_size: int = DEFAULT_ACQUISITION_BATCH_SIZE,
    ) -> tuple[AcquisitionApplyResult, ...]:
        """Stream records through bounded atomic batches (64 by default)."""

        if (
            isinstance(batch_size, bool)
            or not isinstance(batch_size, int)
            or batch_size < 1
        ):
            raise ValueError("batch_size должен быть положительным целым числом")
        if self._pending:
            raise AcquisitionConflictError(
                "append_many требует пустой pending buffer; сначала вызовите drain()"
            )
        chunk_size = min(batch_size, self.max_pending_records)
        chunk: list[AcquisitionRecord] = []
        results: list[AcquisitionApplyResult] = []
        for record in records:
            chunk.append(record)
            if len(chunk) < chunk_size:
                continue
            self.enqueue_many(chunk)
            results.extend(self.drain(limit=len(chunk), batch_size=chunk_size))
            chunk.clear()
        if chunk:
            self.enqueue_many(chunk)
            results.extend(self.drain(limit=len(chunk), batch_size=chunk_size))
        return tuple(results)

    def drain(
        self,
        *,
        limit: int | None = None,
        batch_size: int = DEFAULT_ACQUISITION_BATCH_SIZE,
    ) -> tuple[AcquisitionApplyResult, ...]:
        if limit is not None and (
            isinstance(limit, bool) or not isinstance(limit, int) or limit < 0
        ):
            raise ValueError("limit должен быть неотрицательным целым числом")
        if (
            isinstance(batch_size, bool)
            or not isinstance(batch_size, int)
            or batch_size < 1
        ):
            raise ValueError("batch_size должен быть положительным целым числом")
        results: list[AcquisitionApplyResult] = []
        while self._pending and (limit is None or len(results) < limit):
            remaining = len(self._pending)
            if limit is not None:
                remaining = min(remaining, limit - len(results))
            batch_count = min(batch_size, remaining)
            batch = tuple(islice(self._pending, 0, batch_count))
            applied = self._apply_batch_atomically(batch)
            for _item in batch:
                self._pending.popleft()
            results.extend(applied)
        return tuple(results)

    def create_checkpoint(self, checkpoint_id: str, *, created_at: str) -> AcquisitionCheckpoint:
        self._require_open()
        if self._pending:
            raise AcquisitionConflictError("Нельзя создать checkpoint при непустом buffer")
        if any(item.checkpoint_id == checkpoint_id for item in self.session.checkpoints):
            raise AcquisitionConflictError(f"Checkpoint уже существует: {checkpoint_id}")
        digests = acquisition_projection_digests(self.dataset, self.well)
        checkpoint = AcquisitionCheckpoint(
            checkpoint_id=checkpoint_id,
            sequence=self.session.last_sequence,
            row_count=len(self.dataset.depth),
            dataset_digest=digests[0],
            events_digest=digests[1],
            audit_digest=_audit_digest(
                self.session.session_id,
                self.session.last_sequence,
                digests[0],
                digests[1],
            ),
            created_at=created_at,
        )
        self.session.checkpoints.append(checkpoint)
        return checkpoint

    def verify_checkpoint(self, checkpoint: AcquisitionCheckpoint) -> None:
        if self._pending:
            raise AcquisitionConflictError("Нельзя проверять checkpoint при непустом buffer")
        if checkpoint.sequence != self.session.last_sequence:
            raise AcquisitionConflictError(
                f"Checkpoint sequence conflict: expected {checkpoint.sequence}, "
                f"actual {self.session.last_sequence}"
            )
        if checkpoint.row_count != len(self.dataset.depth):
            raise AcquisitionConflictError("Checkpoint row_count не совпадает с dataset")
        dataset_digest, events_digest = acquisition_projection_digests(self.dataset, self.well)
        audit_digest = _audit_digest(
            self.session.session_id,
            self.session.last_sequence,
            dataset_digest,
            events_digest,
        )
        if (
            dataset_digest != checkpoint.dataset_digest
            or events_digest != checkpoint.events_digest
            or audit_digest != checkpoint.audit_digest
        ):
            raise AcquisitionConflictError("Checkpoint fingerprint не совпадает с проекцией")

    def close(self, *, checkpoint_id: str, closed_at: str) -> AcquisitionCheckpoint:
        self._require_open()
        if self._pending:
            raise AcquisitionConflictError("Перед закрытием acquisition buffer должен быть пуст")
        checkpoint = self.create_checkpoint(checkpoint_id, created_at=closed_at)
        self.session.state = AcquisitionSessionState.CLOSED
        self.session.closed_at = canonical_acquisition_timestamp(closed_at)
        self.session.final_audit_digest = checkpoint.audit_digest
        return checkpoint

    def current_result(self) -> AcquisitionApplyResult:
        dataset_digest, events_digest = acquisition_projection_digests(self.dataset, self.well)
        return AcquisitionApplyResult(
            sequence=self.session.last_sequence,
            rows_appended=0,
            events_upserted=0,
            events_deleted=0,
            dataset_digest=dataset_digest,
            events_digest=events_digest,
            audit_digest=_audit_digest(
                self.session.session_id,
                self.session.last_sequence,
                dataset_digest,
                events_digest,
            ),
            record_chain_digest=self._record_chain_digest,
            batch_end_sequence=self.session.last_sequence,
            digest_mode="projection",
        )

    def _apply_batch_atomically(
        self, records: Sequence[AcquisitionRecord]
    ) -> tuple[AcquisitionApplyResult, ...]:
        if not records:
            return ()
        buffer_checkpoint = self._dataset_buffer.checkpoint()
        events_snapshot = dict(self.well.operational_events)
        record_count = len(self.session.records)
        chain_checkpoint = (
            self._record_chain_digest,
            self._dataset_chain_digest,
            self._events_chain_digest,
        )
        applied: list[
            tuple[AcquisitionRecord, int, int, int, str, str, str]
        ] = []
        row_records: list[AcquisitionRecord] = []

        def flush_rows() -> None:
            if not row_records:
                return
            payloads: list[AcquisitionDataRowPayload] = []
            for item in row_records:
                assert isinstance(item.payload, AcquisitionDataRowPayload)
                payloads.append(item.payload)
            self._dataset_buffer.append_many(payloads)
            for item in row_records:
                self.session.records.append(item)
                self._advance_incremental_chains(item)
                applied.append(
                    (
                        item,
                        1,
                        0,
                        0,
                        self._dataset_chain_digest,
                        self._events_chain_digest,
                        self._record_chain_digest,
                    )
                )
            row_records.clear()

        try:
            for record in records:
                if record.kind is AcquisitionRecordKind.DATA_ROW:
                    row_records.append(record)
                    continue
                flush_rows()
                rows, upserts, deletes = self._apply_event_record(record)
                self.session.records.append(record)
                self._advance_incremental_chains(record)
                applied.append(
                    (
                        record,
                        rows,
                        upserts,
                        deletes,
                        self._dataset_chain_digest,
                        self._events_chain_digest,
                        self._record_chain_digest,
                    )
                )
            flush_rows()
            batch_end_sequence = records[-1].sequence
            return tuple(
                AcquisitionApplyResult(
                    sequence=record.sequence,
                    rows_appended=rows,
                    events_upserted=upserts,
                    events_deleted=deletes,
                    dataset_digest=dataset_chain_digest,
                    events_digest=events_chain_digest,
                    audit_digest=_incremental_audit_digest(
                        self.session.session_id,
                        record.sequence,
                        record_chain_digest,
                        dataset_chain_digest,
                        events_chain_digest,
                    ),
                    record_chain_digest=record_chain_digest,
                    batch_end_sequence=batch_end_sequence,
                    digest_mode="incremental_chain",
                )
                for (
                    record,
                    rows,
                    upserts,
                    deletes,
                    dataset_chain_digest,
                    events_chain_digest,
                    record_chain_digest,
                ) in applied
            )
        except Exception:
            del self.session.records[record_count:]
            self._dataset_buffer.rollback(buffer_checkpoint)
            (
                self._record_chain_digest,
                self._dataset_chain_digest,
                self._events_chain_digest,
            ) = chain_checkpoint
            self.well.operational_events = events_snapshot
            self._event_controller = OperationalEventController(
                self.well, qc_evaluator=self._qc_evaluator
            )
            raise

    def _advance_incremental_chains(self, record: AcquisitionRecord) -> None:
        encoded_record = _encoded_record(record)
        self._record_chain_digest = _chain_step(
            self._record_chain_digest, "record", encoded_record
        )
        if record.kind is AcquisitionRecordKind.DATA_ROW:
            self._dataset_chain_digest = _chain_step(
                self._dataset_chain_digest, "dataset", encoded_record
            )
        else:
            self._events_chain_digest = _chain_step(
                self._events_chain_digest, "events", encoded_record
            )

    def _apply_event_record(self, record: AcquisitionRecord) -> tuple[int, int, int]:
        if record.kind is AcquisitionRecordKind.EVENT_UPSERT:
            assert isinstance(record.payload, AcquisitionEventUpsertPayload)
            payload = record.payload
            if payload.expected_revision is None:
                self._event_controller.create(replace(payload.event, qc_flags=()))
            else:
                self._event_controller.update(
                    payload.event.event_id,
                    replace(payload.event, qc_flags=()),
                    expected_revision=payload.expected_revision,
                )
            return 0, 1, 0
        assert isinstance(record.payload, AcquisitionEventDeletePayload)
        self._event_controller.remove(
            record.payload.event_id,
            expected_revision=record.payload.expected_revision,
        )
        return 0, 0, 1

    def _ensure_dataset(self) -> None:
        dataset_id = self.session.dataset_schema.dataset_id
        existing = self.well.datasets.get(dataset_id)
        if existing is None:
            self.well.datasets[dataset_id] = dataset_from_acquisition_schema(
                self.session.dataset_schema
            )
            return
        if len(existing.depth) != 0 and not self.session.records:
            raise AcquisitionConflictError(
                "Новая acquisition session требует пустой dataset или persisted records"
            )
        _validate_dataset_schema(existing, self.session.dataset_schema)

    def _validate_persisted_projection(self) -> None:
        if not self.session.records:
            for checkpoint in self.session.checkpoints:
                _validate_projection_checkpoint(
                    self.session.session_id,
                    0,
                    self.dataset,
                    self.well,
                    checkpoint,
                )
            return
        expected_well = Well(self.well.well_id, self.well.name)
        expected_dataset = dataset_from_acquisition_schema(self.session.dataset_schema)
        expected_well.datasets[expected_dataset.dataset_id] = expected_dataset
        expected_buffer = _DatasetAppendBuffer(
            expected_dataset, self.session.dataset_schema
        )
        expected_events = OperationalEventController(
            expected_well,
            qc_evaluator=self._qc_evaluator,
        )
        checkpoints_by_sequence: dict[int, list[AcquisitionCheckpoint]] = {}
        for checkpoint in self.session.checkpoints:
            checkpoints_by_sequence.setdefault(checkpoint.sequence, []).append(checkpoint)
        for checkpoint in checkpoints_by_sequence.get(0, []):
            _validate_projection_checkpoint(
                self.session.session_id,
                0,
                expected_dataset,
                expected_well,
                checkpoint,
            )
        for record in self.session.records:
            if isinstance(record.payload, AcquisitionDataRowPayload):
                expected_buffer.append_many((record.payload,))
            elif isinstance(record.payload, AcquisitionEventUpsertPayload):
                if record.payload.expected_revision is None:
                    expected_events.create(replace(record.payload.event, qc_flags=()))
                else:
                    expected_events.update(
                        record.payload.event.event_id,
                        replace(record.payload.event, qc_flags=()),
                        expected_revision=record.payload.expected_revision,
                    )
            else:
                assert isinstance(record.payload, AcquisitionEventDeletePayload)
                expected_events.remove(
                    record.payload.event_id,
                    expected_revision=record.payload.expected_revision,
                )
            for checkpoint in checkpoints_by_sequence.get(record.sequence, []):
                _validate_projection_checkpoint(
                    self.session.session_id,
                    record.sequence,
                    expected_dataset,
                    expected_well,
                    checkpoint,
                )
        expected_digests = acquisition_projection_digests(expected_dataset, expected_well)
        actual_digests = acquisition_projection_digests(self.dataset, self.well)
        if expected_digests != actual_digests:
            raise AcquisitionConflictError(
                "Persisted acquisition projection не соответствует append-only source"
            )

    def _validate_record_schema(self, record: AcquisitionRecord) -> None:
        if isinstance(record.payload, AcquisitionDataRowPayload):
            expected_indexes = {item.index_id for item in self.session.dataset_schema.indexes}
            expected_curves = {
                item.metadata.curve_id for item in self.session.dataset_schema.curves
            }
            if set(record.payload.indexes_dict()) != expected_indexes:
                raise AcquisitionConflictError(
                    "Data row должен содержать точный набор acquisition indexes"
                )
            if set(record.payload.curves_dict()) != expected_curves:
                raise AcquisitionConflictError(
                    "Data row должен содержать точный набор acquisition curves"
                )
        elif isinstance(record.payload, AcquisitionEventUpsertPayload):
            if record.payload.event.well_id != self.well.well_id:
                raise AcquisitionConflictError("Operational event относится к другой скважине")

    def _require_open(self) -> None:
        if self.session.state is not AcquisitionSessionState.OPEN:
            raise AcquisitionConflictError("Acquisition session уже закрыта")


def _replay_working_well(
    source: AcquisitionSession,
    target_well: Well,
    *,
    checkpoint_id: str | None,
) -> Well:
    """Stage only mutable replay projection state instead of cloning the complete well.

    Acquisition records, checkpoints and operational events are immutable domain objects, so the
    staging transaction only needs new containers for them. A checkpoint resume deep-copies the
    single materialized acquisition dataset because its NumPy arrays are mutated during replay.
    Unrelated datasets and their arrays never enter the staging graph.
    """

    working_well = Well(target_well.well_id, target_well.name)
    working_well.operational_events = dict(target_well.operational_events)
    working_well.acquisition_sessions = dict(target_well.acquisition_sessions)

    dataset_id = source.dataset_schema.dataset_id
    if checkpoint_id is None:
        existing_dataset = target_well.datasets.get(dataset_id)
        if existing_dataset is not None:
            working_well.datasets[dataset_id] = existing_dataset
        return working_well

    existing_dataset = target_well.datasets.get(dataset_id)
    if existing_dataset is not None:
        working_well.datasets[dataset_id] = deepcopy(existing_dataset)

    existing_session = target_well.acquisition_sessions.get(source.session_id)
    if existing_session is not None:
        working_well.acquisition_sessions[source.session_id] = AcquisitionSession(
            session_id=existing_session.session_id,
            well_id=existing_session.well_id,
            dataset_schema=existing_session.dataset_schema,
            records=list(existing_session.records),
            checkpoints=list(existing_session.checkpoints),
            state=existing_session.state,
            closed_at=existing_session.closed_at,
            final_audit_digest=existing_session.final_audit_digest,
            schema_version=existing_session.schema_version,
        )
    return working_well


def replay_acquisition_session(
    source: AcquisitionSession,
    target_well: Well,
    *,
    checkpoint_id: str | None = None,
    max_pending_records: int = 256,
    qc_policy: OperationalEventQcPolicy | None = None,
) -> AcquisitionReplayResult:
    """Replay a recorded source transactionally from zero or a verified checkpoint."""

    if source.well_id != target_well.well_id:
        raise AcquisitionReplayError("Acquisition source относится к другой скважине")
    working_well = _replay_working_well(
        source,
        target_well,
        checkpoint_id=checkpoint_id,
    )
    start_sequence = 0
    try:
        if checkpoint_id is None:
            if source.session_id in working_well.acquisition_sessions:
                raise AcquisitionReplayError("Target well уже содержит acquisition session")
            if source.dataset_schema.dataset_id in working_well.datasets:
                raise AcquisitionReplayError("Target well уже содержит replay dataset")
            target_session = AcquisitionSession(
                session_id=source.session_id,
                well_id=working_well.well_id,
                dataset_schema=source.dataset_schema,
            )
            controller = AcquisitionController(
                working_well,
                target_session,
                max_pending_records=max_pending_records,
                qc_policy=qc_policy,
            )
        else:
            try:
                target_session = working_well.acquisition_sessions[source.session_id]
            except KeyError as exc:
                raise AcquisitionReplayError(
                    "Target well не содержит acquisition session"
                ) from exc
            checkpoint = source.checkpoint_by_id(checkpoint_id)
            try:
                controller = AcquisitionController(
                    working_well,
                    target_session,
                    max_pending_records=max_pending_records,
                    qc_policy=qc_policy,
                )
                controller.verify_checkpoint(checkpoint)
            except AcquisitionConflictError as exc:
                raise AcquisitionReplayError(str(exc)) from exc
            start_sequence = checkpoint.sequence
        checkpoints_by_sequence: dict[int, list[AcquisitionCheckpoint]] = {}
        for checkpoint in source.checkpoints:
            if checkpoint.sequence > start_sequence:
                checkpoints_by_sequence.setdefault(checkpoint.sequence, []).append(checkpoint)
        rows = upserts = deletes = 0
        replay_batch: list[AcquisitionRecord] = []
        for record in source.records[start_sequence:]:
            replay_batch.append(record)
            checkpoint_boundary = record.sequence in checkpoints_by_sequence
            if (
                len(replay_batch) < DEFAULT_ACQUISITION_BATCH_SIZE
                and not checkpoint_boundary
            ):
                continue
            try:
                results = controller.append_many(replay_batch)
            except Exception as exc:
                raise AcquisitionReplayError(
                    f"Replay diverged at sequence {record.sequence}: {exc}"
                ) from exc
            rows += sum(item.rows_appended for item in results)
            upserts += sum(item.events_upserted for item in results)
            deletes += sum(item.events_deleted for item in results)
            replay_batch.clear()
            for expected_checkpoint in checkpoints_by_sequence.get(record.sequence, []):
                try:
                    _verify_projection_against_checkpoint(controller, expected_checkpoint)
                except AcquisitionConflictError as exc:
                    raise AcquisitionReplayError(str(exc)) from exc
        if replay_batch:
            last_record = replay_batch[-1]
            try:
                results = controller.append_many(replay_batch)
            except Exception as exc:
                raise AcquisitionReplayError(
                    f"Replay diverged at sequence {last_record.sequence}: {exc}"
                ) from exc
            rows += sum(item.rows_appended for item in results)
            upserts += sum(item.events_upserted for item in results)
            deletes += sum(item.events_deleted for item in results)

        target_session.checkpoints = list(source.checkpoints)
        target_session.state = source.state
        target_session.closed_at = source.closed_at
        target_session.final_audit_digest = source.final_audit_digest
        final = controller.current_result()
        if (
            source.final_audit_digest is not None
            and final.audit_digest != source.final_audit_digest
        ):
            raise AcquisitionReplayError("Final replay fingerprint не совпадает с source")
    except AcquisitionReplayError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise AcquisitionReplayError(str(exc)) from exc

    working_dataset = working_well.datasets[source.dataset_schema.dataset_id]
    working_session = working_well.acquisition_sessions[source.session_id]
    if checkpoint_id is None:
        target_well.datasets[source.dataset_schema.dataset_id] = working_dataset
        target_well.acquisition_sessions[source.session_id] = working_session
    else:
        target_dataset = target_well.datasets[source.dataset_schema.dataset_id]
        target_session = target_well.acquisition_sessions[source.session_id]
        _copy_dataset_projection(target_dataset, working_dataset)
        _copy_session_state(target_session, working_session)
    target_well.operational_events.clear()
    target_well.operational_events.update(working_well.operational_events)
    return AcquisitionReplayResult(
        session_id=source.session_id,
        records_replayed=len(source.records) - start_sequence,
        rows_appended=rows,
        events_upserted=upserts,
        events_deleted=deletes,
        dataset_digest=final.dataset_digest,
        events_digest=final.events_digest,
        audit_digest=final.audit_digest,
    )


def dataset_from_acquisition_schema(schema: AcquisitionDatasetSchema) -> Dataset:
    indexes = {
        item.index_id: DatasetIndex(
            index_id=item.index_id,
            mnemonic=item.mnemonic,
            index_type=item.index_type,
            role=item.role,
            unit=item.unit,
            values=(
                np.asarray([], dtype="datetime64[ns]")
                if item.index_type is IndexType.DATETIME
                else np.asarray([], dtype=np.float64)
            ),
            confidence=item.confidence,
            evidence=item.evidence,
            datetime_format=item.datetime_format,
            timezone=item.timezone,
        )
        for item in schema.indexes
    }
    dataset = Dataset(
        dataset_id=schema.dataset_id,
        name=schema.name,
        kind=schema.kind,
        depth_domain=schema.depth_domain,
        depth=np.asarray([], dtype=np.float64),
        indexes=indexes,
        active_index_id=schema.active_index_id,
    )
    dataset.curves = {
        item.metadata.curve_id: CurveData(
            metadata=item.metadata,
            values=np.asarray([], dtype=np.float64),
        )
        for item in schema.curves
    }
    return dataset


def dataset_projection_digest(dataset: Dataset) -> str:
    """Return a canonical SHA-256 fingerprint for one materialized dataset projection."""

    dataset_payload = {
        "dataset_id": dataset.dataset_id,
        "name": dataset.name,
        "kind": dataset.kind.value,
        "depth_domain": dataset.depth_domain.value,
        "active_index_id": dataset.active_index_id,
        "depth": _array_tokens(dataset.depth),
        "indexes": {
            index_id: {
                "schema": _json_compatible(asdict(AcquisitionIndexSchema.from_index(index))),
                "values": _array_tokens(index.values),
            }
            for index_id, index in sorted(dataset.indexes.items())
        },
        "curves": {
            curve_id: {
                "metadata": _json_compatible(
                    asdict(canonical_curve_metadata(curve.metadata))
                ),
                "version": curve.version,
                "state": curve.state.value,
                "values": _array_tokens(curve.values),
            }
            for curve_id, curve in sorted(dataset.curves.items())
        },
    }
    return _sha256_payload(dataset_payload)


def operational_events_digest(well: Well) -> str:
    events_payload = {
        event_id: _json_compatible(asdict(event))
        for event_id, event in sorted(well.operational_events.items())
    }
    return _sha256_payload(events_payload)


def acquisition_projection_digests(dataset: Dataset, well: Well) -> tuple[str, str]:
    return dataset_projection_digest(dataset), operational_events_digest(well)


def canonical_curve_metadata(metadata: CurveMetadata) -> CurveMetadata:
    """Normalize implicit semantic metadata before hashing persisted projections."""

    original_mnemonic = clean_mnemonic(metadata.original_mnemonic)
    stored_canonical = (
        clean_mnemonic(metadata.canonical_mnemonic)
        if metadata.canonical_mnemonic
        else None
    )
    unit = clean_display_text(metadata.unit) or None
    description = clean_display_text(metadata.description) or None
    inferred_canonical = infer_canonical_mnemonic(
        original_mnemonic,
        description=description or "",
        unit=unit or "",
    )
    canonical_mnemonic = stored_canonical
    if not stored_canonical or normalize_sensor_key(stored_canonical) == normalize_sensor_key(
        original_mnemonic
    ):
        canonical_mnemonic = inferred_canonical or stored_canonical
    semantic = metadata.semantic or default_semantic_channel_dictionary().resolve(
        original_mnemonic,
        description=description or "",
        unit=unit or "",
        canonical_mnemonic=canonical_mnemonic,
    )
    return replace(
        metadata,
        original_mnemonic=original_mnemonic,
        canonical_mnemonic=semantic.canonical_mnemonic,
        unit=unit,
        description=description,
        semantic=semantic,
    )


_canonical_curve_metadata = canonical_curve_metadata


def _append_dataset_row(
    dataset: Dataset,
    schema: AcquisitionDatasetSchema,
    payload: AcquisitionDataRowPayload,
) -> None:
    """Compatibility helper; live acquisition reuses one geometric buffer."""

    _DatasetAppendBuffer(dataset, schema).append_many((payload,))


def _validate_dataset_schema(dataset: Dataset, schema: AcquisitionDatasetSchema) -> None:
    if dataset.dataset_id != schema.dataset_id:
        raise AcquisitionConflictError("Dataset ID не совпадает с acquisition schema")
    if dataset.name != schema.name or dataset.kind is not schema.kind:
        raise AcquisitionConflictError("Dataset metadata не совпадает с acquisition schema")
    if dataset.depth_domain is not schema.depth_domain:
        raise AcquisitionConflictError("Depth domain не совпадает с acquisition schema")
    if dataset.active_index_id != schema.active_index_id:
        raise AcquisitionConflictError("Active index не совпадает с acquisition schema")
    if set(dataset.indexes) != {item.index_id for item in schema.indexes}:
        raise AcquisitionConflictError("Indexes dataset не совпадают с acquisition schema")
    if set(dataset.curves) != {item.metadata.curve_id for item in schema.curves}:
        raise AcquisitionConflictError("Curves dataset не совпадают с acquisition schema")
    for index_schema in schema.indexes:
        actual_index_schema = AcquisitionIndexSchema.from_index(
            dataset.indexes[index_schema.index_id]
        )
        if actual_index_schema != index_schema:
            raise AcquisitionConflictError("Index metadata не совпадает с acquisition schema")
    for curve_schema in schema.curves:
        actual_curve_metadata = dataset.curves[curve_schema.metadata.curve_id].metadata
        if actual_curve_metadata != curve_schema.metadata:
            raise AcquisitionConflictError("Curve metadata не совпадает с acquisition schema")
    row_count = len(dataset.depth)
    if any(len(index.values) != row_count for index in dataset.indexes.values()):
        raise AcquisitionConflictError("Indexes growing dataset имеют разную длину")
    if any(len(curve.values) != row_count for curve in dataset.curves.values()):
        raise AcquisitionConflictError("Curves growing dataset имеют разную длину")
    active = dataset.active_index
    expected_depth = (
        np.asarray(active.values, dtype=np.float64)
        if active.role is IndexRole.DEPTH
        else np.arange(row_count, dtype=np.float64)
    )
    if not np.array_equal(dataset.depth, expected_depth):
        raise AcquisitionConflictError("Dataset depth projection не совпадает с active index")


def _copy_dataset_projection(target: Dataset, source: Dataset) -> None:
    """Commit a validated replay projection while preserving target object identity."""

    target.depth = source.depth.copy()
    for index_id, source_index in source.indexes.items():
        target.indexes[index_id].values = source_index.values.copy()
    for curve_id, source_curve in source.curves.items():
        target_curve = target.curves[curve_id]
        target_curve.values = source_curve.values.copy()
        target_curve.version = source_curve.version
        target_curve.state = source_curve.state


def _copy_session_state(target: AcquisitionSession, source: AcquisitionSession) -> None:
    """Commit replayed append-only state while preserving references held by callers."""

    target.records = list(source.records)
    target.checkpoints = list(source.checkpoints)
    target.state = source.state
    target.closed_at = source.closed_at
    target.final_audit_digest = source.final_audit_digest


def _verify_projection_against_checkpoint(
    controller: AcquisitionController,
    checkpoint: AcquisitionCheckpoint,
) -> None:
    _validate_projection_checkpoint(
        controller.session.session_id,
        controller.session.last_sequence,
        controller.dataset,
        controller.well,
        checkpoint,
    )


def _validate_projection_checkpoint(
    session_id: str,
    sequence: int,
    dataset: Dataset,
    well: Well,
    checkpoint: AcquisitionCheckpoint,
) -> None:
    dataset_digest, events_digest = acquisition_projection_digests(dataset, well)
    audit_digest = _audit_digest(
        session_id,
        sequence,
        dataset_digest,
        events_digest,
    )
    if (
        checkpoint.sequence != sequence
        or len(dataset.depth) != checkpoint.row_count
        or dataset_digest != checkpoint.dataset_digest
        or events_digest != checkpoint.events_digest
        or audit_digest != checkpoint.audit_digest
    ):
        raise AcquisitionConflictError(
            f"Replay checkpoint diverged: {checkpoint.checkpoint_id}"
        )


def _incremental_audit_digest(
    session_id: str,
    sequence: int,
    record_chain_digest: str,
    dataset_chain_digest: str,
    events_chain_digest: str,
) -> str:
    return _sha256_payload(
        {
            "kind": "acquisition-incremental-audit-v1",
            "session_id": session_id,
            "sequence": sequence,
            "record_chain_digest": record_chain_digest,
            "dataset_chain_digest": dataset_chain_digest,
            "events_chain_digest": events_chain_digest,
        }
    )


def _audit_digest(
    session_id: str,
    sequence: int,
    dataset_digest: str,
    events_digest: str,
) -> str:
    return _sha256_payload(
        {
            "session_id": session_id,
            "sequence": sequence,
            "dataset_digest": dataset_digest,
            "events_digest": events_digest,
        }
    )


def _sha256_payload(payload: object) -> str:
    encoded = json.dumps(
        _json_compatible(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _json_compatible(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_compatible(item) for item in value]
    if isinstance(value, np.generic):
        return _json_compatible(value.item())
    if isinstance(value, float):
        if np.isnan(value):
            return "NaN"
        if np.isposinf(value):
            return "+Infinity"
        if np.isneginf(value):
            return "-Infinity"
        return value
    if hasattr(value, "value"):
        return value.value
    return value


def _array_tokens(values: Iterable[Any]) -> list[Any]:
    array = np.asarray(values)
    if np.issubdtype(array.dtype, np.datetime64):
        return [int(item) for item in array.astype("datetime64[ns]").astype(np.int64)]
    return [_json_compatible(item) for item in array.tolist()]
