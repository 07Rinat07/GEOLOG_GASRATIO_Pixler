from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from enum import StrEnum
from hashlib import sha256
from math import isfinite
import time as time_module
from typing import Callable, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from geoworkbench.acquisition.wits0_parser import (
    Wits0ParsedField,
    Wits0ParsedFrame,
    Wits0SequenceStatus,
)
from geoworkbench.domain.acquisition import (
    AcquisitionCheckpoint,
    AcquisitionDataRowPayload,
    AcquisitionEventUpsertPayload,
    AcquisitionRecord,
    AcquisitionRecordKind,
    AcquisitionSession,
    AcquisitionSessionState,
    acquisition_timestamp_to_ns,
    canonical_acquisition_timestamp,
)
from geoworkbench.domain.models import IndexType, Well
from geoworkbench.domain.operational_events import (
    ConnectionEventPayload,
    OperationalEvent,
    OperationalEventKind,
)
from geoworkbench.services.acquisition import (
    AcquisitionApplyResult,
    AcquisitionBackpressureError,
    AcquisitionConflictError,
    AcquisitionController,
)
from geoworkbench.services.wits0_import_review import (
    Wits0ChannelKey,
    Wits0ImportReviewCommit,
    acquisition_schema_digest,
)


class Wits0NormalizationSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Wits0NormalizationCode(StrEnum):
    FRAME_WITHOUT_RECORD = "frame_without_record"
    DUPLICATE_SEQUENCE_SKIPPED = "duplicate_sequence_skipped"
    OUT_OF_ORDER_SEQUENCE_SKIPPED = "out_of_order_sequence_skipped"
    INVALID_SEQUENCE_SKIPPED = "invalid_sequence_skipped"
    MISSING_RECEIVED_AT = "missing_received_at"
    INVALID_RECEIVED_AT = "invalid_received_at"
    MISSING_INDEX = "missing_index"
    INVALID_INDEX = "invalid_index"
    MISSING_TIMEZONE = "missing_timezone"
    UNKNOWN_TIMEZONE = "unknown_timezone"
    MISSING_CURVE_VALUE = "missing_curve_value"
    INVALID_CURVE_VALUE = "invalid_curve_value"
    EMPTY_MEASUREMENT_ROW = "empty_measurement_row"


class Wits0AcquisitionState(StrEnum):
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"


class Wits0BackpressurePolicy(StrEnum):
    RAISE = "raise"
    DRAIN_THEN_RETRY = "drain_then_retry"


@dataclass(frozen=True, slots=True)
class Wits0NormalizationDiagnostic:
    code: Wits0NormalizationCode
    severity: Wits0NormalizationSeverity
    message: str
    source_id: str | None = None


@dataclass(frozen=True, slots=True)
class Wits0NormalizedMeasurement:
    curve_id: str
    source_id: str
    canonical_mnemonic: str
    value: float | None
    source_uom: str | None
    canonical_uom: str | None
    diagnostics: tuple[Wits0NormalizationDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        for value, label in (
            (self.curve_id, "curve_id"),
            (self.source_id, "source_id"),
            (self.canonical_mnemonic, "canonical_mnemonic"),
        ):
            _required_text(value, label)
        if self.value is not None and not isfinite(float(self.value)):
            raise ValueError("Normalized measurement value must be finite or None")


@dataclass(frozen=True, slots=True)
class Wits0MeasurementBatch:
    batch_id: str
    schema_digest: str
    record_no: int
    source_sequence_no: int | None
    sequence_status: Wits0SequenceStatus
    index_values: tuple[tuple[str, float | int], ...]
    measurements: tuple[Wits0NormalizedMeasurement, ...]
    received_at: str
    source_ref: str | None
    raw_sha256: str
    diagnostics: tuple[Wits0NormalizationDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        _required_text(self.batch_id, "batch_id")
        if not _is_sha256(self.schema_digest) or not _is_sha256(self.raw_sha256):
            raise ValueError("schema_digest/raw_sha256 must be SHA-256 hex digests")
        if isinstance(self.record_no, bool) or not 0 <= self.record_no <= 99:
            raise ValueError("record_no must be in the range 0..99")
        if self.source_sequence_no is not None and (
            isinstance(self.source_sequence_no, bool) or self.source_sequence_no < 0
        ):
            raise ValueError("source_sequence_no must be non-negative or None")
        if not isinstance(self.sequence_status, Wits0SequenceStatus):
            raise ValueError("sequence_status must use Wits0SequenceStatus")
        if not self.index_values:
            raise ValueError("Normalized WITS0 batch requires an index")
        if len({item[0] for item in self.index_values}) != len(self.index_values):
            raise ValueError("index_values must not contain duplicate IDs")
        if len({item.curve_id for item in self.measurements}) != len(self.measurements):
            raise ValueError("measurements must not contain duplicate curve IDs")
        object.__setattr__(self, "received_at", canonical_acquisition_timestamp(self.received_at))

    @property
    def non_null_count(self) -> int:
        return sum(item.value is not None for item in self.measurements)

    def to_acquisition_record(self, sequence: int) -> AcquisitionRecord:
        source_parts = [
            f"wits0:record={self.record_no:02d}",
            f"sequence-status={self.sequence_status.value}",
            f"raw-sha256={self.raw_sha256}",
        ]
        if self.source_sequence_no is not None:
            source_parts.append(f"source-sequence={self.source_sequence_no}")
        if self.source_ref:
            source_parts.append(f"ref={self.source_ref}")
        quality_entries = sorted(
            {
                f"{measurement.source_id}:{diagnostic.code.value}"
                for measurement in self.measurements
                for diagnostic in measurement.diagnostics
            }
        )
        if quality_entries:
            source_parts.append(f"quality={','.join(quality_entries)}")
        frame_quality = sorted(
            {
                diagnostic.code.value
                for diagnostic in self.diagnostics
                if diagnostic.source_id is None
            }
        )
        if frame_quality:
            source_parts.append(f"frame-quality={','.join(frame_quality)}")
        return AcquisitionRecord(
            record_id=f"wits0-{self.batch_id}",
            sequence=sequence,
            kind=AcquisitionRecordKind.DATA_ROW,
            payload=AcquisitionDataRowPayload(
                index_values=self.index_values,
                curve_values=tuple(
                    (item.curve_id, item.value) for item in self.measurements
                ),
            ),
            received_at=self.received_at,
            source=";".join(source_parts),
        )


@dataclass(frozen=True, slots=True)
class Wits0NormalizationResult:
    batch: Wits0MeasurementBatch | None
    diagnostics: tuple[Wits0NormalizationDiagnostic, ...]

    @property
    def accepted(self) -> bool:
        return self.batch is not None


@dataclass(frozen=True, slots=True)
class Wits0FrameNormalizerPolicy:
    skip_duplicate_sequences: bool = True
    skip_out_of_order_sequences: bool = True
    skip_invalid_sequences: bool = True
    require_received_at: bool = True
    skip_empty_rows: bool = True


class Wits0FrameNormalizer:
    """Convert reviewed WITS0 frames into deterministic normalized measurement batches."""

    def __init__(
        self,
        commit: Wits0ImportReviewCommit,
        *,
        policy: Wits0FrameNormalizerPolicy | None = None,
    ) -> None:
        if acquisition_schema_digest(commit.schema) != commit.schema_digest:
            raise ValueError("WITS0 Import Review commit schema digest is invalid")
        self.commit = commit
        self.schema = commit.schema
        self.policy = policy or Wits0FrameNormalizerPolicy()
        self._index = self.schema.indexes[0]
        self._selected_index = commit.review.selected_index
        if self._selected_index is None:
            raise ValueError("WITS0 Import Review commit has no selected index")
        self._curve_by_key: dict[Wits0ChannelKey, object] = {}
        for curve in self.schema.curves:
            provenance = curve.metadata.provenance
            if not provenance.startswith("wits0:"):
                raise ValueError(f"Unsupported WITS0 curve provenance: {provenance}")
            key = Wits0ChannelKey.parse(provenance.removeprefix("wits0:"))
            if key in self._curve_by_key:
                raise ValueError(f"Duplicate WITS0 curve mapping: {key.source_id}")
            self._curve_by_key[key] = curve

    def normalize(self, frame: Wits0ParsedFrame) -> Wits0NormalizationResult:
        diagnostics: list[Wits0NormalizationDiagnostic] = []
        if frame.record_no is None:
            return self._rejected(
                Wits0NormalizationCode.FRAME_WITHOUT_RECORD,
                "WITS0 frame does not resolve to one record number",
            )
        sequence_rejection = self._sequence_rejection(frame)
        if sequence_rejection is not None:
            return sequence_rejection

        received_at = self._received_at(frame, diagnostics)
        if received_at is None:
            return Wits0NormalizationResult(None, tuple(diagnostics))
        index_value = self._index_value(frame, diagnostics)
        if index_value is None:
            return Wits0NormalizationResult(None, tuple(diagnostics))

        field_by_key = {
            Wits0ChannelKey(field.record_no, field.item_no): field
            for field in frame.fields
        }
        measurements: list[Wits0NormalizedMeasurement] = []
        for key, curve_schema in sorted(
            self._curve_by_key.items(), key=lambda item: item[0]
        ):
            metadata = curve_schema.metadata
            field = field_by_key.get(key)
            measurement_diagnostics: list[Wits0NormalizationDiagnostic] = []
            value: float | None = None
            if field is None:
                measurement_diagnostics.append(
                    Wits0NormalizationDiagnostic(
                        Wits0NormalizationCode.MISSING_CURVE_VALUE,
                        Wits0NormalizationSeverity.INFO,
                        f"WITS0 field {key.source_id} is absent from this frame",
                        key.source_id,
                    )
                )
            else:
                value = self._numeric_field_value(field, measurement_diagnostics)
            measurements.append(
                Wits0NormalizedMeasurement(
                    curve_id=metadata.curve_id,
                    source_id=key.source_id,
                    canonical_mnemonic=metadata.canonical_mnemonic
                    or metadata.original_mnemonic,
                    value=value,
                    source_uom=(field.source_unit if field is not None else None),
                    canonical_uom=metadata.unit,
                    diagnostics=tuple(measurement_diagnostics),
                )
            )
            diagnostics.extend(measurement_diagnostics)

        if self.policy.skip_empty_rows and not any(
            item.value is not None for item in measurements
        ):
            diagnostics.append(
                Wits0NormalizationDiagnostic(
                    Wits0NormalizationCode.EMPTY_MEASUREMENT_ROW,
                    Wits0NormalizationSeverity.WARNING,
                    "WITS0 frame contains no enabled numeric curve values",
                )
            )
            return Wits0NormalizationResult(None, tuple(diagnostics))

        raw_sha = sha256(frame.raw_frame).hexdigest()
        identity = "|".join(
            (
                self.commit.schema_digest,
                f"record={frame.record_no:02d}",
                f"source-sequence={frame.sequence_no}",
                f"index={index_value}",
                f"received-at={received_at}",
                raw_sha,
            )
        )
        batch_id = sha256(identity.encode("utf-8")).hexdigest()
        batch = Wits0MeasurementBatch(
            batch_id=batch_id,
            schema_digest=self.commit.schema_digest,
            record_no=frame.record_no,
            source_sequence_no=frame.sequence_no,
            sequence_status=frame.sequence_status,
            index_values=((self._index.index_id, index_value),),
            measurements=tuple(measurements),
            received_at=received_at,
            source_ref=frame.source_ref,
            raw_sha256=raw_sha,
            diagnostics=tuple(diagnostics),
        )
        return Wits0NormalizationResult(batch, tuple(diagnostics))

    def normalize_many(
        self,
        frames: Iterable[Wits0ParsedFrame],
    ) -> tuple[Wits0NormalizationResult, ...]:
        return tuple(self.normalize(frame) for frame in frames)

    def _sequence_rejection(
        self,
        frame: Wits0ParsedFrame,
    ) -> Wits0NormalizationResult | None:
        if (
            frame.sequence_status is Wits0SequenceStatus.DUPLICATE
            and self.policy.skip_duplicate_sequences
        ):
            return self._rejected(
                Wits0NormalizationCode.DUPLICATE_SEQUENCE_SKIPPED,
                "Duplicate WITS0 source sequence was not appended",
            )
        if (
            frame.sequence_status is Wits0SequenceStatus.OUT_OF_ORDER
            and self.policy.skip_out_of_order_sequences
        ):
            return self._rejected(
                Wits0NormalizationCode.OUT_OF_ORDER_SEQUENCE_SKIPPED,
                "Out-of-order WITS0 source sequence was not appended",
            )
        if (
            frame.sequence_status is Wits0SequenceStatus.INVALID
            and self.policy.skip_invalid_sequences
        ):
            return self._rejected(
                Wits0NormalizationCode.INVALID_SEQUENCE_SKIPPED,
                "Invalid WITS0 source sequence was not appended",
            )
        return None

    def _received_at(
        self,
        frame: Wits0ParsedFrame,
        diagnostics: list[Wits0NormalizationDiagnostic],
    ) -> str | None:
        if frame.received_at:
            try:
                return canonical_acquisition_timestamp(frame.received_at)
            except ValueError:
                diagnostics.append(
                    Wits0NormalizationDiagnostic(
                        Wits0NormalizationCode.INVALID_RECEIVED_AT,
                        Wits0NormalizationSeverity.ERROR,
                        f"Invalid frame received_at timestamp: {frame.received_at}",
                    )
                )
                return None
        if self.policy.require_received_at:
            diagnostics.append(
                Wits0NormalizationDiagnostic(
                    Wits0NormalizationCode.MISSING_RECEIVED_AT,
                    Wits0NormalizationSeverity.ERROR,
                    "WITS0 frame has no deterministic reception timestamp",
                )
            )
            return None
        index_timestamp = self._header_datetime(frame, diagnostics)
        if index_timestamp is None:
            return None
        return index_timestamp.astimezone(timezone.utc).isoformat(
            timespec="microseconds"
        ).replace("+00:00", "Z")

    def _index_value(
        self,
        frame: Wits0ParsedFrame,
        diagnostics: list[Wits0NormalizationDiagnostic],
    ) -> float | int | None:
        selected = self._selected_index
        if selected.source_kind == "header_datetime":
            parsed = self._header_datetime(frame, diagnostics)
            if parsed is None:
                return None
            timestamp = parsed.astimezone(timezone.utc).isoformat(
                timespec="microseconds"
            ).replace("+00:00", "Z")
            return acquisition_timestamp_to_ns(timestamp)
        key = selected.channel_key
        if key is None:
            diagnostics.append(
                Wits0NormalizationDiagnostic(
                    Wits0NormalizationCode.MISSING_INDEX,
                    Wits0NormalizationSeverity.ERROR,
                    "Selected WITS0 field index has no source key",
                )
            )
            return None
        field = frame.field(key.record_no, key.item_no)
        if field is None:
            diagnostics.append(
                Wits0NormalizationDiagnostic(
                    Wits0NormalizationCode.MISSING_INDEX,
                    Wits0NormalizationSeverity.WARNING,
                    f"Selected index field {key.source_id} is absent from this frame",
                    key.source_id,
                )
            )
            return None
        value = self._numeric_field_value(field, diagnostics, is_index=True)
        if value is None:
            return None
        if self._index.index_type is IndexType.DATETIME:
            diagnostics.append(
                Wits0NormalizationDiagnostic(
                    Wits0NormalizationCode.INVALID_INDEX,
                    Wits0NormalizationSeverity.ERROR,
                    "DATETIME index cannot be supplied by a plain numeric WITS0 field",
                    key.source_id,
                )
            )
            return None
        return value

    def _header_datetime(
        self,
        frame: Wits0ParsedFrame,
        diagnostics: list[Wits0NormalizationDiagnostic],
    ) -> datetime | None:
        date_field = frame.field(frame.record_no or 0, 5)
        time_field = frame.field(frame.record_no or 0, 6)
        if (
            date_field is None
            or time_field is None
            or not isinstance(date_field.value, date)
            or not isinstance(time_field.value, time)
        ):
            diagnostics.append(
                Wits0NormalizationDiagnostic(
                    Wits0NormalizationCode.MISSING_INDEX,
                    Wits0NormalizationSeverity.WARNING,
                    "WITS0 header date/time items 05 and 06 are required for this row",
                )
            )
            return None
        timezone_name = self._index.timezone
        if not timezone_name:
            diagnostics.append(
                Wits0NormalizationDiagnostic(
                    Wits0NormalizationCode.MISSING_TIMEZONE,
                    Wits0NormalizationSeverity.ERROR,
                    "DATETIME acquisition index requires an explicit timezone",
                )
            )
            return None
        try:
            zone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            diagnostics.append(
                Wits0NormalizationDiagnostic(
                    Wits0NormalizationCode.UNKNOWN_TIMEZONE,
                    Wits0NormalizationSeverity.ERROR,
                    f"Unknown timezone: {timezone_name}",
                )
            )
            return None
        return datetime.combine(date_field.value, time_field.value, tzinfo=zone)

    @staticmethod
    def _numeric_field_value(
        field: Wits0ParsedField,
        diagnostics: list[Wits0NormalizationDiagnostic],
        *,
        is_index: bool = False,
    ) -> float | None:
        if field.value is None or field.has_error:
            diagnostics.append(
                Wits0NormalizationDiagnostic(
                    Wits0NormalizationCode.INVALID_INDEX
                    if is_index
                    else Wits0NormalizationCode.INVALID_CURVE_VALUE,
                    Wits0NormalizationSeverity.ERROR if is_index else Wits0NormalizationSeverity.WARNING,
                    f"WITS0 field {field.record_no:02d}{field.item_no:02d} has no valid numeric value",
                    f"{field.record_no:02d}{field.item_no:02d}",
                )
            )
            return None
        if isinstance(field.value, bool):
            numeric_value: float | int | None = None
        elif isinstance(field.value, (int, float)):
            numeric_value = field.value
        elif isinstance(field.value, str):
            candidate = field.raw_value.strip().replace(",", ".")
            try:
                numeric_value = float(candidate)
            except ValueError:
                numeric_value = None
        else:
            numeric_value = None
        if numeric_value is None:
            diagnostics.append(
                Wits0NormalizationDiagnostic(
                    Wits0NormalizationCode.INVALID_INDEX
                    if is_index
                    else Wits0NormalizationCode.INVALID_CURVE_VALUE,
                    Wits0NormalizationSeverity.ERROR if is_index else Wits0NormalizationSeverity.WARNING,
                    f"WITS0 field {field.record_no:02d}{field.item_no:02d} is not numeric",
                    f"{field.record_no:02d}{field.item_no:02d}",
                )
            )
            return None
        value = float(numeric_value)
        if not isfinite(value):
            diagnostics.append(
                Wits0NormalizationDiagnostic(
                    Wits0NormalizationCode.INVALID_INDEX
                    if is_index
                    else Wits0NormalizationCode.INVALID_CURVE_VALUE,
                    Wits0NormalizationSeverity.ERROR if is_index else Wits0NormalizationSeverity.WARNING,
                    f"WITS0 field {field.record_no:02d}{field.item_no:02d} is non-finite",
                    f"{field.record_no:02d}{field.item_no:02d}",
                )
            )
            return None
        return value

    @staticmethod
    def _rejected(
        code: Wits0NormalizationCode,
        message: str,
    ) -> Wits0NormalizationResult:
        diagnostic = Wits0NormalizationDiagnostic(
            code,
            Wits0NormalizationSeverity.WARNING,
            message,
        )
        return Wits0NormalizationResult(None, (diagnostic,))


@dataclass(frozen=True, slots=True)
class Wits0AcquisitionConfig:
    max_pending_records: int = 256
    drain_batch_size: int = 64
    checkpoint_every_records: int = 500
    checkpoint_interval_seconds: float = 60.0
    backpressure_policy: Wits0BackpressurePolicy = Wits0BackpressurePolicy.RAISE

    def __post_init__(self) -> None:
        for value, label in (
            (self.max_pending_records, "max_pending_records"),
            (self.drain_batch_size, "drain_batch_size"),
            (self.checkpoint_every_records, "checkpoint_every_records"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{label} must be a positive integer")
        if (
            isinstance(self.checkpoint_interval_seconds, bool)
            or not isinstance(self.checkpoint_interval_seconds, (int, float))
            or self.checkpoint_interval_seconds <= 0
        ):
            raise ValueError("checkpoint_interval_seconds must be positive")
        if not isinstance(self.backpressure_policy, Wits0BackpressurePolicy):
            raise ValueError("backpressure_policy must use Wits0BackpressurePolicy")


@dataclass(frozen=True, slots=True)
class Wits0AcquisitionSnapshot:
    state: Wits0AcquisitionState
    session_id: str
    pending_records: int
    queue_capacity: int
    queue_remaining_capacity: int
    frames_submitted: int
    batches_normalized: int
    frames_skipped: int
    records_enqueued: int
    records_applied: int
    backpressure_count: int
    checkpoints_created: int
    last_checkpoint_sequence: int
    last_applied_sequence: int
    last_error: str | None


class Wits0AcquisitionBackpressureError(AcquisitionBackpressureError):
    """WITS0-specific backpressure signal with a stable public exception type."""


class Wits0AcquisitionRuntime:
    """Coordinate normalization, bounded enqueue, draining, checkpoints, and close."""

    def __init__(
        self,
        well: Well,
        commit: Wits0ImportReviewCommit,
        *,
        session_id: str,
        session: AcquisitionSession | None = None,
        config: Wits0AcquisitionConfig | None = None,
        normalizer_policy: Wits0FrameNormalizerPolicy | None = None,
        monotonic: Callable[[], float] = time_module.monotonic,
    ) -> None:
        _required_text(session_id, "session_id")
        self.config = config or Wits0AcquisitionConfig()
        self.normalizer = Wits0FrameNormalizer(commit, policy=normalizer_policy)
        if session is None:
            session = AcquisitionSession(session_id, well.well_id, commit.schema)
        elif session.session_id != session_id:
            raise ValueError("session_id does not match the supplied AcquisitionSession")
        elif session.dataset_schema != commit.schema:
            raise AcquisitionConflictError(
                "Persisted acquisition session schema differs from WITS0 Import Review"
            )
        if session.state is not AcquisitionSessionState.OPEN:
            raise AcquisitionConflictError("Cannot resume a closed acquisition session")
        self.controller = AcquisitionController(
            well,
            session,
            max_pending_records=self.config.max_pending_records,
        )
        self.session = session
        self.state = Wits0AcquisitionState.OPEN
        self._monotonic = monotonic
        self._last_checkpoint_clock = float(monotonic())
        self._frames_submitted = 0
        self._batches_normalized = 0
        self._frames_skipped = 0
        # Session-level counters remain meaningful when an open persisted session
        # is resumed after project reload. Frame counters below are runtime-local.
        self._records_enqueued = session.last_sequence
        self._records_applied = session.last_sequence
        self._backpressure_count = 0
        self._checkpoints_created = len(session.checkpoints)
        self._last_error: str | None = None

    def submit_frame(self, frame: Wits0ParsedFrame) -> Wits0NormalizationResult:
        self._require_open()
        self._frames_submitted += 1
        result = self.normalizer.normalize(frame)
        if result.batch is None:
            self._frames_skipped += 1
            return result
        self.submit_batches((result.batch,))
        return result

    def submit_frames(
        self,
        frames: Iterable[Wits0ParsedFrame],
    ) -> tuple[Wits0NormalizationResult, ...]:
        results: list[Wits0NormalizationResult] = []
        for frame in frames:
            results.append(self.submit_frame(frame))
        return tuple(results)

    def submit_batches(self, batches: Iterable[Wits0MeasurementBatch]) -> None:
        self._require_open()
        materialized = tuple(batches)
        if not materialized:
            return
        for batch in materialized:
            if batch.schema_digest != self.normalizer.commit.schema_digest:
                raise AcquisitionConflictError(
                    "Normalized WITS0 batch belongs to another acquisition schema"
                )
        records = self._records_for_batches(materialized)
        self._enqueue_records(records)
        self._batches_normalized += len(materialized)

    def submit_connection_event(
        self,
        *,
        connected: bool,
        occurred_at: str,
        connection_id: str,
        peer: str | None = None,
        reason: str | None = None,
        raw_file: str | None = None,
        bytes_received: int = 0,
        frames_received: int = 0,
    ) -> AcquisitionRecord:
        """Append one connection/disconnection event through the same bounded queue."""

        self._require_open()
        timestamp = canonical_acquisition_timestamp(occurred_at)
        state = "connected" if connected else "disconnected"
        event_id = sha256(
            "|".join(
                (
                    self.session.session_id,
                    "connection",
                    connection_id,
                    state,
                    timestamp,
                )
            ).encode("utf-8")
        ).hexdigest()
        event = OperationalEvent(
            event_id=event_id,
            well_id=self.session.well_id,
            kind=OperationalEventKind.CONNECTION,
            payload=ConnectionEventPayload(
                state=state,
                connection_id=connection_id,
                peer=peer,
                reason=reason,
                raw_file=raw_file,
                bytes_received=bytes_received,
                frames_received=frames_received,
            ),
            measured_at=timestamp,
            received_at=timestamp,
            source="wits0:connection",
        )
        sequence = self.session.last_sequence + self.controller.pending_count + 1
        record = AcquisitionRecord(
            record_id=f"{self.session.session_id}:connection:{event_id}",
            sequence=sequence,
            kind=AcquisitionRecordKind.EVENT_UPSERT,
            payload=AcquisitionEventUpsertPayload(event),
            received_at=timestamp,
            source=(
                f"wits0:connection;state={state};connection-id={connection_id};"
                f"peer={peer or ''};reason={reason or ''};raw={raw_file or ''}"
            ),
        )
        self._enqueue_records((record,))
        return record

    def drain(self, *, limit: int | None = None) -> tuple[AcquisitionApplyResult, ...]:
        self._require_not_closed()
        results = self.controller.drain(limit=limit)
        self._records_applied += len(results)
        if self.controller.pending_count == 0:
            self._create_checkpoint_if_due()
        return results

    def flush(self) -> tuple[AcquisitionApplyResult, ...]:
        return self.drain(limit=None)

    def create_checkpoint(
        self,
        *,
        created_at: str | None = None,
        force: bool = False,
    ) -> AcquisitionCheckpoint | None:
        self._require_open()
        if self.controller.pending_count:
            raise AcquisitionConflictError(
                "WITS0 checkpoint requires an empty pending queue"
            )
        sequence = self.session.last_sequence
        if not force and sequence == self.last_checkpoint_sequence:
            return None
        checkpoint = self.controller.create_checkpoint(
            self._checkpoint_id(sequence),
            created_at=created_at or _utc_now(),
        )
        self._checkpoints_created += 1
        self._last_checkpoint_clock = float(self._monotonic())
        return checkpoint

    def close(self, *, closed_at: str | None = None) -> AcquisitionCheckpoint:
        self._require_open()
        self.state = Wits0AcquisitionState.CLOSING
        timestamp = closed_at or _utc_now()
        try:
            self.controller.drain(limit=None)
            # drain() above intentionally bypasses runtime counters only during close;
            # update from the authoritative session sequence delta.
            self._records_applied = self.session.last_sequence
            checkpoint = self.controller.close(
                checkpoint_id=self._final_checkpoint_id(self.session.last_sequence),
                closed_at=timestamp,
            )
            self._checkpoints_created += 1
            self._last_checkpoint_clock = float(self._monotonic())
            self.state = Wits0AcquisitionState.CLOSED
            return checkpoint
        except Exception as exc:
            self._last_error = str(exc)
            self.state = Wits0AcquisitionState.FAILED
            raise

    @property
    def last_checkpoint_sequence(self) -> int:
        if not self.session.checkpoints:
            return 0
        return self.session.checkpoints[-1].sequence

    def snapshot(self) -> Wits0AcquisitionSnapshot:
        return Wits0AcquisitionSnapshot(
            state=self.state,
            session_id=self.session.session_id,
            pending_records=self.controller.pending_count,
            queue_capacity=self.config.max_pending_records,
            queue_remaining_capacity=self.controller.remaining_capacity,
            frames_submitted=self._frames_submitted,
            batches_normalized=self._batches_normalized,
            frames_skipped=self._frames_skipped,
            records_enqueued=self._records_enqueued,
            records_applied=self._records_applied,
            backpressure_count=self._backpressure_count,
            checkpoints_created=self._checkpoints_created,
            last_checkpoint_sequence=self.last_checkpoint_sequence,
            last_applied_sequence=self.session.last_sequence,
            last_error=self._last_error,
        )

    def _enqueue_records(self, records: tuple[AcquisitionRecord, ...]) -> None:
        try:
            self.controller.enqueue_many(records)
        except AcquisitionBackpressureError as exc:
            self._backpressure_count += 1
            if self.config.backpressure_policy is Wits0BackpressurePolicy.DRAIN_THEN_RETRY:
                self.drain(limit=self.config.drain_batch_size)
                try:
                    self.controller.enqueue_many(records)
                except AcquisitionBackpressureError as retry_exc:
                    self._last_error = str(retry_exc)
                    raise Wits0AcquisitionBackpressureError(str(retry_exc)) from retry_exc
            else:
                self._last_error = str(exc)
                raise Wits0AcquisitionBackpressureError(str(exc)) from exc
        self._records_enqueued += len(records)

    def _records_for_batches(
        self,
        batches: tuple[Wits0MeasurementBatch, ...],
    ) -> tuple[AcquisitionRecord, ...]:
        start = self.session.last_sequence + self.controller.pending_count + 1
        return tuple(
            batch.to_acquisition_record(start + offset)
            for offset, batch in enumerate(batches)
        )

    def _create_checkpoint_if_due(self) -> AcquisitionCheckpoint | None:
        sequence_delta = self.session.last_sequence - self.last_checkpoint_sequence
        elapsed = float(self._monotonic()) - self._last_checkpoint_clock
        if sequence_delta < self.config.checkpoint_every_records and elapsed < float(
            self.config.checkpoint_interval_seconds
        ):
            return None
        if self.session.last_sequence == self.last_checkpoint_sequence:
            self._last_checkpoint_clock = float(self._monotonic())
            return None
        return self.create_checkpoint(force=True)

    def _checkpoint_id(self, sequence: int) -> str:
        return f"{self.session.session_id}:checkpoint:{sequence:012d}"

    def _final_checkpoint_id(self, sequence: int) -> str:
        return f"{self.session.session_id}:final:{sequence:012d}"

    def _require_open(self) -> None:
        if self.state is not Wits0AcquisitionState.OPEN:
            raise AcquisitionConflictError(
                f"WITS0 acquisition runtime is not open: {self.state.value}"
            )

    def _require_not_closed(self) -> None:
        if self.state in {Wits0AcquisitionState.CLOSED, Wits0AcquisitionState.FAILED}:
            raise AcquisitionConflictError(
                f"WITS0 acquisition runtime cannot drain in state {self.state.value}"
            )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _required_text(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")


def _is_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True
