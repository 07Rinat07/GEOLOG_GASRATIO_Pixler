from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import date, datetime, time
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO, Iterable, Iterator, TypeAlias

from geoworkbench.acquisition.wits0 import (
    Wits0FieldDefinition,
    Wits0FrameDecoder,
    Wits0Profile,
)


from geoworkbench.acquisition.wits0_catalog import load_builtin_wits0_catalog

Wits0TypedValue: TypeAlias = float | int | str | date | time | None


class Wits0DiagnosticSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Wits0DiagnosticCode(StrEnum):
    INVALID_FRAME_MARKERS = "invalid_frame_markers"
    DECODE_ERROR = "decode_error"
    TOO_MANY_LINES = "too_many_lines"
    LINE_TOO_LONG = "line_too_long"
    INVALID_LINE = "invalid_line"
    EMPTY_VALUE = "empty_value"
    VALUE_PARSE_ERROR = "value_parse_error"
    NON_FINITE_NUMBER = "non_finite_number"
    UNKNOWN_RECORD = "unknown_record"
    UNKNOWN_FIELD = "unknown_field"
    DUPLICATE_FIELD = "duplicate_field"
    MIXED_RECORDS = "mixed_records"
    MISSING_SEQUENCE = "missing_sequence"
    INVALID_SEQUENCE = "invalid_sequence"
    SEQUENCE_DUPLICATE = "sequence_duplicate"
    SEQUENCE_GAP = "sequence_gap"
    SEQUENCE_OUT_OF_ORDER = "sequence_out_of_order"


class Wits0SequenceStatus(StrEnum):
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"
    FIRST = "first"
    CONTIGUOUS = "contiguous"
    DUPLICATE = "duplicate"
    GAP = "gap"
    OUT_OF_ORDER = "out_of_order"


@dataclass(frozen=True, slots=True)
class Wits0Diagnostic:
    code: Wits0DiagnosticCode
    severity: Wits0DiagnosticSeverity
    message: str
    line_no: int | None = None
    record_no: int | None = None
    item_no: int | None = None
    raw_line: str | None = None
    expected_sequence: int | None = None
    actual_sequence: int | None = None


@dataclass(frozen=True, slots=True)
class Wits0ParsedField:
    line_no: int
    record_no: int
    item_no: int
    raw_line: str
    raw_value: str
    canonical_mnemonic: str | None
    name_ru: str | None
    source_unit: str | None
    value_kind: str
    aggregation: str | None
    value: Wits0TypedValue
    is_known: bool
    diagnostics: tuple[Wits0Diagnostic, ...] = ()

    @property
    def has_error(self) -> bool:
        return any(
            item.severity is Wits0DiagnosticSeverity.ERROR for item in self.diagnostics
        )


@dataclass(frozen=True, slots=True)
class Wits0ParsedFrame:
    raw_frame: bytes
    raw_text: str
    received_at: str | None
    source_ref: str | None
    record_no: int | None
    sequence_no: int | None
    sequence_status: Wits0SequenceStatus
    fields: tuple[Wits0ParsedField, ...]
    diagnostics: tuple[Wits0Diagnostic, ...]

    @property
    def warning_count(self) -> int:
        return sum(
            item.severity is Wits0DiagnosticSeverity.WARNING
            for item in self.diagnostics
        )

    @property
    def error_count(self) -> int:
        return sum(
            item.severity is Wits0DiagnosticSeverity.ERROR
            for item in self.diagnostics
        )

    @property
    def unknown_field_count(self) -> int:
        return sum(
            item.code is Wits0DiagnosticCode.UNKNOWN_FIELD for item in self.diagnostics
        )

    @property
    def unknown_record_count(self) -> int:
        return sum(
            item.code is Wits0DiagnosticCode.UNKNOWN_RECORD for item in self.diagnostics
        )

    def field(self, record_no: int, item_no: int) -> Wits0ParsedField | None:
        return next(
            (
                item
                for item in self.fields
                if item.record_no == record_no and item.item_no == item_no
            ),
            None,
        )

    def mnemonic(self, canonical_mnemonic: str) -> tuple[Wits0ParsedField, ...]:
        requested = canonical_mnemonic.casefold()
        return tuple(
            item
            for item in self.fields
            if item.canonical_mnemonic is not None
            and item.canonical_mnemonic.casefold() == requested
        )


@dataclass(frozen=True, slots=True)
class Wits0ParserConfig:
    sequence_item_no: int = 4
    max_lines_per_frame: int = 10_000
    max_line_chars: int = 16_384
    accept_decimal_comma: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.sequence_item_no, bool) or not 0 <= self.sequence_item_no <= 99:
            raise ValueError("sequence_item_no must be in the range 0..99")
        if isinstance(self.max_lines_per_frame, bool) or self.max_lines_per_frame < 1:
            raise ValueError("max_lines_per_frame must be positive")
        if isinstance(self.max_line_chars, bool) or self.max_line_chars < 4:
            raise ValueError("max_line_chars must be at least 4")


_STANDARD_HEADER_FIELDS: dict[int, Wits0FieldDefinition] = {
    1: Wits0FieldDefinition(
        item_no=1,
        canonical_mnemonic="WELL_IDENTIFIER",
        name_ru="Идентификатор скважины",
        source_unit=None,
        value_kind="text",
        aggregation="exact",
    ),
    2: Wits0FieldDefinition(
        item_no=2,
        canonical_mnemonic="SIDETRACK_HOLE_SECTION",
        name_ru="Номер бокового ствола или секции скважины",
        source_unit=None,
        value_kind="integer",
        aggregation="exact",
    ),
    3: Wits0FieldDefinition(
        item_no=3,
        canonical_mnemonic="WITS_RECORD_IDENTIFIER",
        name_ru="Идентификатор записи WITS",
        source_unit=None,
        value_kind="integer",
        aggregation="exact",
    ),
    4: Wits0FieldDefinition(
        item_no=4,
        canonical_mnemonic="WITS_SEQUENCE",
        name_ru="Номер последовательности",
        source_unit=None,
        value_kind="integer",
        aggregation="exact",
    ),
    5: Wits0FieldDefinition(
        item_no=5,
        canonical_mnemonic="WITS_DATE",
        name_ru="Дата записи",
        source_unit=None,
        value_kind="date",
        aggregation="exact",
    ),
    6: Wits0FieldDefinition(
        item_no=6,
        canonical_mnemonic="WITS_TIME",
        name_ru="Время записи",
        source_unit=None,
        value_kind="time",
        aggregation="exact",
    ),
    7: Wits0FieldDefinition(
        item_no=7,
        canonical_mnemonic="ACTIVITY_CODE",
        name_ru="Код работы WITS",
        source_unit=None,
        value_kind="integer",
        aggregation="exact",
    ),
}


class Wits0Parser:
    """Parse complete WITS0 frames without mutating sequence state.

    The parser deliberately keeps malformed and unknown fields in the result.  A downstream
    review screen can therefore inspect the original value and amend a profile without replaying
    or losing the raw stream.
    """

    def __init__(
        self,
        profile: Wits0Profile,
        *,
        config: Wits0ParserConfig | None = None,
    ) -> None:
        self.profile = profile
        self.config = config or Wits0ParserConfig()
        self._start_marker = profile.start_marker.encode("ascii")
        self._end_marker = profile.end_marker.encode("ascii")
        self._catalog_definitions: dict[tuple[int, int], Wits0FieldDefinition] = {}
        self._catalog_records: set[int] = set()
        if profile.field_catalog_id is not None:
            catalog = load_builtin_wits0_catalog(profile.field_catalog_id)
            self._catalog_definitions = {
                (field.record_no, field.item_no): field.to_definition()
                for field in catalog.fields
            }
            self._catalog_records = set(catalog.record_numbers)

    def parse(
        self,
        raw_frame: bytes | bytearray | memoryview,
        *,
        received_at: str | None = None,
        source_ref: str | None = None,
    ) -> Wits0ParsedFrame:
        frame = bytes(raw_frame)
        diagnostics: list[Wits0Diagnostic] = []
        body = frame
        if frame.startswith(self._start_marker) and frame.endswith(self._end_marker):
            body = frame[len(self._start_marker) : -len(self._end_marker)]
        else:
            diagnostics.append(
                Wits0Diagnostic(
                    code=Wits0DiagnosticCode.INVALID_FRAME_MARKERS,
                    severity=Wits0DiagnosticSeverity.ERROR,
                    message="WITS0 frame does not have the configured start/end markers",
                )
            )
            if body.startswith(self._start_marker):
                body = body[len(self._start_marker) :]
            if body.endswith(self._end_marker):
                body = body[: -len(self._end_marker)]

        try:
            raw_text = frame.decode(self.profile.encoding, errors="strict")
            body_text = body.decode(self.profile.encoding, errors="strict")
        except UnicodeDecodeError as exc:
            raw_text = frame.decode(self.profile.encoding, errors="replace")
            body_text = body.decode(self.profile.encoding, errors="replace")
            diagnostics.append(
                Wits0Diagnostic(
                    code=Wits0DiagnosticCode.DECODE_ERROR,
                    severity=Wits0DiagnosticSeverity.ERROR,
                    message=f"Cannot decode WITS0 frame as {self.profile.encoding}: {exc}",
                )
            )

        lines = body_text.splitlines()
        if len(lines) > self.config.max_lines_per_frame:
            diagnostics.append(
                Wits0Diagnostic(
                    code=Wits0DiagnosticCode.TOO_MANY_LINES,
                    severity=Wits0DiagnosticSeverity.ERROR,
                    message=(
                        f"WITS0 frame contains {len(lines)} lines; "
                        f"limit is {self.config.max_lines_per_frame}"
                    ),
                )
            )
            lines = lines[: self.config.max_lines_per_frame]

        parsed_fields: list[Wits0ParsedField] = []
        seen: set[tuple[int, int]] = set()
        record_numbers: list[int] = []
        unknown_records_reported: set[int] = set()

        for line_no, original_line in enumerate(lines, start=1):
            line = original_line.strip()
            if not line:
                continue
            if len(line) > self.config.max_line_chars:
                diagnostics.append(
                    Wits0Diagnostic(
                        code=Wits0DiagnosticCode.LINE_TOO_LONG,
                        severity=Wits0DiagnosticSeverity.ERROR,
                        message=(
                            f"WITS0 line {line_no} contains {len(line)} characters; "
                            f"limit is {self.config.max_line_chars}"
                        ),
                        line_no=line_no,
                        raw_line=line[: self.config.max_line_chars],
                    )
                )
                continue
            if len(line) < 4 or not line[:4].isdigit():
                diagnostics.append(
                    Wits0Diagnostic(
                        code=Wits0DiagnosticCode.INVALID_LINE,
                        severity=Wits0DiagnosticSeverity.ERROR,
                        message=f"WITS0 line {line_no} does not start with a four-digit identifier",
                        line_no=line_no,
                        raw_line=original_line,
                    )
                )
                continue

            record_no = int(line[:2])
            item_no = int(line[2:4])
            raw_value = line[4:].lstrip(" \t=:").strip()
            record_numbers.append(record_no)
            definition = self._definition(record_no, item_no)
            field_diagnostics: list[Wits0Diagnostic] = []

            record_definition = self.profile.record(record_no)
            record_is_known = (
                record_definition is not None or record_no in self._catalog_records
            )
            if not record_is_known and record_no not in unknown_records_reported:
                unknown_records_reported.add(record_no)
                diagnostic = Wits0Diagnostic(
                    code=Wits0DiagnosticCode.UNKNOWN_RECORD,
                    severity=Wits0DiagnosticSeverity.WARNING,
                    message=f"WITS0 record {record_no:02d} is absent from profile",
                    line_no=line_no,
                    record_no=record_no,
                    item_no=item_no,
                    raw_line=original_line,
                )
                field_diagnostics.append(diagnostic)
                diagnostics.append(diagnostic)
            elif definition is None:
                diagnostic = Wits0Diagnostic(
                    code=Wits0DiagnosticCode.UNKNOWN_FIELD,
                    severity=Wits0DiagnosticSeverity.WARNING,
                    message=(
                        f"WITS0 field {record_no:02d}{item_no:02d} is absent from profile"
                    ),
                    line_no=line_no,
                    record_no=record_no,
                    item_no=item_no,
                    raw_line=original_line,
                )
                field_diagnostics.append(diagnostic)
                diagnostics.append(diagnostic)

            field_key = (record_no, item_no)
            if field_key in seen:
                diagnostic = Wits0Diagnostic(
                    code=Wits0DiagnosticCode.DUPLICATE_FIELD,
                    severity=Wits0DiagnosticSeverity.WARNING,
                    message=f"Duplicate WITS0 field {record_no:02d}{item_no:02d}",
                    line_no=line_no,
                    record_no=record_no,
                    item_no=item_no,
                    raw_line=original_line,
                )
                field_diagnostics.append(diagnostic)
                diagnostics.append(diagnostic)
            seen.add(field_key)

            value_kind = definition.value_kind if definition is not None else "text"
            value, value_diagnostics = self._parse_value(
                raw_value,
                value_kind=value_kind,
                line_no=line_no,
                record_no=record_no,
                item_no=item_no,
                raw_line=original_line,
            )
            field_diagnostics.extend(value_diagnostics)
            diagnostics.extend(value_diagnostics)
            parsed_fields.append(
                Wits0ParsedField(
                    line_no=line_no,
                    record_no=record_no,
                    item_no=item_no,
                    raw_line=original_line,
                    raw_value=raw_value,
                    canonical_mnemonic=(
                        definition.canonical_mnemonic if definition is not None else None
                    ),
                    name_ru=definition.name_ru if definition is not None else None,
                    source_unit=definition.source_unit if definition is not None else None,
                    value_kind=value_kind,
                    aggregation=definition.aggregation if definition is not None else None,
                    value=value,
                    is_known=definition is not None,
                    diagnostics=tuple(field_diagnostics),
                )
            )

        unique_records = tuple(dict.fromkeys(record_numbers))
        record_no = unique_records[0] if len(unique_records) == 1 else None
        if len(unique_records) > 1:
            diagnostics.append(
                Wits0Diagnostic(
                    code=Wits0DiagnosticCode.MIXED_RECORDS,
                    severity=Wits0DiagnosticSeverity.WARNING,
                    message=(
                        "One WITS0 frame contains multiple record numbers: "
                        + ", ".join(f"{item:02d}" for item in unique_records)
                    ),
                )
            )

        sequence_fields = [
            item for item in parsed_fields if item.item_no == self.config.sequence_item_no
        ]
        sequence_no: int | None = None
        sequence_status = Wits0SequenceStatus.UNAVAILABLE
        if sequence_fields:
            candidate = sequence_fields[0]
            if isinstance(candidate.value, int) and not isinstance(candidate.value, bool):
                sequence_no = candidate.value
            else:
                sequence_status = Wits0SequenceStatus.INVALID
                diagnostics.append(
                    Wits0Diagnostic(
                        code=Wits0DiagnosticCode.INVALID_SEQUENCE,
                        severity=Wits0DiagnosticSeverity.ERROR,
                        message=(
                            f"WITS0 sequence field {candidate.record_no:02d}"
                            f"{candidate.item_no:02d} is not a valid integer"
                        ),
                        line_no=candidate.line_no,
                        record_no=candidate.record_no,
                        item_no=candidate.item_no,
                        raw_line=candidate.raw_line,
                    )
                )

        return Wits0ParsedFrame(
            raw_frame=frame,
            raw_text=raw_text,
            received_at=received_at,
            source_ref=source_ref,
            record_no=record_no,
            sequence_no=sequence_no,
            sequence_status=sequence_status,
            fields=tuple(parsed_fields),
            diagnostics=tuple(diagnostics),
        )

    def _definition(self, record_no: int, item_no: int) -> Wits0FieldDefinition | None:
        if item_no in _STANDARD_HEADER_FIELDS:
            return _STANDARD_HEADER_FIELDS[item_no]
        record = self.profile.record(record_no)
        if record is not None:
            profile_field = record.field(item_no)
            if profile_field is not None:
                return profile_field
        return self._catalog_definitions.get((record_no, item_no))

    def _parse_value(
        self,
        raw_value: str,
        *,
        value_kind: str,
        line_no: int,
        record_no: int,
        item_no: int,
        raw_line: str,
    ) -> tuple[Wits0TypedValue, tuple[Wits0Diagnostic, ...]]:
        if not raw_value:
            diagnostic = Wits0Diagnostic(
                code=Wits0DiagnosticCode.EMPTY_VALUE,
                severity=Wits0DiagnosticSeverity.WARNING,
                message=f"WITS0 field {record_no:02d}{item_no:02d} has an empty value",
                line_no=line_no,
                record_no=record_no,
                item_no=item_no,
                raw_line=raw_line,
            )
            return None, (diagnostic,)
        if value_kind == "text":
            return raw_value, ()
        try:
            if value_kind == "integer":
                return int(raw_value, 10), ()
            if value_kind == "float":
                normalized = raw_value
                if self.config.accept_decimal_comma and "," in normalized and "." not in normalized:
                    normalized = normalized.replace(",", ".")
                value = float(normalized)
                if not math.isfinite(value):
                    diagnostic = Wits0Diagnostic(
                        code=Wits0DiagnosticCode.NON_FINITE_NUMBER,
                        severity=Wits0DiagnosticSeverity.ERROR,
                        message=(
                            f"WITS0 field {record_no:02d}{item_no:02d} "
                            "contains a non-finite number"
                        ),
                        line_no=line_no,
                        record_no=record_no,
                        item_no=item_no,
                        raw_line=raw_line,
                    )
                    return None, (diagnostic,)
                return value, ()
            if value_kind == "date":
                return _parse_wits_date(raw_value), ()
            if value_kind == "time":
                return _parse_wits_time(raw_value), ()
        except (ValueError, OverflowError) as exc:
            diagnostic = Wits0Diagnostic(
                code=Wits0DiagnosticCode.VALUE_PARSE_ERROR,
                severity=Wits0DiagnosticSeverity.ERROR,
                message=(
                    f"Cannot parse WITS0 field {record_no:02d}{item_no:02d} "
                    f"as {value_kind}: {exc}"
                ),
                line_no=line_no,
                record_no=record_no,
                item_no=item_no,
                raw_line=raw_line,
            )
            return None, (diagnostic,)
        raise ValueError(f"Unsupported WITS0 value kind: {value_kind}")


class Wits0SequenceTracker:
    """Track monotonic sequence numbers independently for every WITS record."""

    def __init__(self, *, sequence_item_no: int = 4) -> None:
        if isinstance(sequence_item_no, bool) or not 0 <= sequence_item_no <= 99:
            raise ValueError("sequence_item_no must be in the range 0..99")
        self.sequence_item_no = sequence_item_no
        self._last_by_record: dict[int, int] = {}

    @property
    def last_by_record(self) -> dict[int, int]:
        return dict(self._last_by_record)

    def reset(self) -> None:
        self._last_by_record.clear()

    def inspect(self, frame: Wits0ParsedFrame) -> Wits0ParsedFrame:
        if frame.record_no is None:
            return frame
        sequence_fields = [
            item for item in frame.fields if item.item_no == self.sequence_item_no
        ]
        if not sequence_fields:
            diagnostic = Wits0Diagnostic(
                code=Wits0DiagnosticCode.MISSING_SEQUENCE,
                severity=Wits0DiagnosticSeverity.WARNING,
                message=(
                    f"WITS0 record {frame.record_no:02d} has no sequence field "
                    f"{self.sequence_item_no:02d}"
                ),
                record_no=frame.record_no,
            )
            return replace(
                frame,
                sequence_status=Wits0SequenceStatus.UNAVAILABLE,
                diagnostics=frame.diagnostics + (diagnostic,),
            )
        if frame.sequence_no is None:
            return replace(frame, sequence_status=Wits0SequenceStatus.INVALID)

        actual = frame.sequence_no
        previous = self._last_by_record.get(frame.record_no)
        if previous is None:
            self._last_by_record[frame.record_no] = actual
            return replace(frame, sequence_status=Wits0SequenceStatus.FIRST)

        expected = previous + 1
        if actual == expected:
            self._last_by_record[frame.record_no] = actual
            return replace(frame, sequence_status=Wits0SequenceStatus.CONTIGUOUS)
        if actual == previous:
            diagnostic = Wits0Diagnostic(
                code=Wits0DiagnosticCode.SEQUENCE_DUPLICATE,
                severity=Wits0DiagnosticSeverity.WARNING,
                message=(
                    f"Duplicate WITS0 sequence {actual} for record {frame.record_no:02d}"
                ),
                record_no=frame.record_no,
                expected_sequence=expected,
                actual_sequence=actual,
            )
            return replace(
                frame,
                sequence_status=Wits0SequenceStatus.DUPLICATE,
                diagnostics=frame.diagnostics + (diagnostic,),
            )
        if actual > expected:
            self._last_by_record[frame.record_no] = actual
            diagnostic = Wits0Diagnostic(
                code=Wits0DiagnosticCode.SEQUENCE_GAP,
                severity=Wits0DiagnosticSeverity.WARNING,
                message=(
                    f"WITS0 sequence gap for record {frame.record_no:02d}: "
                    f"expected {expected}, received {actual}"
                ),
                record_no=frame.record_no,
                expected_sequence=expected,
                actual_sequence=actual,
            )
            return replace(
                frame,
                sequence_status=Wits0SequenceStatus.GAP,
                diagnostics=frame.diagnostics + (diagnostic,),
            )

        diagnostic = Wits0Diagnostic(
            code=Wits0DiagnosticCode.SEQUENCE_OUT_OF_ORDER,
            severity=Wits0DiagnosticSeverity.WARNING,
            message=(
                f"Out-of-order WITS0 sequence for record {frame.record_no:02d}: "
                f"last {previous}, received {actual}"
            ),
            record_no=frame.record_no,
            expected_sequence=expected,
            actual_sequence=actual,
        )
        return replace(
            frame,
            sequence_status=Wits0SequenceStatus.OUT_OF_ORDER,
            diagnostics=frame.diagnostics + (diagnostic,),
        )


class Wits0StreamProcessor:
    """Shared live/replay byte-stream pipeline: framing, parsing, and sequence QC."""

    def __init__(
        self,
        profile: Wits0Profile,
        *,
        parser_config: Wits0ParserConfig | None = None,
        max_frame_bytes: int = 1_048_576,
    ) -> None:
        self.profile = profile
        self.decoder = Wits0FrameDecoder(
            start_marker=profile.start_marker.encode("ascii"),
            end_marker=profile.end_marker.encode("ascii"),
            max_frame_bytes=max_frame_bytes,
        )
        self.parser = Wits0Parser(profile, config=parser_config)
        self.sequence_tracker = Wits0SequenceTracker(
            sequence_item_no=self.parser.config.sequence_item_no
        )

    @property
    def discarded_bytes(self) -> int:
        return self.decoder.discarded_bytes

    @property
    def buffered_bytes(self) -> int:
        return self.decoder.buffered_bytes

    @property
    def last_sequence_by_record(self) -> dict[int, int]:
        return self.sequence_tracker.last_by_record

    def append(
        self,
        chunk: bytes | bytearray | memoryview,
        *,
        received_at: str | None = None,
        source_ref: str | None = None,
    ) -> tuple[Wits0ParsedFrame, ...]:
        parsed: list[Wits0ParsedFrame] = []
        for raw_frame in self.decoder.append(chunk):
            frame = self.parser.parse(
                raw_frame,
                received_at=received_at,
                source_ref=source_ref,
            )
            parsed.append(self.sequence_tracker.inspect(frame))
        return tuple(parsed)

    def reset(self, *, reset_sequences: bool = True) -> bytes:
        pending = self.decoder.reset()
        if reset_sequences:
            self.sequence_tracker.reset()
        return pending


def iter_parsed_wits0_frames(
    source: str | Path | BinaryIO,
    *,
    profile: Wits0Profile,
    chunk_size: int = 65_536,
    max_frame_bytes: int = 1_048_576,
    received_at: str | None = None,
    source_ref: str | None = None,
) -> Iterator[Wits0ParsedFrame]:
    """Replay bytes through exactly the same processor used by live TCP capture."""

    if isinstance(chunk_size, bool) or chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    processor = Wits0StreamProcessor(profile, max_frame_bytes=max_frame_bytes)
    owns_stream = not hasattr(source, "read")
    stream: BinaryIO
    if owns_stream:
        stream = Path(source).open("rb")
    else:
        stream = source  # type: ignore[assignment]
    effective_ref = source_ref
    if effective_ref is None and owns_stream:
        effective_ref = str(Path(source))
    try:
        while chunk := stream.read(chunk_size):
            yield from processor.append(
                chunk,
                received_at=received_at,
                source_ref=effective_ref,
            )
    finally:
        if owns_stream:
            stream.close()


def process_wits0_chunks(
    chunks: Iterable[bytes],
    *,
    profile: Wits0Profile,
    received_at: str | None = None,
    source_ref: str | None = None,
    max_frame_bytes: int = 1_048_576,
) -> tuple[Wits0ParsedFrame, ...]:
    """Convenience helper used by deterministic live/replay and simulator tests."""

    processor = Wits0StreamProcessor(profile, max_frame_bytes=max_frame_bytes)
    frames: list[Wits0ParsedFrame] = []
    for chunk in chunks:
        frames.extend(
            processor.append(
                chunk,
                received_at=received_at,
                source_ref=source_ref,
            )
        )
    return tuple(frames)


def _parse_wits_date(value: str) -> date:
    candidate = value.strip()
    if candidate.isdigit():
        if len(candidate) == 8:
            return datetime.strptime(candidate, "%Y%m%d").date()
        if len(candidate) == 6:
            return datetime.strptime(candidate, "%y%m%d").date()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(candidate, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unsupported WITS date format: {value!r}")


def _parse_wits_time(value: str) -> time:
    candidate = value.strip()
    for fmt in ("%H:%M:%S.%f", "%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(candidate, fmt).time()
        except ValueError:
            continue

    compact = candidate.replace(",", ".")
    if "." in compact:
        whole, fraction = compact.split(".", 1)
    else:
        whole, fraction = compact, ""
    if not whole.isdigit() or (fraction and not fraction.isdigit()):
        raise ValueError(f"unsupported WITS time format: {value!r}")
    if len(whole) == 4:
        whole += "00"
    elif len(whole) > 6 and not fraction:
        fraction = whole[6:]
        whole = whole[:6]
    if len(whole) != 6:
        raise ValueError(f"unsupported WITS time format: {value!r}")
    hour = int(whole[:2])
    minute = int(whole[2:4])
    second = int(whole[4:6])
    microsecond = int((fraction[:6]).ljust(6, "0")) if fraction else 0
    return time(hour=hour, minute=minute, second=second, microsecond=microsecond)
