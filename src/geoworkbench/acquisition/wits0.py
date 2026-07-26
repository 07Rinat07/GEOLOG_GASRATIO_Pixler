from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any, BinaryIO, Iterator


WITS0_PROFILE_SCHEMA_VERSION = 1


class Wits0FrameError(ValueError):
    """Base error for malformed or unsafe WITS0 framing."""


class Wits0FrameTooLargeError(Wits0FrameError):
    """Raised when an unterminated frame exceeds the configured resource limit."""


class Wits0ProfileError(ValueError):
    """Raised when a WITS0 profile does not satisfy the strict schema."""


class Wits0FrameDecoder:
    """Incrementally split a byte stream into ``&& ... !!`` WITS0 frames.

    TCP is a stream protocol and never preserves application-message boundaries.  The decoder
    therefore accepts arbitrary chunks, including a single marker split across multiple calls.
    Bytes before the next start marker are counted as discarded diagnostics and never returned
    as a valid frame.
    """

    def __init__(
        self,
        *,
        start_marker: bytes = b"&&",
        end_marker: bytes = b"!!",
        max_frame_bytes: int = 1_048_576,
    ) -> None:
        if not start_marker or not end_marker:
            raise ValueError("WITS0 markers must not be empty")
        if start_marker == end_marker:
            raise ValueError("WITS0 start and end markers must differ")
        if isinstance(max_frame_bytes, bool) or max_frame_bytes < 16:
            raise ValueError("max_frame_bytes must be at least 16")
        self.start_marker = bytes(start_marker)
        self.end_marker = bytes(end_marker)
        self.max_frame_bytes = int(max_frame_bytes)
        self._buffer = bytearray()
        self.discarded_bytes = 0

    @property
    def buffered_bytes(self) -> int:
        return len(self._buffer)

    def reset(self) -> bytes:
        """Clear and return the incomplete bytes kept by the decoder."""

        pending = bytes(self._buffer)
        self._buffer.clear()
        return pending

    def append(self, chunk: bytes | bytearray | memoryview) -> tuple[bytes, ...]:
        data = bytes(chunk)
        if not data:
            return ()
        self._buffer.extend(data)
        frames: list[bytes] = []

        while True:
            start = self._buffer.find(self.start_marker)
            if start < 0:
                self._discard_without_start_marker()
                return tuple(frames)
            if start:
                self.discarded_bytes += start
                del self._buffer[:start]

            end = self._buffer.find(self.end_marker, len(self.start_marker))
            if end < 0:
                if len(self._buffer) > self.max_frame_bytes:
                    size = len(self._buffer)
                    self._buffer.clear()
                    raise Wits0FrameTooLargeError(
                        f"WITS0 frame exceeded {self.max_frame_bytes} bytes ({size})"
                    )
                return tuple(frames)

            frame_end = end + len(self.end_marker)
            if frame_end > self.max_frame_bytes:
                del self._buffer[:frame_end]
                raise Wits0FrameTooLargeError(
                    f"WITS0 frame exceeded {self.max_frame_bytes} bytes ({frame_end})"
                )
            frames.append(bytes(self._buffer[:frame_end]))
            del self._buffer[:frame_end]

    def _discard_without_start_marker(self) -> None:
        # Keep only the longest possible marker prefix at the tail.  For the standard marker
        # this preserves a trailing single '&' so a marker split as '&' + '&' is recovered.
        keep = min(len(self._buffer), len(self.start_marker) - 1)
        if keep:
            suffix = bytes(self._buffer[-keep:])
            prefix_length = 0
            for length in range(keep, 0, -1):
                if suffix[-length:] == self.start_marker[:length]:
                    prefix_length = length
                    break
            discarded = len(self._buffer) - prefix_length
            if discarded:
                self.discarded_bytes += discarded
                del self._buffer[:discarded]
            return
        self.discarded_bytes += len(self._buffer)
        self._buffer.clear()


@dataclass(frozen=True, slots=True)
class Wits0FieldDefinition:
    item_no: int
    canonical_mnemonic: str
    name_ru: str
    source_unit: str | None
    value_kind: str
    aggregation: str

    def __post_init__(self) -> None:
        if isinstance(self.item_no, bool) or not 0 <= self.item_no <= 99:
            raise Wits0ProfileError("item_no must be an integer in the range 0..99")
        _required_text(self.canonical_mnemonic, "canonical_mnemonic")
        _required_text(self.name_ru, "name_ru")
        _optional_text(self.source_unit, "source_unit")
        if self.value_kind not in {"float", "integer", "text", "date", "time"}:
            raise Wits0ProfileError(f"Unsupported WITS0 value_kind: {self.value_kind}")
        if self.aggregation not in {"exact", "average", "minimum", "maximum"}:
            raise Wits0ProfileError(f"Unsupported WITS0 aggregation: {self.aggregation}")


@dataclass(frozen=True, slots=True)
class Wits0RecordDefinition:
    record_no: int
    name_ru: str
    index_type: str
    send_policy: str
    fields: tuple[Wits0FieldDefinition, ...]

    def __post_init__(self) -> None:
        if isinstance(self.record_no, bool) or not 0 <= self.record_no <= 99:
            raise Wits0ProfileError("record_no must be an integer in the range 0..99")
        _required_text(self.name_ru, "name_ru")
        if self.index_type not in {"time", "depth", "depth_lagged", "event"}:
            raise Wits0ProfileError(f"Unsupported WITS0 index_type: {self.index_type}")
        _required_text(self.send_policy, "send_policy")
        if not self.fields:
            raise Wits0ProfileError("A WITS0 record must define at least one field")
        item_numbers = [item.item_no for item in self.fields]
        if len(item_numbers) != len(set(item_numbers)):
            raise Wits0ProfileError(f"Duplicate fields in WITS0 record {self.record_no:02d}")

    def field(self, item_no: int) -> Wits0FieldDefinition | None:
        return next((item for item in self.fields if item.item_no == item_no), None)


@dataclass(frozen=True, slots=True)
class Wits0Profile:
    profile_id: str
    title: str
    version: int
    encoding: str
    start_marker: str
    end_marker: str
    reference: str | None
    records: tuple[Wits0RecordDefinition, ...]
    schema_version: int = WITS0_PROFILE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != WITS0_PROFILE_SCHEMA_VERSION:
            raise Wits0ProfileError(
                f"Unsupported WITS0 profile schema version: {self.schema_version}"
            )
        _required_text(self.profile_id, "profile_id")
        _required_text(self.title, "title")
        if isinstance(self.version, bool) or self.version < 1:
            raise Wits0ProfileError("profile version must be a positive integer")
        if self.encoding.casefold() not in {"ascii", "latin-1", "cp1251", "utf-8"}:
            raise Wits0ProfileError(f"Unsupported WITS0 encoding: {self.encoding}")
        _required_text(self.start_marker, "start_marker")
        _required_text(self.end_marker, "end_marker")
        if self.start_marker == self.end_marker:
            raise Wits0ProfileError("WITS0 profile markers must differ")
        _optional_text(self.reference, "reference")
        if not self.records:
            raise Wits0ProfileError("WITS0 profile must contain records")
        record_numbers = [item.record_no for item in self.records]
        if len(record_numbers) != len(set(record_numbers)):
            raise Wits0ProfileError("Duplicate WITS0 record numbers")

    def record(self, record_no: int) -> Wits0RecordDefinition | None:
        return next((item for item in self.records if item.record_no == record_no), None)


def load_builtin_wits0_profile(profile_id: str = "geoscape-gswits") -> Wits0Profile:
    resource = files("geoworkbench.resources").joinpath(
        "wits", "profiles", f"{profile_id}.json"
    )
    try:
        payload = resource.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise Wits0ProfileError(f"Unknown built-in WITS0 profile: {profile_id}") from exc
    return _profile_from_payload(json.loads(payload))


def load_wits0_profile(path: str | Path) -> Wits0Profile:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Wits0ProfileError(f"Cannot read WITS0 profile {source}: {exc}") from exc
    return _profile_from_payload(payload)


def iter_wits0_frames(
    source: str | Path | BinaryIO,
    *,
    chunk_size: int = 65_536,
    start_marker: bytes = b"&&",
    end_marker: bytes = b"!!",
    max_frame_bytes: int = 1_048_576,
) -> Iterator[bytes]:
    """Replay a raw file through the same incremental framing contract as live TCP."""

    if isinstance(chunk_size, bool) or chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    decoder = Wits0FrameDecoder(
        start_marker=start_marker,
        end_marker=end_marker,
        max_frame_bytes=max_frame_bytes,
    )
    owns_stream = not hasattr(source, "read")
    stream: BinaryIO
    if owns_stream:
        stream = Path(source).open("rb")
    else:
        stream = source  # type: ignore[assignment]
    try:
        while chunk := stream.read(chunk_size):
            yield from decoder.append(chunk)
    finally:
        if owns_stream:
            stream.close()


def _profile_from_payload(payload: Any) -> Wits0Profile:
    if not isinstance(payload, dict):
        raise Wits0ProfileError("WITS0 profile root must be an object")
    allowed = {
        "schemaVersion",
        "profileId",
        "title",
        "version",
        "encoding",
        "frame",
        "reference",
        "records",
    }
    _reject_unknown(payload, allowed, "WITS0 profile")
    frame = _required_object(payload, "frame")
    _reject_unknown(frame, {"start", "end"}, "WITS0 frame")
    records_payload = payload.get("records")
    if not isinstance(records_payload, list):
        raise Wits0ProfileError("WITS0 records must be an array")
    records: list[Wits0RecordDefinition] = []
    for record_payload in records_payload:
        if not isinstance(record_payload, dict):
            raise Wits0ProfileError("Each WITS0 record must be an object")
        _reject_unknown(
            record_payload,
            {"record", "nameRu", "indexType", "sendPolicy", "fields"},
            "WITS0 record",
        )
        fields_payload = record_payload.get("fields")
        if not isinstance(fields_payload, list):
            raise Wits0ProfileError("WITS0 record fields must be an array")
        fields_defs: list[Wits0FieldDefinition] = []
        for field_payload in fields_payload:
            if not isinstance(field_payload, dict):
                raise Wits0ProfileError("Each WITS0 field must be an object")
            _reject_unknown(
                field_payload,
                {
                    "item",
                    "canonicalMnemonic",
                    "nameRu",
                    "sourceUnit",
                    "valueKind",
                    "aggregation",
                },
                "WITS0 field",
            )
            fields_defs.append(
                Wits0FieldDefinition(
                    item_no=_required_int(field_payload, "item"),
                    canonical_mnemonic=_required_str(
                        field_payload, "canonicalMnemonic"
                    ),
                    name_ru=_required_str(field_payload, "nameRu"),
                    source_unit=_optional_str(field_payload, "sourceUnit"),
                    value_kind=_required_str(field_payload, "valueKind"),
                    aggregation=_required_str(field_payload, "aggregation"),
                )
            )
        records.append(
            Wits0RecordDefinition(
                record_no=_required_int(record_payload, "record"),
                name_ru=_required_str(record_payload, "nameRu"),
                index_type=_required_str(record_payload, "indexType"),
                send_policy=_required_str(record_payload, "sendPolicy"),
                fields=tuple(fields_defs),
            )
        )
    return Wits0Profile(
        profile_id=_required_str(payload, "profileId"),
        title=_required_str(payload, "title"),
        version=_required_int(payload, "version"),
        encoding=_required_str(payload, "encoding"),
        start_marker=_required_str(frame, "start"),
        end_marker=_required_str(frame, "end"),
        reference=_optional_str(payload, "reference"),
        records=tuple(records),
        schema_version=_required_int(payload, "schemaVersion"),
    )


def _reject_unknown(payload: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(payload) - allowed
    if unknown:
        raise Wits0ProfileError(f"{label} contains unknown fields: {sorted(unknown)}")


def _required_object(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise Wits0ProfileError(f"{key} must be an object")
    return value


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise Wits0ProfileError(f"{key} must be a non-empty string")
    return value.strip()


def _optional_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise Wits0ProfileError(f"{key} must be null or a non-empty string")
    return value.strip()


def _required_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise Wits0ProfileError(f"{key} must be an integer")
    return value


def _required_text(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise Wits0ProfileError(f"{label} must be a non-empty string")


def _optional_text(value: str | None, label: str) -> None:
    if value is not None:
        _required_text(value, label)
