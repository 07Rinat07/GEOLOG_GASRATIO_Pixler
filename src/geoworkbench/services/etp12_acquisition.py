from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
from math import isfinite
import re
import time as time_module
from typing import Callable, Iterable, Mapping

from geoworkbench.domain.acquisition import (
    AcquisitionCheckpoint,
    AcquisitionCurveSchema,
    AcquisitionDataRowPayload,
    AcquisitionRecord,
    AcquisitionRecordKind,
    AcquisitionSession,
    AcquisitionSessionState,
    canonical_acquisition_timestamp,
)
from geoworkbench.domain.models import IndexType, Well
from geoworkbench.importers.etp12.models import Etp12ChannelBatch, Etp12ChannelMetadata
from geoworkbench.services.acquisition import (
    AcquisitionApplyResult,
    AcquisitionBackpressureError,
    AcquisitionConflictError,
    AcquisitionController,
)
from geoworkbench.services.etp12_import_review import Etp12ImportReviewCommit
from geoworkbench.services.uom_dictionary import UomDictionary, default_uom_dictionary
from geoworkbench.services.wits0_import_review import acquisition_schema_digest


_POINT_HASH_TOKEN = re.compile(r"(?:^|;)point-sha256=([0-9a-f,]+)(?:;|$)")


class Etp12NormalizationSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Etp12NormalizationCode(StrEnum):
    SUBSCRIPTION_MISMATCH = "subscription_mismatch"
    UNKNOWN_CHANNEL_ID = "unknown_channel_id"
    CHANNEL_NOT_SELECTED = "channel_not_selected"
    INVALID_INDEX = "invalid_index"
    INVALID_VALUE = "invalid_value"
    UOM_CONVERSION_FAILED = "uom_conversion_failed"
    DUPLICATE_POINT_IN_BATCH = "duplicate_point_in_batch"
    CONFLICTING_POINT_IN_BATCH = "conflicting_point_in_batch"
    EMPTY_BATCH = "empty_batch"
    OVERLAP_POINT_DROPPED = "overlap_point_dropped"
    OVERLAP_BATCH_DROPPED = "overlap_batch_dropped"


@dataclass(frozen=True, slots=True)
class Etp12NormalizationDiagnostic:
    code: Etp12NormalizationCode
    severity: Etp12NormalizationSeverity
    message: str
    channel_uri: str | None = None


@dataclass(frozen=True, slots=True)
class Etp12NormalizedMeasurement:
    curve_id: str
    channel_uri: str
    canonical_mnemonic: str
    value: float | None
    source_uom: str | None
    canonical_uom: str | None
    point_sha256: str | None
    diagnostics: tuple[Etp12NormalizationDiagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class Etp12MeasurementBatch:
    batch_id: str
    schema_digest: str
    subscription_id: str
    generation: int
    index_values: tuple[tuple[str, float | int], ...]
    measurements: tuple[Etp12NormalizedMeasurement, ...]
    received_at: str
    message_id: int
    correlation_id: int
    protocol: int
    point_hashes: tuple[str, ...]
    diagnostics: tuple[Etp12NormalizationDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        if len(self.batch_id) != 64 or len(self.schema_digest) != 64:
            raise ValueError("batch_id/schema_digest must be SHA-256 digests")
        if self.generation < 1:
            raise ValueError("generation must be positive")
        if not self.index_values:
            raise ValueError("ETP measurement batch requires an index")
        if len({item.curve_id for item in self.measurements}) != len(self.measurements):
            raise ValueError("measurements contain duplicate curve ids")
        if len(set(self.point_hashes)) != len(self.point_hashes):
            raise ValueError("point_hashes must be unique")
        object.__setattr__(self, "received_at", canonical_acquisition_timestamp(self.received_at))

    def with_measurements(
        self,
        measurements: tuple[Etp12NormalizedMeasurement, ...],
        point_hashes: tuple[str, ...],
        diagnostics: tuple[Etp12NormalizationDiagnostic, ...],
    ) -> "Etp12MeasurementBatch":
        identity = "|".join(
            (
                self.schema_digest,
                self.subscription_id,
                str(self.index_values),
                ",".join(sorted(point_hashes)),
            )
        )
        return replace(
            self,
            batch_id=sha256(identity.encode("utf-8")).hexdigest(),
            measurements=measurements,
            point_hashes=point_hashes,
            diagnostics=diagnostics,
        )

    def to_acquisition_record(self, sequence: int) -> AcquisitionRecord:
        source = (
            f"etp12:subscription={self.subscription_id};generation={self.generation};"
            f"message-id={self.message_id};correlation-id={self.correlation_id};"
            f"point-sha256={','.join(self.point_hashes)}"
        )
        quality = sorted({item.code.value for item in self.diagnostics})
        if quality:
            source += ";quality=" + ",".join(quality)
        return AcquisitionRecord(
            record_id=f"etp12-{self.batch_id}",
            sequence=sequence,
            kind=AcquisitionRecordKind.DATA_ROW,
            payload=AcquisitionDataRowPayload(
                index_values=self.index_values,
                curve_values=tuple((item.curve_id, item.value) for item in self.measurements),
            ),
            received_at=self.received_at,
            source=source,
        )


@dataclass(frozen=True, slots=True)
class Etp12NormalizationResult:
    batches: tuple[Etp12MeasurementBatch, ...]
    diagnostics: tuple[Etp12NormalizationDiagnostic, ...]

    @property
    def accepted(self) -> bool:
        return bool(self.batches)


class Etp12ChannelNormalizer:
    """Convert ETP ChannelData points into deterministic schema-complete rows."""

    def __init__(
        self,
        commit: Etp12ImportReviewCommit,
        metadata: Mapping[str, Etp12ChannelMetadata] | Iterable[Etp12ChannelMetadata] = (),
        *,
        uoms: UomDictionary | None = None,
    ) -> None:
        if acquisition_schema_digest(commit.schema) != commit.schema_digest:
            raise ValueError("ETP Import Review schema digest is invalid")
        self.commit = commit
        self.schema = commit.schema
        self.uoms = uoms or default_uom_dictionary()
        self._index = self.schema.indexes[0]
        self._curve_by_uri: dict[str, AcquisitionCurveSchema] = {}
        self._source_uom_by_uri: dict[str, str | None] = {}
        override_by_uri = {item.channel_uri: item for item in commit.plan.channels}
        for curve in self.schema.curves:
            provenance = curve.metadata.provenance
            if not provenance.startswith("etp12:"):
                raise ValueError(f"Unsupported ETP curve provenance: {provenance}")
            uri = provenance.removeprefix("etp12:")
            self._curve_by_uri[uri] = curve
            self._source_uom_by_uri[uri] = override_by_uri[uri].source_uom
        self._id_to_uri: dict[int, str] = {}
        self.update_metadata(metadata)

    def update_metadata(
        self,
        metadata: Mapping[str, Etp12ChannelMetadata] | Iterable[Etp12ChannelMetadata],
    ) -> None:
        values = metadata.values() if isinstance(metadata, Mapping) else metadata
        for item in values:
            if not isinstance(item, Etp12ChannelMetadata):
                raise TypeError("metadata must contain Etp12ChannelMetadata")
            self._id_to_uri[item.channel_id] = item.channel_uri

    def normalize(self, batch: Etp12ChannelBatch) -> Etp12NormalizationResult:
        diagnostics: list[Etp12NormalizationDiagnostic] = []
        expected_subscription = self.commit.review.subscription_id
        if expected_subscription and batch.subscription_id != expected_subscription:
            diagnostic = Etp12NormalizationDiagnostic(
                Etp12NormalizationCode.SUBSCRIPTION_MISMATCH,
                Etp12NormalizationSeverity.ERROR,
                f"Batch belongs to {batch.subscription_id}, expected {expected_subscription}",
            )
            return Etp12NormalizationResult((), (diagnostic,))
        id_to_uri = dict(self._id_to_uri)
        id_to_uri.update(
            {int(key): channel_uri for key, channel_uri in batch.channel_uris.items()}
        )
        grouped: dict[float | int, dict[str, tuple[float, str]]] = {}
        grouped_diagnostics: dict[float | int, list[Etp12NormalizationDiagnostic]] = {}
        for point in batch.points:
            uri = id_to_uri.get(point.channel_id)
            if uri is None:
                diagnostics.append(
                    Etp12NormalizationDiagnostic(
                        Etp12NormalizationCode.UNKNOWN_CHANNEL_ID,
                        Etp12NormalizationSeverity.WARNING,
                        f"No URI mapping for ETP channel id {point.channel_id}",
                    )
                )
                continue
            curve = self._curve_by_uri.get(uri)
            if curve is None:
                diagnostics.append(
                    Etp12NormalizationDiagnostic(
                        Etp12NormalizationCode.CHANNEL_NOT_SELECTED,
                        Etp12NormalizationSeverity.INFO,
                        "ETP channel is not enabled by Import Review",
                        uri,
                    )
                )
                continue
            try:
                index_value = self._normalize_index(point.index)
            except (TypeError, ValueError) as exc:
                diagnostics.append(
                    Etp12NormalizationDiagnostic(
                        Etp12NormalizationCode.INVALID_INDEX,
                        Etp12NormalizationSeverity.ERROR,
                        str(exc),
                        uri,
                    )
                )
                continue
            try:
                numeric = self._normalize_value(
                    point.value,
                    self._source_uom_by_uri[uri],
                    curve.metadata.unit,
                )
            except (TypeError, ValueError) as exc:
                diagnostics.append(
                    Etp12NormalizationDiagnostic(
                        Etp12NormalizationCode.INVALID_VALUE,
                        Etp12NormalizationSeverity.WARNING,
                        str(exc),
                        uri,
                    )
                )
                continue
            normalized_point_hash = _point_hash(
                self.commit.schema_digest, uri, index_value, numeric
            )
            row = grouped.setdefault(index_value, {})
            row_diags = grouped_diagnostics.setdefault(index_value, [])
            previous = row.get(uri)
            if previous is not None:
                if previous[0] == numeric:
                    row_diags.append(
                        Etp12NormalizationDiagnostic(
                            Etp12NormalizationCode.DUPLICATE_POINT_IN_BATCH,
                            Etp12NormalizationSeverity.INFO,
                            "Exact duplicate point occurred in one ETP message",
                            uri,
                        )
                    )
                    continue
                row_diags.append(
                    Etp12NormalizationDiagnostic(
                        Etp12NormalizationCode.CONFLICTING_POINT_IN_BATCH,
                        Etp12NormalizationSeverity.WARNING,
                        "Several values exist for the same channel/index; the last value is used",
                        uri,
                    )
                )
            row[uri] = (numeric, normalized_point_hash)

        normalized: list[Etp12MeasurementBatch] = []
        received_at = batch.received_at_utc.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        for index_value in sorted(grouped):
            row = grouped[index_value]
            measurements: list[Etp12NormalizedMeasurement] = []
            hashes: list[str] = []
            row_diags = list(grouped_diagnostics.get(index_value, ()))
            for uri, curve in sorted(self._curve_by_uri.items()):
                current = row.get(uri)
                measurement_value = current[0] if current is not None else None
                measurement_hash = current[1] if current is not None else None
                if measurement_hash is not None:
                    hashes.append(measurement_hash)
                measurements.append(
                    Etp12NormalizedMeasurement(
                        curve_id=curve.metadata.curve_id,
                        channel_uri=uri,
                        canonical_mnemonic=curve.metadata.canonical_mnemonic
                        or curve.metadata.original_mnemonic,
                        value=measurement_value,
                        source_uom=self._source_uom_by_uri[uri],
                        canonical_uom=curve.metadata.unit,
                        point_sha256=measurement_hash,
                    )
                )
            if not hashes:
                continue
            identity = "|".join(
                (
                    self.commit.schema_digest,
                    batch.subscription_id,
                    _stable_number(index_value),
                    ",".join(sorted(hashes)),
                )
            )
            normalized.append(
                Etp12MeasurementBatch(
                    batch_id=sha256(identity.encode("utf-8")).hexdigest(),
                    schema_digest=self.commit.schema_digest,
                    subscription_id=batch.subscription_id,
                    generation=batch.generation,
                    index_values=((self._index.index_id, index_value),),
                    measurements=tuple(measurements),
                    received_at=received_at,
                    message_id=batch.message_id,
                    correlation_id=batch.correlation_id,
                    protocol=int(batch.protocol),
                    point_hashes=tuple(sorted(hashes)),
                    diagnostics=tuple(row_diags),
                )
            )
        if not normalized:
            diagnostics.append(
                Etp12NormalizationDiagnostic(
                    Etp12NormalizationCode.EMPTY_BATCH,
                    Etp12NormalizationSeverity.INFO,
                    "ETP ChannelData contains no enabled valid points",
                )
            )
        return Etp12NormalizationResult(tuple(normalized), tuple(diagnostics))

    def _normalize_index(self, value: object) -> float | int:
        if self._index.index_type is IndexType.DATETIME:
            return _datetime_index_to_ns(value, self.commit.plan.index_source_uom)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"ETP index is not numeric: {value!r}")
        numeric = float(value)
        if not isfinite(numeric):
            raise ValueError("ETP index must be finite")
        if (self.commit.plan.index_source_uom or "").strip().casefold() != (
            self.commit.plan.index_canonical_uom or ""
        ).strip().casefold():
            numeric = self.uoms.convert_scalar(
                numeric,
                self.commit.plan.index_source_uom,
                self.commit.plan.index_canonical_uom,
            )
        return numeric

    def _normalize_value(
        self,
        value: object,
        source_uom: str | None,
        canonical_uom: str | None,
    ) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"ETP channel value is not numeric: {value!r}")
        numeric = float(value)
        if not isfinite(numeric):
            raise ValueError("ETP channel value must be finite")
        if (source_uom or "").strip().casefold() == (canonical_uom or "").strip().casefold():
            return numeric
        return self.uoms.convert_scalar(numeric, source_uom, canonical_uom)


class Etp12BackpressurePolicy(StrEnum):
    RAISE = "raise"
    DRAIN_THEN_RETRY = "drain_then_retry"


class Etp12AcquisitionState(StrEnum):
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Etp12AcquisitionConfig:
    max_pending_records: int = 256
    drain_batch_size: int = 64
    checkpoint_every_records: int = 500
    checkpoint_interval_seconds: float = 60.0
    overlap_window_points: int = 100_000
    backpressure_policy: Etp12BackpressurePolicy = Etp12BackpressurePolicy.RAISE

    def __post_init__(self) -> None:
        for value in (
            self.max_pending_records,
            self.drain_batch_size,
            self.checkpoint_every_records,
            self.overlap_window_points,
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("ETP acquisition integer limits must be positive")
        if self.checkpoint_interval_seconds <= 0:
            raise ValueError("checkpoint_interval_seconds must be positive")


@dataclass(frozen=True, slots=True)
class Etp12AcquisitionSnapshot:
    state: Etp12AcquisitionState
    session_id: str
    pending_records: int
    batches_submitted: int
    rows_normalized: int
    rows_enqueued: int
    records_applied: int
    overlap_points_dropped: int
    overlap_batches_dropped: int
    backpressure_count: int
    checkpoints_created: int
    last_checkpoint_sequence: int
    last_error: str | None


class Etp12OverlapDeduplicator:
    def __init__(self, max_entries: int) -> None:
        self.max_entries = max_entries
        self._order: deque[str] = deque()
        self._seen: set[str] = set()

    def restore(self, session: AcquisitionSession) -> None:
        for record in session.records[-self.max_entries :]:
            for token in extract_point_hashes(record.source):
                self.commit((token,))

    def preview(
        self,
        batches: Iterable[Etp12MeasurementBatch],
    ) -> tuple[tuple[Etp12MeasurementBatch, ...], tuple[str, ...], int, int]:
        accepted: list[Etp12MeasurementBatch] = []
        new_hashes: list[str] = []
        temporary = set(self._seen)
        dropped_points = 0
        dropped_batches = 0
        for batch in batches:
            keep = [item for item in batch.measurements if item.point_sha256 and item.point_sha256 not in temporary]
            dropped_points += len(batch.point_hashes) - len(keep)
            if not keep:
                dropped_batches += 1
                continue
            keep_hashes = tuple(sorted(item.point_sha256 for item in keep if item.point_sha256))
            temporary.update(keep_hashes)
            new_hashes.extend(keep_hashes)
            keep_by_curve = {item.curve_id: item for item in keep}
            measurements = tuple(
                keep_by_curve.get(item.curve_id)
                or replace(item, value=None, point_sha256=None)
                for item in batch.measurements
            )
            diagnostics = batch.diagnostics
            if len(keep_hashes) != len(batch.point_hashes):
                diagnostics = (
                    *diagnostics,
                    Etp12NormalizationDiagnostic(
                        Etp12NormalizationCode.OVERLAP_POINT_DROPPED,
                        Etp12NormalizationSeverity.INFO,
                        "Exact channel/index/value overlap was removed after reconnect",
                    ),
                )
            accepted.append(batch.with_measurements(measurements, keep_hashes, diagnostics))
        return tuple(accepted), tuple(new_hashes), dropped_points, dropped_batches

    def commit(self, hashes: Iterable[str]) -> None:
        for token in hashes:
            if token in self._seen:
                continue
            self._seen.add(token)
            self._order.append(token)
            while len(self._order) > self.max_entries:
                self._seen.discard(self._order.popleft())


class Etp12AcquisitionBackpressureError(AcquisitionBackpressureError):
    pass


class Etp12AcquisitionRuntime:
    """Append-only ETP acquisition with bounded queue and reconnect overlap dedup."""

    def __init__(
        self,
        well: Well,
        commit: Etp12ImportReviewCommit,
        *,
        session_id: str,
        metadata: Mapping[str, Etp12ChannelMetadata] | Iterable[Etp12ChannelMetadata] = (),
        session: AcquisitionSession | None = None,
        config: Etp12AcquisitionConfig | None = None,
        monotonic: Callable[[], float] = time_module.monotonic,
    ) -> None:
        self.config = config or Etp12AcquisitionConfig()
        self.normalizer = Etp12ChannelNormalizer(commit, metadata)
        if session is None:
            session = AcquisitionSession(session_id, well.well_id, commit.schema)
        elif session.session_id != session_id or session.dataset_schema != commit.schema:
            raise AcquisitionConflictError("Persisted ETP session does not match reviewed schema")
        if session.state is not AcquisitionSessionState.OPEN:
            raise AcquisitionConflictError("Cannot resume a closed ETP acquisition session")
        self.controller = AcquisitionController(
            well,
            session,
            max_pending_records=self.config.max_pending_records,
        )
        self.session = session
        self.commit = commit
        self.state = Etp12AcquisitionState.OPEN
        self._dedup = Etp12OverlapDeduplicator(self.config.overlap_window_points)
        self._dedup.restore(session)
        self._monotonic = monotonic
        self._last_checkpoint_clock = float(monotonic())
        self._batches_submitted = 0
        self._rows_normalized = 0
        self._rows_enqueued = session.last_sequence
        self._records_applied = session.last_sequence
        self._overlap_points_dropped = 0
        self._overlap_batches_dropped = 0
        self._backpressure_count = 0
        self._checkpoints_created = len(session.checkpoints)
        self._last_error: str | None = None

    def update_metadata(
        self,
        metadata: Mapping[str, Etp12ChannelMetadata] | Iterable[Etp12ChannelMetadata],
    ) -> None:
        self.normalizer.update_metadata(metadata)

    def submit_channel_batch(self, batch: Etp12ChannelBatch) -> Etp12NormalizationResult:
        self._require_open()
        self._batches_submitted += 1
        result = self.normalizer.normalize(batch)
        self._rows_normalized += len(result.batches)
        accepted, hashes, dropped_points, dropped_batches = self._dedup.preview(result.batches)
        self._overlap_points_dropped += dropped_points
        self._overlap_batches_dropped += dropped_batches
        if not accepted:
            return result
        records = self._records_for_batches(accepted)
        self._enqueue(records)
        self._dedup.commit(hashes)
        self._rows_enqueued += len(records)
        return result

    def submit_channel_batches(
        self, batches: Iterable[Etp12ChannelBatch]
    ) -> tuple[Etp12NormalizationResult, ...]:
        return tuple(self.submit_channel_batch(item) for item in batches)

    def drain(self, *, limit: int | None = None) -> tuple[AcquisitionApplyResult, ...]:
        self._require_not_closed()
        results = self.controller.drain(limit=limit)
        self._records_applied += len(results)
        if self.controller.pending_count == 0:
            self._create_checkpoint_if_due()
        return results

    def flush(self) -> tuple[AcquisitionApplyResult, ...]:
        return self.drain(limit=None)

    def create_checkpoint(self, *, force: bool = False) -> AcquisitionCheckpoint | None:
        self._require_open()
        if self.controller.pending_count:
            raise AcquisitionConflictError("ETP checkpoint requires an empty pending queue")
        if not force and self.session.last_sequence == self.last_checkpoint_sequence:
            return None
        checkpoint = self.controller.create_checkpoint(
            self._checkpoint_id(self.session.last_sequence), created_at=_utc_now()
        )
        self._checkpoints_created += 1
        self._last_checkpoint_clock = float(self._monotonic())
        return checkpoint

    def close(self, *, closed_at: str | None = None) -> AcquisitionCheckpoint:
        self._require_open()
        self.state = Etp12AcquisitionState.CLOSING
        try:
            self.controller.drain(limit=None)
            self._records_applied = self.session.last_sequence
            checkpoint = self.controller.close(
                checkpoint_id=f"etp12-final-{self.session.last_sequence}",
                closed_at=closed_at or _utc_now(),
            )
            self._checkpoints_created += 1
            self.state = Etp12AcquisitionState.CLOSED
            return checkpoint
        except Exception as exc:
            self._last_error = str(exc)
            self.state = Etp12AcquisitionState.FAILED
            raise

    @property
    def last_checkpoint_sequence(self) -> int:
        return self.session.checkpoints[-1].sequence if self.session.checkpoints else 0

    def snapshot(self) -> Etp12AcquisitionSnapshot:
        return Etp12AcquisitionSnapshot(
            state=self.state,
            session_id=self.session.session_id,
            pending_records=self.controller.pending_count,
            batches_submitted=self._batches_submitted,
            rows_normalized=self._rows_normalized,
            rows_enqueued=self._rows_enqueued,
            records_applied=self._records_applied,
            overlap_points_dropped=self._overlap_points_dropped,
            overlap_batches_dropped=self._overlap_batches_dropped,
            backpressure_count=self._backpressure_count,
            checkpoints_created=self._checkpoints_created,
            last_checkpoint_sequence=self.last_checkpoint_sequence,
            last_error=self._last_error,
        )

    def _records_for_batches(
        self, batches: tuple[Etp12MeasurementBatch, ...]
    ) -> tuple[AcquisitionRecord, ...]:
        first = self.session.last_sequence + self.controller.pending_count + 1
        return tuple(item.to_acquisition_record(first + offset) for offset, item in enumerate(batches))

    def _enqueue(self, records: tuple[AcquisitionRecord, ...]) -> None:
        try:
            self.controller.enqueue_many(records)
            return
        except AcquisitionBackpressureError as exc:
            self._backpressure_count += 1
            if self.config.backpressure_policy is Etp12BackpressurePolicy.RAISE:
                raise Etp12AcquisitionBackpressureError(str(exc)) from exc
        self.controller.drain(limit=self.config.drain_batch_size)
        self._records_applied = self.session.last_sequence
        try:
            self.controller.enqueue_many(records)
        except AcquisitionBackpressureError as exc:
            raise Etp12AcquisitionBackpressureError(str(exc)) from exc

    def _create_checkpoint_if_due(self) -> None:
        if self.session.last_sequence == self.last_checkpoint_sequence:
            return
        due_records = (
            self.session.last_sequence - self.last_checkpoint_sequence
            >= self.config.checkpoint_every_records
        )
        due_time = (
            float(self._monotonic()) - self._last_checkpoint_clock
            >= self.config.checkpoint_interval_seconds
        )
        if due_records or due_time:
            self.create_checkpoint(force=True)

    def _checkpoint_id(self, sequence: int) -> str:
        return f"etp12-{self.session.session_id}-{sequence}"

    def _require_open(self) -> None:
        if self.state is not Etp12AcquisitionState.OPEN:
            raise AcquisitionConflictError("ETP acquisition runtime is not open")

    def _require_not_closed(self) -> None:
        if self.state is Etp12AcquisitionState.CLOSED:
            raise AcquisitionConflictError("ETP acquisition runtime is closed")


def extract_point_hashes(source: str) -> tuple[str, ...]:
    match = _POINT_HASH_TOKEN.search(source)
    if match is None:
        return ()
    return tuple(token for token in match.group(1).split(",") if len(token) == 64)


def open_etp12_sessions(well: Well) -> tuple[AcquisitionSession, ...]:
    return tuple(
        item
        for item in well.acquisition_sessions.values()
        if item.state is AcquisitionSessionState.OPEN
        and all(curve.metadata.provenance.startswith("etp12:") for curve in item.dataset_schema.curves)
    )


def _datetime_index_to_ns(value: object, source_uom: str | None) -> int:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("ETP datetime index must include timezone")
        return int(value.astimezone(timezone.utc).timestamp() * 1_000_000_000)
    if isinstance(value, str):
        token = value.strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(token)
        if parsed.tzinfo is None:
            raise ValueError("ETP datetime string must include timezone")
        return int(parsed.astimezone(timezone.utc).timestamp() * 1_000_000_000)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"Unsupported ETP datetime index: {value!r}")
    numeric = float(value)
    if not isfinite(numeric):
        raise ValueError("ETP datetime index must be finite")
    unit = (source_uom or "us").strip().casefold()
    factor = {
        "ns": 1,
        "nanosecond": 1,
        "nanoseconds": 1,
        "us": 1_000,
        "µs": 1_000,
        "microsecond": 1_000,
        "microseconds": 1_000,
        "ms": 1_000_000,
        "millisecond": 1_000_000,
        "s": 1_000_000_000,
        "second": 1_000_000_000,
    }.get(unit)
    if factor is None:
        raise ValueError(f"Unsupported ETP datetime transport unit: {source_uom}")
    return int(round(numeric * factor))


def _point_hash(schema_digest: str, uri: str, index: float | int, value: float) -> str:
    return sha256(
        "|".join((schema_digest, uri, _stable_number(index), _stable_number(value))).encode("utf-8")
    ).hexdigest()


def _stable_number(value: float | int) -> str:
    return str(value) if isinstance(value, int) else format(float(value), ".17g")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
