from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timezone
from enum import StrEnum
from hashlib import sha256
from math import isfinite
from pathlib import Path
from typing import Any, Iterable
from uuid import NAMESPACE_URL, uuid4, uuid5

from geoworkbench.acquisition.wits0 import Wits0Profile
from geoworkbench.acquisition.wits0_parser import (
    Wits0DiagnosticSeverity,
    Wits0ParsedField,
    Wits0ParsedFrame,
)
from geoworkbench.domain.acquisition import (
    AcquisitionCurveSchema,
    AcquisitionDatasetSchema,
    AcquisitionIndexSchema,
)
from geoworkbench.domain.models import (
    CurveMetadata,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
)
from geoworkbench.services.semantic_channels import (
    SemanticChannelBinding,
    SemanticChannelDictionary,
    default_semantic_channel_dictionary,
)
from geoworkbench.services.uom_dictionary import QuantityClass


WITS0_CUSTOM_PROFILE_SCHEMA_VERSION = 1
_HEADER_ITEM_MAX = 7
_TOKEN = re.compile(r"[^a-zA-Z0-9_.-]+")


class Wits0ReviewSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True, order=True)
class Wits0ChannelKey:
    record_no: int
    item_no: int

    def __post_init__(self) -> None:
        for value, name in ((self.record_no, "record_no"), (self.item_no, "item_no")):
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 99:
                raise ValueError(f"{name} must be an integer in the range 0..99")

    @property
    def source_id(self) -> str:
        return f"{self.record_no:02d}{self.item_no:02d}"

    @classmethod
    def parse(cls, value: str) -> Wits0ChannelKey:
        text = value.strip()
        if len(text) != 4 or not text.isdigit():
            raise ValueError(f"Invalid WITS0 channel key: {value!r}")
        return cls(int(text[:2]), int(text[2:]))


@dataclass(frozen=True, slots=True)
class Wits0ReviewIssue:
    code: str
    severity: Wits0ReviewSeverity
    message: str
    channel_key: Wits0ChannelKey | None = None

    def __post_init__(self) -> None:
        _required_text(self.code, "code")
        _required_text(self.message, "message")
        if not isinstance(self.severity, Wits0ReviewSeverity):
            raise ValueError("severity must use Wits0ReviewSeverity")
        if self.channel_key is not None and not isinstance(
            self.channel_key, Wits0ChannelKey
        ):
            raise ValueError("channel_key must use Wits0ChannelKey")


@dataclass(frozen=True, slots=True)
class Wits0DiscoveredChannel:
    key: Wits0ChannelKey
    source_mnemonic: str
    name: str
    source_uom: str | None
    value_kind: str
    aggregation: str | None
    record_index_type: str | None
    known: bool
    observed_count: int
    valid_count: int
    null_count: int
    error_count: int
    numeric_min: float | None
    numeric_max: float | None
    samples: tuple[str, ...]

    def __post_init__(self) -> None:
        _required_text(self.source_mnemonic, "source_mnemonic")
        _required_text(self.name, "name")
        _optional_text(self.source_uom, "source_uom")
        if self.value_kind not in {"float", "integer", "text", "date", "time"}:
            raise ValueError(f"Unsupported WITS0 value kind: {self.value_kind}")
        for value, label in (
            (self.observed_count, "observed_count"),
            (self.valid_count, "valid_count"),
            (self.null_count, "null_count"),
            (self.error_count, "error_count"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{label} must be a non-negative integer")
        if self.valid_count + self.null_count > self.observed_count:
            raise ValueError("valid/null counts exceed observed_count")
        if self.numeric_min is not None and not isfinite(self.numeric_min):
            raise ValueError("numeric_min must be finite")
        if self.numeric_max is not None and not isfinite(self.numeric_max):
            raise ValueError("numeric_max must be finite")
        if (
            self.numeric_min is not None
            and self.numeric_max is not None
            and self.numeric_min > self.numeric_max
        ):
            raise ValueError("numeric_min must not exceed numeric_max")

    @property
    def numeric(self) -> bool:
        return self.value_kind in {"float", "integer"}


@dataclass(frozen=True, slots=True)
class Wits0DiscoverySnapshot:
    profile_id: str
    profile_version: int
    frame_count: int
    record_counts: tuple[tuple[int, int], ...]
    datetime_observation_count: int
    channels: tuple[Wits0DiscoveredChannel, ...]
    parser_warning_count: int
    parser_error_count: int
    fingerprint: str

    def __post_init__(self) -> None:
        _required_text(self.profile_id, "profile_id")
        if isinstance(self.profile_version, bool) or self.profile_version < 1:
            raise ValueError("profile_version must be positive")
        for value, label in (
            (self.frame_count, "frame_count"),
            (self.datetime_observation_count, "datetime_observation_count"),
            (self.parser_warning_count, "parser_warning_count"),
            (self.parser_error_count, "parser_error_count"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{label} must be a non-negative integer")
        if len({item.key for item in self.channels}) != len(self.channels):
            raise ValueError("Discovery snapshot contains duplicate channels")
        if not re.fullmatch(r"[0-9a-f]{64}", self.fingerprint):
            raise ValueError("fingerprint must be a SHA-256 hex digest")

    def channel(self, key: Wits0ChannelKey | str) -> Wits0DiscoveredChannel | None:
        wanted = Wits0ChannelKey.parse(key) if isinstance(key, str) else key
        return next((item for item in self.channels if item.key == wanted), None)


@dataclass(slots=True)
class _MutableChannelStats:
    key: Wits0ChannelKey
    source_mnemonic: str
    name: str
    source_uom: str | None
    value_kind: str
    aggregation: str | None
    record_index_type: str | None
    known: bool
    observed_count: int = 0
    valid_count: int = 0
    null_count: int = 0
    error_count: int = 0
    numeric_min: float | None = None
    numeric_max: float | None = None
    samples: list[str] | None = None

    def observe(self, field: Wits0ParsedField, *, max_samples: int) -> None:
        self.observed_count += 1
        self.error_count += sum(
            item.severity is Wits0DiagnosticSeverity.ERROR for item in field.diagnostics
        )
        if field.value is None:
            self.null_count += 1
            return
        observed_value: object = field.value
        if not self.known and self.value_kind == "text" and isinstance(field.value, str):
            inferred = _infer_unknown_numeric(field.raw_value)
            if inferred is not None:
                self.value_kind = "float"
                observed_value = inferred
        elif not self.known and self.value_kind == "float" and isinstance(field.value, str):
            inferred = _infer_unknown_numeric(field.raw_value)
            if inferred is None:
                # A vendor field that mixes text and numbers cannot safely enter the numeric
                # AcquisitionDatasetSchema without an explicit parser-profile definition.
                self.value_kind = "text"
            else:
                observed_value = inferred
        self.valid_count += 1
        rendered = _render_sample(observed_value)
        if self.samples is None:
            self.samples = []
        if rendered not in self.samples and len(self.samples) < max_samples:
            self.samples.append(rendered)
        if isinstance(observed_value, (int, float)) and not isinstance(observed_value, bool):
            numeric = float(observed_value)
            if isfinite(numeric):
                self.numeric_min = (
                    numeric if self.numeric_min is None else min(self.numeric_min, numeric)
                )
                self.numeric_max = (
                    numeric if self.numeric_max is None else max(self.numeric_max, numeric)
                )

    def freeze(self) -> Wits0DiscoveredChannel:
        return Wits0DiscoveredChannel(
            key=self.key,
            source_mnemonic=self.source_mnemonic,
            name=self.name,
            source_uom=self.source_uom,
            value_kind=self.value_kind,
            aggregation=self.aggregation,
            record_index_type=self.record_index_type,
            known=self.known,
            observed_count=self.observed_count,
            valid_count=self.valid_count,
            null_count=self.null_count,
            error_count=self.error_count,
            numeric_min=self.numeric_min,
            numeric_max=self.numeric_max,
            samples=tuple(self.samples or ()),
        )


class Wits0DiscoveryAccumulator:
    """Mutable collector whose public result is an immutable deterministic snapshot."""

    def __init__(self, profile: Wits0Profile, *, max_samples_per_channel: int = 5) -> None:
        if isinstance(max_samples_per_channel, bool) or max_samples_per_channel < 1:
            raise ValueError("max_samples_per_channel must be positive")
        self.profile = profile
        self.max_samples_per_channel = int(max_samples_per_channel)
        self._channels: dict[Wits0ChannelKey, _MutableChannelStats] = {}
        self._record_counts: dict[int, int] = {}
        self._frame_count = 0
        self._datetime_observation_count = 0
        self._parser_warning_count = 0
        self._parser_error_count = 0

    def reset(self) -> None:
        self._channels.clear()
        self._record_counts.clear()
        self._frame_count = 0
        self._datetime_observation_count = 0
        self._parser_warning_count = 0
        self._parser_error_count = 0

    def observe(self, frame: Wits0ParsedFrame) -> None:
        self._frame_count += 1
        self._parser_warning_count += frame.warning_count
        self._parser_error_count += frame.error_count
        if frame.record_no is not None:
            self._record_counts[frame.record_no] = self._record_counts.get(frame.record_no, 0) + 1
        if _frame_datetime(frame) is not None:
            self._datetime_observation_count += 1
        for field in frame.fields:
            if field.item_no <= _HEADER_ITEM_MAX:
                continue
            key = Wits0ChannelKey(field.record_no, field.item_no)
            stats = self._channels.get(key)
            if stats is None:
                record = self.profile.record(field.record_no)
                mnemonic = field.canonical_mnemonic or f"WITS_{key.source_id}"
                name = field.name_ru or f"Неизвестное поле WITS0 {key.source_id}"
                stats = _MutableChannelStats(
                    key=key,
                    source_mnemonic=mnemonic,
                    name=name,
                    source_uom=field.source_unit,
                    value_kind=field.value_kind,
                    aggregation=field.aggregation,
                    record_index_type=record.index_type if record is not None else None,
                    known=field.is_known,
                )
                self._channels[key] = stats
            stats.observe(field, max_samples=self.max_samples_per_channel)

    def observe_many(self, frames: Iterable[Wits0ParsedFrame]) -> None:
        for frame in frames:
            self.observe(frame)

    def snapshot(self) -> Wits0DiscoverySnapshot:
        channels = tuple(self._channels[key].freeze() for key in sorted(self._channels))
        record_counts = tuple(sorted(self._record_counts.items()))
        # The fingerprint is a schema-discovery identity, not a sample-statistics digest.
        # Additional values for already discovered fields must not invalidate a confirmed
        # Import Review while a live stream is still running.  A new record/item, a changed
        # inferred value kind/UOM, or newly available header datetime does invalidate it.
        fingerprint_payload = {
            "profileId": self.profile.profile_id,
            "profileVersion": self.profile.version,
            "hasHeaderDatetime": self._datetime_observation_count > 0,
            "channels": [
                {
                    "sourceId": item.key.source_id,
                    "sourceMnemonic": item.source_mnemonic,
                    "sourceUom": item.source_uom,
                    "valueKind": item.value_kind,
                    "aggregation": item.aggregation,
                    "recordIndexType": item.record_index_type,
                    "known": item.known,
                }
                for item in channels
            ],
        }
        fingerprint = sha256(
            json.dumps(
                fingerprint_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return Wits0DiscoverySnapshot(
            profile_id=self.profile.profile_id,
            profile_version=self.profile.version,
            frame_count=self._frame_count,
            record_counts=record_counts,
            datetime_observation_count=self._datetime_observation_count,
            channels=channels,
            parser_warning_count=self._parser_warning_count,
            parser_error_count=self._parser_error_count,
            fingerprint=fingerprint,
        )


def discover_wits0_frames(
    profile: Wits0Profile,
    frames: Iterable[Wits0ParsedFrame],
    *,
    max_samples_per_channel: int = 5,
) -> Wits0DiscoverySnapshot:
    accumulator = Wits0DiscoveryAccumulator(
        profile,
        max_samples_per_channel=max_samples_per_channel,
    )
    accumulator.observe_many(frames)
    return accumulator.snapshot()


@dataclass(frozen=True, slots=True)
class Wits0IndexCandidate:
    candidate_id: str
    source_kind: str
    mnemonic: str
    role: IndexRole
    index_type: IndexType
    source_uom: str | None
    canonical_uom: str | None
    confidence: float
    observation_count: int
    evidence: tuple[str, ...]
    channel_key: Wits0ChannelKey | None = None

    def __post_init__(self) -> None:
        _required_text(self.candidate_id, "candidate_id")
        if self.source_kind not in {"header_datetime", "field"}:
            raise ValueError(f"Unsupported index source kind: {self.source_kind}")
        _required_text(self.mnemonic, "mnemonic")
        if not isinstance(self.role, IndexRole) or not isinstance(self.index_type, IndexType):
            raise ValueError("Index candidate role/type must use domain enums")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Index candidate confidence must be in the range 0..1")
        if self.observation_count < 0:
            raise ValueError("observation_count must be non-negative")


@dataclass(frozen=True, slots=True)
class Wits0ChannelOverride:
    key: Wits0ChannelKey
    curve_id: str
    import_enabled: bool
    canonical_mnemonic: str
    canonical_kind: str
    quantity_class: QuantityClass | str
    source_uom: str | None
    canonical_uom: str | None

    def __post_init__(self) -> None:
        _required_text(self.curve_id, "curve_id")
        _required_text(self.canonical_mnemonic, "canonical_mnemonic")
        _required_text(self.canonical_kind, "canonical_kind")
        quantity = self.quantity_class
        if not isinstance(quantity, QuantityClass):
            try:
                quantity = QuantityClass(str(quantity))
            except ValueError as exc:
                raise ValueError(f"Unsupported quantity class: {self.quantity_class!r}") from exc
            object.__setattr__(self, "quantity_class", quantity)
        object.__setattr__(self, "canonical_mnemonic", self.canonical_mnemonic.strip().upper())
        object.__setattr__(self, "canonical_kind", self.canonical_kind.strip().casefold())
        object.__setattr__(self, "source_uom", _clean_optional(self.source_uom))
        object.__setattr__(self, "canonical_uom", _clean_optional(self.canonical_uom))


@dataclass(frozen=True, slots=True)
class Wits0ImportReviewPlan:
    discovery_fingerprint: str
    dataset_id: str
    dataset_name: str
    dataset_kind: DatasetKind
    index_id: str
    index_candidate_id: str
    index_mnemonic: str
    index_type: IndexType
    index_unit: str | None
    timezone: str | None
    channels: tuple[Wits0ChannelOverride, ...]
    custom_profile_id: str
    custom_profile_revision: int

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[0-9a-f]{64}", self.discovery_fingerprint):
            raise ValueError("discovery_fingerprint must be a SHA-256 digest")
        for value, label in (
            (self.dataset_id, "dataset_id"),
            (self.dataset_name, "dataset_name"),
            (self.index_id, "index_id"),
            (self.index_candidate_id, "index_candidate_id"),
            (self.index_mnemonic, "index_mnemonic"),
            (self.custom_profile_id, "custom_profile_id"),
        ):
            _required_text(value, label)
        if not isinstance(self.dataset_kind, DatasetKind):
            raise ValueError("dataset_kind must use DatasetKind")
        if not isinstance(self.index_type, IndexType):
            raise ValueError("index_type must use IndexType")
        object.__setattr__(self, "index_unit", _clean_optional(self.index_unit))
        object.__setattr__(self, "timezone", _clean_optional(self.timezone))
        if isinstance(self.custom_profile_revision, bool) or self.custom_profile_revision < 1:
            raise ValueError("custom_profile_revision must be positive")
        if not all(isinstance(item, Wits0ChannelOverride) for item in self.channels):
            raise ValueError("channels must contain Wits0ChannelOverride values")
        keys = [item.key for item in self.channels]
        curve_ids = [item.curve_id for item in self.channels]
        if len(keys) != len(set(keys)):
            raise ValueError("Review plan contains duplicate channel keys")
        if len(curve_ids) != len(set(curve_ids)):
            raise ValueError("Review plan contains duplicate curve IDs")


@dataclass(frozen=True, slots=True)
class Wits0ImportChannelReview:
    key: Wits0ChannelKey
    source_mnemonic: str
    source_name: str
    value_kind: str
    import_enabled: bool
    canonical_mnemonic: str
    canonical_kind: str
    quantity_class: QuantityClass
    source_uom: str | None
    canonical_uom: str | None
    confidence: float
    observed_count: int
    valid_count: int
    null_count: int
    samples: tuple[str, ...]
    issues: tuple[Wits0ReviewIssue, ...]


@dataclass(frozen=True, slots=True)
class Wits0ImportReview:
    discovery_fingerprint: str
    selected_index: Wits0IndexCandidate | None
    index_candidates: tuple[Wits0IndexCandidate, ...]
    channels: tuple[Wits0ImportChannelReview, ...]
    issues: tuple[Wits0ReviewIssue, ...]
    schema_preview: AcquisitionDatasetSchema | None

    @property
    def warning_count(self) -> int:
        return sum(item.severity is Wits0ReviewSeverity.WARNING for item in self.issues) + sum(
            item.severity is Wits0ReviewSeverity.WARNING
            for channel in self.channels
            for item in channel.issues
        )

    @property
    def error_count(self) -> int:
        return sum(item.severity is Wits0ReviewSeverity.ERROR for item in self.issues) + sum(
            item.severity is Wits0ReviewSeverity.ERROR
            for channel in self.channels
            for item in channel.issues
        )


@dataclass(frozen=True, slots=True)
class Wits0CustomChannelMapping:
    key: Wits0ChannelKey
    import_enabled: bool
    canonical_mnemonic: str
    canonical_kind: str
    quantity_class: QuantityClass
    source_uom: str | None
    canonical_uom: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.key, Wits0ChannelKey):
            raise ValueError("key must use Wits0ChannelKey")
        if not isinstance(self.import_enabled, bool):
            raise ValueError("import_enabled must be a boolean")
        _required_text(self.canonical_mnemonic, "canonical_mnemonic")
        _required_text(self.canonical_kind, "canonical_kind")
        if not isinstance(self.quantity_class, QuantityClass):
            raise ValueError("quantity_class must use QuantityClass")
        object.__setattr__(
            self, "canonical_mnemonic", self.canonical_mnemonic.strip().upper()
        )
        object.__setattr__(self, "canonical_kind", self.canonical_kind.strip().casefold())
        object.__setattr__(self, "source_uom", _clean_optional(self.source_uom))
        object.__setattr__(self, "canonical_uom", _clean_optional(self.canonical_uom))


@dataclass(frozen=True, slots=True)
class Wits0CustomProfile:
    custom_profile_id: str
    revision: int
    title: str
    base_profile_id: str
    base_profile_version: int
    discovery_fingerprint: str
    index_candidate_id: str
    index_mnemonic: str
    index_type: IndexType
    index_unit: str | None
    timezone: str | None
    channels: tuple[Wits0CustomChannelMapping, ...]
    created_at: str
    schema_version: int = WITS0_CUSTOM_PROFILE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != WITS0_CUSTOM_PROFILE_SCHEMA_VERSION:
            raise ValueError("Unsupported WITS0 custom profile schema version")
        for value, label in (
            (self.custom_profile_id, "custom_profile_id"),
            (self.title, "title"),
            (self.base_profile_id, "base_profile_id"),
            (self.discovery_fingerprint, "discovery_fingerprint"),
            (self.index_candidate_id, "index_candidate_id"),
            (self.index_mnemonic, "index_mnemonic"),
            (self.created_at, "created_at"),
        ):
            _required_text(value, label)
        if (
            isinstance(self.revision, bool)
            or isinstance(self.base_profile_version, bool)
            or self.revision < 1
            or self.base_profile_version < 1
        ):
            raise ValueError("Profile revisions must be positive integers")
        if not re.fullmatch(r"[0-9a-f]{64}", self.discovery_fingerprint):
            raise ValueError("discovery_fingerprint must be a SHA-256 digest")
        if not isinstance(self.index_type, IndexType):
            raise ValueError("index_type must use IndexType")
        object.__setattr__(self, "index_unit", _clean_optional(self.index_unit))
        object.__setattr__(self, "timezone", _clean_optional(self.timezone))
        if not all(isinstance(item, Wits0CustomChannelMapping) for item in self.channels):
            raise ValueError("channels must contain Wits0CustomChannelMapping values")
        if len({item.key for item in self.channels}) != len(self.channels):
            raise ValueError("Custom profile contains duplicate channel keys")


@dataclass(frozen=True, slots=True)
class Wits0ImportReviewCommit:
    review: Wits0ImportReview
    schema: AcquisitionDatasetSchema
    custom_profile: Wits0CustomProfile
    schema_digest: str

    def __post_init__(self) -> None:
        if self.review.schema_preview != self.schema:
            raise ValueError("Committed schema must equal the reviewed schema preview")
        if self.custom_profile.discovery_fingerprint != self.review.discovery_fingerprint:
            raise ValueError("Custom profile and review use different discovery fingerprints")
        expected = acquisition_schema_digest(self.schema)
        if self.schema_digest != expected:
            raise ValueError("schema_digest does not match the committed schema")


class Wits0ImportReviewValidationError(ValueError):
    def __init__(self, review: Wits0ImportReview) -> None:
        self.review = review
        messages = [
            issue.message
            for issue in review.issues
            if issue.severity is Wits0ReviewSeverity.ERROR
        ]
        messages.extend(
            issue.message
            for channel in review.channels
            for issue in channel.issues
            if issue.severity is Wits0ReviewSeverity.ERROR
        )
        super().__init__("; ".join(messages) or "WITS0 Import Review contains blocking errors")


class Wits0ImportReviewController:
    """Headless draft/preview/commit boundary for WITS0 channel mapping."""

    def __init__(self, dictionary: SemanticChannelDictionary | None = None) -> None:
        self.dictionary = dictionary or default_semantic_channel_dictionary()

    def index_candidates(
        self,
        snapshot: Wits0DiscoverySnapshot,
    ) -> tuple[Wits0IndexCandidate, ...]:
        candidates: list[Wits0IndexCandidate] = []
        if snapshot.datetime_observation_count:
            candidates.append(
                Wits0IndexCandidate(
                    candidate_id="header:datetime",
                    source_kind="header_datetime",
                    mnemonic="DATETIME",
                    role=IndexRole.TIME,
                    index_type=IndexType.DATETIME,
                    source_uom=None,
                    canonical_uom=None,
                    confidence=1.0,
                    observation_count=snapshot.datetime_observation_count,
                    evidence=("WITS header items 05 + 06",),
                )
            )
        for channel in snapshot.channels:
            if not channel.numeric or not channel.valid_count:
                continue
            binding = self._automatic_binding(channel)
            mnemonic = binding.canonical_mnemonic.upper()
            depth_hint = (
                binding.quantity_class is QuantityClass.LENGTH
                and (
                    "DEPTH" in mnemonic
                    or mnemonic in {"MD", "TVD", "TVDSS", "DEPT"}
                    or channel.record_index_type in {"depth", "depth_lagged"}
                )
            )
            time_hint = binding.quantity_class is QuantityClass.TIME or "TIME" in mnemonic
            if depth_hint:
                confidence = 0.98 if "DEPTH" in mnemonic or mnemonic in {"MD", "TVD", "TVDSS"} else 0.75
                index_type = (
                    IndexType.TVDSS
                    if "TVDSS" in mnemonic
                    else IndexType.TVD
                    if "TVD" in mnemonic
                    else IndexType.MD
                )
                candidates.append(
                    Wits0IndexCandidate(
                        candidate_id=f"field:{channel.key.source_id}",
                        source_kind="field",
                        mnemonic=mnemonic,
                        role=IndexRole.DEPTH,
                        index_type=index_type,
                        source_uom=channel.source_uom,
                        canonical_uom=binding.canonical_uom,
                        confidence=confidence,
                        observation_count=channel.valid_count,
                        evidence=(
                            f"WITS0 field {channel.key.source_id}",
                            f"record index type={channel.record_index_type or 'unknown'}",
                            f"quantity={binding.quantity_class.value}",
                        ),
                        channel_key=channel.key,
                    )
                )
            elif time_hint:
                candidates.append(
                    Wits0IndexCandidate(
                        candidate_id=f"field:{channel.key.source_id}",
                        source_kind="field",
                        mnemonic=mnemonic,
                        role=IndexRole.TIME,
                        index_type=IndexType.RELATIVE_TIME,
                        source_uom=channel.source_uom,
                        canonical_uom=binding.canonical_uom,
                        confidence=0.8,
                        observation_count=channel.valid_count,
                        evidence=(
                            f"WITS0 field {channel.key.source_id}",
                            f"quantity={binding.quantity_class.value}",
                        ),
                        channel_key=channel.key,
                    )
                )
        return tuple(
            sorted(
                candidates,
                key=lambda item: (
                    item.source_kind != "header_datetime",
                    -item.confidence,
                    item.candidate_id,
                ),
            )
        )

    def initial_plan(
        self,
        snapshot: Wits0DiscoverySnapshot,
        *,
        dataset_name: str = "WITS0 Live",
        custom_profile: Wits0CustomProfile | None = None,
    ) -> Wits0ImportReviewPlan:
        if custom_profile is not None and (
            custom_profile.base_profile_id != snapshot.profile_id
            or custom_profile.base_profile_version != snapshot.profile_version
        ):
            raise ValueError(
                "Custom WITS0 profile belongs to another base profile or version"
            )
        candidates = self.index_candidates(snapshot)
        selected = candidates[0] if candidates else None
        dataset_id = str(uuid4())
        custom_by_key = (
            {item.key: item for item in custom_profile.channels}
            if custom_profile is not None
            else {}
        )
        overrides: list[Wits0ChannelOverride] = []
        for channel in snapshot.channels:
            automatic = self._automatic_binding(channel)
            stored = custom_by_key.get(channel.key)
            overrides.append(
                Wits0ChannelOverride(
                    key=channel.key,
                    curve_id=_stable_id(dataset_id, f"curve:{channel.key.source_id}"),
                    import_enabled=(
                        stored.import_enabled
                        if stored is not None
                        else channel.numeric and channel.valid_count > 0
                    ),
                    canonical_mnemonic=(
                        stored.canonical_mnemonic
                        if stored is not None
                        else automatic.canonical_mnemonic
                    ),
                    canonical_kind=(
                        stored.canonical_kind if stored is not None else automatic.canonical_kind
                    ),
                    quantity_class=(
                        stored.quantity_class
                        if stored is not None
                        else automatic.quantity_class
                    ),
                    source_uom=(
                        stored.source_uom if stored is not None else channel.source_uom
                    ),
                    canonical_uom=(
                        stored.canonical_uom
                        if stored is not None
                        else automatic.canonical_uom
                    ),
                )
            )
        if custom_profile is not None:
            custom_candidate = next(
                (
                    item
                    for item in candidates
                    if item.candidate_id == custom_profile.index_candidate_id
                ),
                None,
            )
            selected = custom_candidate or selected
        index_type = (
            custom_profile.index_type
            if custom_profile is not None
            else selected.index_type
            if selected is not None
            else IndexType.DATETIME
        )
        index_unit = (
            custom_profile.index_unit
            if custom_profile is not None
            else selected.canonical_uom
            if selected is not None
            else None
        )
        index_mnemonic = (
            custom_profile.index_mnemonic
            if custom_profile is not None
            else selected.mnemonic
            if selected is not None
            else "DATETIME"
        )
        timezone_name = custom_profile.timezone if custom_profile is not None else "UTC"
        custom_profile_id = (
            custom_profile.custom_profile_id
            if custom_profile is not None
            else f"{snapshot.profile_id}-review"
        )
        revision = custom_profile.revision + 1 if custom_profile is not None else 1
        return Wits0ImportReviewPlan(
            discovery_fingerprint=snapshot.fingerprint,
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            dataset_kind=DatasetKind.GTI,
            index_id=_stable_id(dataset_id, "index:active"),
            index_candidate_id=selected.candidate_id if selected is not None else "missing",
            index_mnemonic=index_mnemonic,
            index_type=index_type,
            index_unit=index_unit,
            timezone=timezone_name,
            channels=tuple(overrides),
            custom_profile_id=custom_profile_id,
            custom_profile_revision=revision,
        )

    def preview(
        self,
        snapshot: Wits0DiscoverySnapshot,
        profile: Wits0Profile,
        plan: Wits0ImportReviewPlan,
    ) -> Wits0ImportReview:
        issues: list[Wits0ReviewIssue] = []
        if snapshot.profile_id != profile.profile_id or snapshot.profile_version != profile.version:
            issues.append(
                Wits0ReviewIssue(
                    "profile-mismatch",
                    Wits0ReviewSeverity.ERROR,
                    "Discovery snapshot does not belong to the selected WITS0 profile",
                )
            )
        if plan.discovery_fingerprint != snapshot.fingerprint:
            issues.append(
                Wits0ReviewIssue(
                    "stale-discovery",
                    Wits0ReviewSeverity.ERROR,
                    "Detected record/item set changed after this review plan was created",
                )
            )
        candidates = self.index_candidates(snapshot)
        selected = next(
            (item for item in candidates if item.candidate_id == plan.index_candidate_id),
            None,
        )
        if selected is None:
            issues.append(
                Wits0ReviewIssue(
                    "missing-index",
                    Wits0ReviewSeverity.ERROR,
                    "A detected time or depth index must be selected",
                )
            )
        else:
            expected_role = selected.role
            compatible = {
                IndexRole.DEPTH: {IndexType.MD, IndexType.TVD, IndexType.TVDSS},
                IndexRole.TIME: {IndexType.DATETIME, IndexType.RELATIVE_TIME},
            }
            if plan.index_type not in compatible[expected_role]:
                issues.append(
                    Wits0ReviewIssue(
                        "index-type-conflict",
                        Wits0ReviewSeverity.ERROR,
                        f"Index type {plan.index_type.value} is incompatible with {expected_role.value}",
                    )
                )
            if selected.source_kind == "header_datetime" and not plan.timezone:
                issues.append(
                    Wits0ReviewIssue(
                        "missing-timezone",
                        Wits0ReviewSeverity.ERROR,
                        "WITS header datetime requires an explicit timezone",
                    )
                )
        override_by_key = {item.key: item for item in plan.channels}
        discovered_keys = {item.key for item in snapshot.channels}
        unknown_overrides = set(override_by_key).difference(discovered_keys)
        if unknown_overrides:
            issues.append(
                Wits0ReviewIssue(
                    "unknown-channel-overrides",
                    Wits0ReviewSeverity.ERROR,
                    "Plan references channels absent from discovery: "
                    + ", ".join(item.source_id for item in sorted(unknown_overrides)),
                )
            )
        rows: list[Wits0ImportChannelReview] = []
        canonical_kinds: dict[str, int] = {}
        enabled_count = 0
        for channel in snapshot.channels:
            override = override_by_key.get(channel.key)
            if override is None:
                issues.append(
                    Wits0ReviewIssue(
                        "missing-channel-override",
                        Wits0ReviewSeverity.ERROR,
                        f"No mapping decision exists for WITS0 field {channel.key.source_id}",
                        channel.key,
                    )
                )
                continue
            binding, channel_issues = self._reviewed_binding(channel, override)
            import_enabled = override.import_enabled
            if selected is not None and selected.channel_key == channel.key:
                import_enabled = False
                channel_issues.append(
                    Wits0ReviewIssue(
                        "index-channel-excluded",
                        Wits0ReviewSeverity.INFO,
                        "Selected index field is represented by the dataset index, not a curve",
                        channel.key,
                    )
                )
            if import_enabled:
                enabled_count += 1
                canonical_kinds[binding.canonical_kind] = (
                    canonical_kinds.get(binding.canonical_kind, 0) + 1
                )
            if override.import_enabled and not channel.numeric:
                channel_issues.append(
                    Wits0ReviewIssue(
                        "non-numeric-channel",
                        Wits0ReviewSeverity.ERROR,
                        "Current AcquisitionDatasetSchema supports numeric curves only",
                        channel.key,
                    )
                )
            if override.import_enabled and channel.valid_count == 0:
                channel_issues.append(
                    Wits0ReviewIssue(
                        "all-null-channel",
                        Wits0ReviewSeverity.WARNING,
                        "Detected channel has no valid typed values",
                        channel.key,
                    )
                )
            if not channel.known:
                channel_issues.append(
                    Wits0ReviewIssue(
                        "unknown-profile-field",
                        Wits0ReviewSeverity.WARNING,
                        "Field is absent from the base WITS0 profile and requires manual confirmation",
                        channel.key,
                    )
                )
            rows.append(
                Wits0ImportChannelReview(
                    key=channel.key,
                    source_mnemonic=channel.source_mnemonic,
                    source_name=channel.name,
                    value_kind=channel.value_kind,
                    import_enabled=import_enabled,
                    canonical_mnemonic=binding.canonical_mnemonic,
                    canonical_kind=binding.canonical_kind,
                    quantity_class=binding.quantity_class,
                    source_uom=binding.source_uom,
                    canonical_uom=binding.canonical_uom,
                    confidence=binding.confidence,
                    observed_count=channel.observed_count,
                    valid_count=channel.valid_count,
                    null_count=channel.null_count,
                    samples=channel.samples,
                    issues=tuple(channel_issues),
                )
            )
        if enabled_count == 0:
            issues.append(
                Wits0ReviewIssue(
                    "no-enabled-channels",
                    Wits0ReviewSeverity.ERROR,
                    "At least one numeric WITS0 data channel must be enabled",
                )
            )
        duplicates = sorted(
            kind
            for kind, count in canonical_kinds.items()
            if count > 1 and not kind.startswith("unknown.")
        )
        if duplicates:
            issues.append(
                Wits0ReviewIssue(
                    "duplicate-canonical-kind",
                    Wits0ReviewSeverity.WARNING,
                    "Several enabled fields map to the same semantic kind: "
                    + ", ".join(duplicates),
                )
            )
        schema: AcquisitionDatasetSchema | None = None
        if not _has_errors(issues, rows) and selected is not None:
            schema = self._build_schema(plan, selected, rows)
        return Wits0ImportReview(
            discovery_fingerprint=snapshot.fingerprint,
            selected_index=selected,
            index_candidates=candidates,
            channels=tuple(rows),
            issues=tuple(issues),
            schema_preview=schema,
        )

    def commit(
        self,
        snapshot: Wits0DiscoverySnapshot,
        profile: Wits0Profile,
        plan: Wits0ImportReviewPlan,
        *,
        created_at: str | None = None,
    ) -> Wits0ImportReviewCommit:
        review = self.preview(snapshot, profile, plan)
        if review.error_count or review.schema_preview is None:
            raise Wits0ImportReviewValidationError(review)
        custom_profile = Wits0CustomProfile(
            custom_profile_id=plan.custom_profile_id,
            revision=plan.custom_profile_revision,
            title=f"{profile.title} — reviewed mapping",
            base_profile_id=profile.profile_id,
            base_profile_version=profile.version,
            discovery_fingerprint=snapshot.fingerprint,
            index_candidate_id=plan.index_candidate_id,
            index_mnemonic=plan.index_mnemonic,
            index_type=plan.index_type,
            index_unit=plan.index_unit,
            timezone=plan.timezone,
            channels=tuple(
                Wits0CustomChannelMapping(
                    key=item.key,
                    import_enabled=item.import_enabled,
                    canonical_mnemonic=item.canonical_mnemonic,
                    canonical_kind=item.canonical_kind,
                    quantity_class=item.quantity_class,
                    source_uom=item.source_uom,
                    canonical_uom=item.canonical_uom,
                )
                for item in plan.channels
            ),
            created_at=created_at or _utc_now(),
        )
        schema = review.schema_preview
        return Wits0ImportReviewCommit(
            review=review,
            schema=schema,
            custom_profile=custom_profile,
            schema_digest=acquisition_schema_digest(schema),
        )

    def _automatic_binding(self, channel: Wits0DiscoveredChannel) -> SemanticChannelBinding:
        return self.dictionary.resolve(
            channel.source_mnemonic,
            description=channel.name,
            unit=channel.source_uom or "",
            source_mnemonic=channel.source_mnemonic,
            canonical_mnemonic=channel.source_mnemonic,
        )

    def _reviewed_binding(
        self,
        channel: Wits0DiscoveredChannel,
        override: Wits0ChannelOverride,
    ) -> tuple[SemanticChannelBinding, list[Wits0ReviewIssue]]:
        automatic = self.dictionary.resolve(
            channel.source_mnemonic,
            description=channel.name,
            unit=override.source_uom or "",
            source_mnemonic=channel.source_mnemonic,
            canonical_mnemonic=override.canonical_mnemonic,
        )
        issues: list[Wits0ReviewIssue] = []
        source_resolution = self.dictionary.uoms.resolve(override.source_uom)
        canonical_resolution = self.dictionary.uoms.resolve(override.canonical_uom)
        quantity = override.quantity_class
        evidence = [
            f"WITS0 field={channel.key.source_id}",
            "mapping confirmed in WITS0 Import Review",
            f"automatic match={automatic.matched_by}",
        ]
        if override.source_uom and not source_resolution.recognized:
            issues.append(
                Wits0ReviewIssue(
                    "unknown-source-uom",
                    Wits0ReviewSeverity.WARNING,
                    f"Source UOM is not recognized: {override.source_uom}",
                    channel.key,
                )
            )
            evidence.append(f"unrecognized source UOM: {override.source_uom}")
        if override.canonical_uom and not canonical_resolution.recognized:
            issues.append(
                Wits0ReviewIssue(
                    "unknown-canonical-uom",
                    Wits0ReviewSeverity.WARNING,
                    f"Canonical UOM is not recognized: {override.canonical_uom}",
                    channel.key,
                )
            )
            evidence.append(f"unrecognized canonical UOM: {override.canonical_uom}")
        if source_resolution.recognized and canonical_resolution.recognized:
            if source_resolution.quantity_class is not canonical_resolution.quantity_class:
                issues.append(
                    Wits0ReviewIssue(
                        "uom-quantity-conflict",
                        Wits0ReviewSeverity.ERROR,
                        "Source and canonical UOM belong to different quantity classes",
                        channel.key,
                    )
                )
            elif source_resolution.canonical != canonical_resolution.canonical:
                issues.append(
                    Wits0ReviewIssue(
                        "uom-conversion-required",
                        Wits0ReviewSeverity.ERROR,
                        "A numeric UOM conversion is required but is not implemented in stage C",
                        channel.key,
                    )
                )
        resolved_quantity = (
            canonical_resolution.quantity_class
            if canonical_resolution.recognized
            else source_resolution.quantity_class
            if source_resolution.recognized
            else QuantityClass.UNKNOWN
        )
        if quantity is not QuantityClass.UNKNOWN and resolved_quantity is not QuantityClass.UNKNOWN:
            if quantity is not resolved_quantity:
                issues.append(
                    Wits0ReviewIssue(
                        "quantity-uom-conflict",
                        Wits0ReviewSeverity.ERROR,
                        f"Quantity {quantity.value} conflicts with selected UOM",
                        channel.key,
                    )
                )
        if quantity is QuantityClass.UNKNOWN:
            issues.append(
                Wits0ReviewIssue(
                    "unknown-quantity",
                    Wits0ReviewSeverity.WARNING,
                    "Engineering quantity class is not confirmed",
                    channel.key,
                )
            )
        if not automatic.resolved and override.canonical_kind.startswith("unknown."):
            issues.append(
                Wits0ReviewIssue(
                    "unresolved-semantic-channel",
                    Wits0ReviewSeverity.WARNING,
                    "Channel is not matched to the Semantic Channel Dictionary",
                    channel.key,
                )
            )
        aliases = _unique(
            (
                override.canonical_mnemonic,
                channel.source_mnemonic,
                automatic.canonical_mnemonic,
                *automatic.aliases,
            )
        )
        manual_semantics = (
            override.canonical_kind != automatic.canonical_kind
            or override.canonical_mnemonic != automatic.canonical_mnemonic
            or quantity is not automatic.quantity_class
            or override.canonical_uom != automatic.canonical_uom
        )
        binding = SemanticChannelBinding(
            canonical_kind=override.canonical_kind,
            canonical_mnemonic=override.canonical_mnemonic,
            quantity_class=quantity,
            canonical_uom=override.canonical_uom,
            source_uom=override.source_uom,
            aliases=aliases,
            sensor_id=None if manual_semantics else automatic.sensor_id,
            source="wits0-import-review" if manual_semantics else automatic.source,
            family="manual" if manual_semantics else automatic.family,
            category=override.canonical_kind.partition(".")[0] or "manual",
            source_mnemonic=channel.source_mnemonic,
            confidence=1.0 if manual_semantics else automatic.confidence,
            matched_by="manual_wits0_import_review" if manual_semantics else automatic.matched_by,
            evidence=_unique((*automatic.evidence, *evidence)),
        )
        return binding, issues

    def _build_schema(
        self,
        plan: Wits0ImportReviewPlan,
        selected: Wits0IndexCandidate,
        rows: list[Wits0ImportChannelReview],
    ) -> AcquisitionDatasetSchema:
        role = selected.role
        depth_domain = (
            DepthDomain.TIME
            if role is IndexRole.TIME
            else DepthDomain.TVDSS
            if plan.index_type is IndexType.TVDSS
            else DepthDomain.TVD
            if plan.index_type is IndexType.TVD
            else DepthDomain.MD
        )
        index = AcquisitionIndexSchema(
            index_id=plan.index_id,
            mnemonic=plan.index_mnemonic.strip().upper(),
            index_type=plan.index_type,
            role=role,
            unit=plan.index_unit,
            confidence=selected.confidence,
            evidence=_unique((*selected.evidence, "confirmed by WITS0 Import Review")),
            datetime_format=("WITS items 05+06" if selected.source_kind == "header_datetime" else None),
            timezone=(plan.timezone if selected.source_kind == "header_datetime" else None),
        )
        override_by_key = {item.key: item for item in plan.channels}
        curves: list[AcquisitionCurveSchema] = []
        for row in rows:
            override = override_by_key[row.key]
            if not row.import_enabled:
                continue
            binding, _issues = self._reviewed_binding(
                Wits0DiscoveredChannel(
                    key=row.key,
                    source_mnemonic=row.source_mnemonic,
                    name=row.source_name,
                    source_uom=row.source_uom,
                    value_kind=row.value_kind,
                    aggregation=None,
                    record_index_type=None,
                    known=True,
                    observed_count=row.observed_count,
                    valid_count=row.valid_count,
                    null_count=row.null_count,
                    error_count=0,
                    numeric_min=None,
                    numeric_max=None,
                    samples=row.samples,
                ),
                override,
            )
            metadata = CurveMetadata(
                curve_id=override.curve_id,
                original_mnemonic=f"WITS_{row.key.source_id}_{row.source_mnemonic}",
                canonical_mnemonic=binding.canonical_mnemonic,
                unit=binding.canonical_uom,
                description=f"WITS0 {row.key.source_id} — {row.source_name}",
                source_dataset_id=plan.dataset_id,
                provenance=f"wits0:{row.key.source_id}",
                semantic=binding,
            )
            curves.append(AcquisitionCurveSchema(metadata))
        return AcquisitionDatasetSchema(
            dataset_id=plan.dataset_id,
            name=plan.dataset_name.strip(),
            kind=plan.dataset_kind,
            depth_domain=depth_domain,
            indexes=(index,),
            active_index_id=index.index_id,
            curves=tuple(curves),
        )


def acquisition_schema_digest(schema: AcquisitionDatasetSchema) -> str:
    payload = asdict(schema)
    return sha256(
        json.dumps(
            _json_compatible(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def save_wits0_custom_profile(
    profile: Wits0CustomProfile,
    directory: str | Path,
) -> Path:
    target_directory = Path(directory)
    target_directory.mkdir(parents=True, exist_ok=True)
    safe_id = _safe_token(profile.custom_profile_id)
    target = target_directory / f"{safe_id}.v{profile.revision}.json"
    payload = _custom_profile_to_payload(profile)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    except FileExistsError as exc:
        raise FileExistsError(f"WITS0 custom profile revision already exists: {target}") from exc
    return target


def load_wits0_custom_profile(path: str | Path) -> Wits0CustomProfile:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read WITS0 custom profile {source}: {exc}") from exc
    return _custom_profile_from_payload(payload)


def next_wits0_custom_profile_revision(directory: str | Path, custom_profile_id: str) -> int:
    root = Path(directory)
    if not root.exists():
        return 1
    safe_id = _safe_token(custom_profile_id)
    revisions: list[int] = []
    pattern = re.compile(rf"^{re.escape(safe_id)}\.v([1-9][0-9]*)\.json$")
    for path in root.iterdir():
        match = pattern.match(path.name)
        if match:
            revisions.append(int(match.group(1)))
    return max(revisions, default=0) + 1


def _custom_profile_to_payload(profile: Wits0CustomProfile) -> dict[str, Any]:
    return {
        "schemaVersion": profile.schema_version,
        "customProfileId": profile.custom_profile_id,
        "revision": profile.revision,
        "title": profile.title,
        "baseProfile": {
            "profileId": profile.base_profile_id,
            "version": profile.base_profile_version,
        },
        "discoveryFingerprint": profile.discovery_fingerprint,
        "index": {
            "candidateId": profile.index_candidate_id,
            "mnemonic": profile.index_mnemonic,
            "indexType": profile.index_type.value,
            "unit": profile.index_unit,
            "timezone": profile.timezone,
        },
        "channels": [
            {
                "record": item.key.record_no,
                "item": item.key.item_no,
                "importEnabled": item.import_enabled,
                "canonicalMnemonic": item.canonical_mnemonic,
                "canonicalKind": item.canonical_kind,
                "quantityClass": item.quantity_class.value,
                "sourceUom": item.source_uom,
                "canonicalUom": item.canonical_uom,
            }
            for item in profile.channels
        ],
        "createdAt": profile.created_at,
    }


def _custom_profile_from_payload(payload: Any) -> Wits0CustomProfile:
    if not isinstance(payload, dict):
        raise ValueError("WITS0 custom profile root must be an object")
    _reject_unknown(
        payload,
        {
            "schemaVersion",
            "customProfileId",
            "revision",
            "title",
            "baseProfile",
            "discoveryFingerprint",
            "index",
            "channels",
            "createdAt",
        },
        "WITS0 custom profile",
    )
    base = _required_object(payload, "baseProfile")
    _reject_unknown(base, {"profileId", "version"}, "baseProfile")
    index = _required_object(payload, "index")
    _reject_unknown(index, {"candidateId", "mnemonic", "indexType", "unit", "timezone"}, "index")
    channels_payload = payload.get("channels")
    if not isinstance(channels_payload, list):
        raise ValueError("channels must be an array")
    channels: list[Wits0CustomChannelMapping] = []
    for row in channels_payload:
        if not isinstance(row, dict):
            raise ValueError("Each custom channel mapping must be an object")
        _reject_unknown(
            row,
            {
                "record",
                "item",
                "importEnabled",
                "canonicalMnemonic",
                "canonicalKind",
                "quantityClass",
                "sourceUom",
                "canonicalUom",
            },
            "custom channel mapping",
        )
        enabled = row.get("importEnabled")
        if not isinstance(enabled, bool):
            raise ValueError("importEnabled must be a boolean")
        channels.append(
            Wits0CustomChannelMapping(
                key=Wits0ChannelKey(_required_int(row, "record"), _required_int(row, "item")),
                import_enabled=enabled,
                canonical_mnemonic=_required_str(row, "canonicalMnemonic").upper(),
                canonical_kind=_required_str(row, "canonicalKind").casefold(),
                quantity_class=QuantityClass(_required_str(row, "quantityClass")),
                source_uom=_optional_str(row, "sourceUom"),
                canonical_uom=_optional_str(row, "canonicalUom"),
            )
        )
    return Wits0CustomProfile(
        custom_profile_id=_required_str(payload, "customProfileId"),
        revision=_required_int(payload, "revision"),
        title=_required_str(payload, "title"),
        base_profile_id=_required_str(base, "profileId"),
        base_profile_version=_required_int(base, "version"),
        discovery_fingerprint=_required_str(payload, "discoveryFingerprint"),
        index_candidate_id=_required_str(index, "candidateId"),
        index_mnemonic=_required_str(index, "mnemonic"),
        index_type=IndexType(_required_str(index, "indexType")),
        index_unit=_optional_str(index, "unit"),
        timezone=_optional_str(index, "timezone"),
        channels=tuple(channels),
        created_at=_required_str(payload, "createdAt"),
        schema_version=_required_int(payload, "schemaVersion"),
    )



def _infer_unknown_numeric(value: str) -> float | None:
    candidate = value.strip()
    if not candidate:
        return None
    if "," in candidate and "." not in candidate:
        candidate = candidate.replace(",", ".")
    try:
        numeric = float(candidate)
    except (TypeError, ValueError, OverflowError):
        return None
    return numeric if isfinite(numeric) else None


def _frame_datetime(frame: Wits0ParsedFrame) -> datetime | None:
    dates = [
        item.value
        for item in frame.fields
        if item.item_no == 5 and isinstance(item.value, date)
    ]
    times = [
        item.value
        for item in frame.fields
        if item.item_no == 6 and isinstance(item.value, time)
    ]
    if not dates or not times:
        return None
    return datetime.combine(dates[0], times[0])


def _render_sample(value: object) -> str:
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, float):
        return f"{value:.12g}"
    return str(value)


def _stable_id(dataset_id: str, token: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"geolog:wits0:{dataset_id}:{token}"))


def _safe_token(value: str) -> str:
    cleaned = _TOKEN.sub("-", value.strip()).strip(".-")
    return cleaned[:96] or "wits0-profile"


def _clean_optional(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip() or None


def _required_text(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")


def _optional_text(value: str | None, label: str) -> None:
    if value is not None:
        _required_text(value, label)


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return tuple(result)


def _has_errors(
    issues: Iterable[Wits0ReviewIssue],
    channels: Iterable[Wits0ImportChannelReview],
) -> bool:
    return any(item.severity is Wits0ReviewSeverity.ERROR for item in issues) or any(
        item.severity is Wits0ReviewSeverity.ERROR
        for channel in channels
        for item in channel.issues
    )


def _json_compatible(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return [_json_compatible(item) for item in value]
    if isinstance(value, list):
        return [_json_compatible(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    return value


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _reject_unknown(payload: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(payload).difference(allowed)
    if unknown:
        raise ValueError(f"{label} contains unknown fields: {sorted(unknown)}")


def _required_object(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value.strip()


def _optional_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be null or a non-empty string")
    return value.strip()


def _required_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value
