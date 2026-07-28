from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum, StrEnum
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit


def _public_float(value: object, field_name: str) -> float:
    if not isinstance(value, bool) and isinstance(
        value, (str, bytes, bytearray, int, float)
    ):
        return float(value)
    raise TypeError(f"{field_name} must be numeric")


def _public_int(value: object, field_name: str) -> int:
    if not isinstance(value, bool) and isinstance(
        value, (str, bytes, bytearray, int, float)
    ):
        return int(value)
    raise TypeError(f"{field_name} must be an integer")


class Etp12Protocol(IntEnum):
    CORE = 0
    CHANNEL_STREAMING = 1
    DISCOVERY = 3
    STORE = 4
    DATA_ARRAY = 9
    CHANNEL_SUBSCRIBE = 21


class Etp12Role(StrEnum):
    CLIENT = "client"
    SERVER = "server"
    CUSTOMER = "customer"
    STORE = "store"
    CONSUMER = "consumer"
    PRODUCER = "producer"


class Etp12AuthMode(StrEnum):
    NONE = "none"
    BASIC = "basic"
    BEARER = "bearer"


class Etp12SessionState(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    NEGOTIATING = "negotiating"
    OPEN = "open"
    RECONNECTING = "reconnecting"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"


class Etp12QualityLevel(StrEnum):
    GOOD = "good"
    SUSPECT = "suspect"
    BAD = "bad"
    MISSING = "missing"
    UNKNOWN = "unknown"


class Etp12SubscriptionState(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    RESTORING = "restoring"
    SUSPENDED = "suspended"
    CLOSED = "closed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Etp12Credentials:
    username: str = ""
    secret: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "username", self.username.strip())


@dataclass(frozen=True, slots=True)
class Etp12RetryPolicy:
    max_attempts: int = 8
    initial_backoff_seconds: float = 0.5
    max_backoff_seconds: float = 30.0
    multiplier: float = 2.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.initial_backoff_seconds < 0 or self.max_backoff_seconds < 0:
            raise ValueError("backoff values must be non-negative")
        if self.max_backoff_seconds < self.initial_backoff_seconds:
            raise ValueError("max_backoff_seconds must be >= initial_backoff_seconds")
        if self.multiplier < 1:
            raise ValueError("multiplier must be >= 1")

    def delay_for_attempt(self, attempt: int) -> float:
        if attempt < 1:
            raise ValueError("attempt must be positive")
        return min(
            self.max_backoff_seconds,
            self.initial_backoff_seconds * (self.multiplier ** (attempt - 1)),
        )


@dataclass(frozen=True, slots=True)
class Etp12ConnectionProfile:
    profile_id: str
    name: str
    endpoint: str
    auth_mode: Etp12AuthMode = Etp12AuthMode.NONE
    username: str = ""
    credential_id: str | None = None
    verify_tls: bool = True
    allow_insecure_localhost: bool = False
    ca_file: str | None = None
    open_timeout_seconds: float = 20.0
    request_timeout_seconds: float = 30.0
    close_timeout_seconds: float = 10.0
    ping_interval_seconds: float = 20.0
    ping_timeout_seconds: float = 20.0
    max_message_bytes: int = 16 * 1024 * 1024
    request_acknowledgement: bool = True
    reconnect: Etp12RetryPolicy = field(default_factory=Etp12RetryPolicy)

    def __post_init__(self) -> None:
        profile_id = self.profile_id.strip()
        name = self.name.strip()
        endpoint = self.endpoint.strip()
        username = self.username.strip()
        credential_id = self.credential_id.strip() if self.credential_id else None
        ca_file = self.ca_file.strip() if self.ca_file else None
        if not profile_id or not name or not endpoint:
            raise ValueError("profile_id, name and endpoint must be non-empty")
        parts = urlsplit(endpoint)
        if parts.scheme not in {"ws", "wss"}:
            raise ValueError("ETP endpoint must use ws:// or wss://")
        if parts.username is not None or parts.password is not None:
            raise ValueError("Credentials must not be embedded in the ETP endpoint URL")
        host = (parts.hostname or "").casefold()
        local = host in {"localhost", "127.0.0.1", "::1"}
        if parts.scheme == "ws" and not (self.allow_insecure_localhost and local):
            raise ValueError(
                "Unencrypted ws:// is allowed only for localhost when explicitly enabled"
            )
        if parts.scheme == "wss" and not self.verify_tls and not local:
            raise ValueError("TLS verification can be disabled only for localhost")
        if not parts.hostname:
            raise ValueError("ETP endpoint must contain a host")
        for value, label in (
            (self.open_timeout_seconds, "open_timeout_seconds"),
            (self.request_timeout_seconds, "request_timeout_seconds"),
            (self.close_timeout_seconds, "close_timeout_seconds"),
            (self.ping_interval_seconds, "ping_interval_seconds"),
            (self.ping_timeout_seconds, "ping_timeout_seconds"),
        ):
            if value <= 0:
                raise ValueError(f"{label} must be positive")
        if self.max_message_bytes < 64 * 1024:
            raise ValueError("max_message_bytes must be at least 64 KiB")
        if not isinstance(self.auth_mode, Etp12AuthMode):
            object.__setattr__(self, "auth_mode", Etp12AuthMode(str(self.auth_mode)))
        object.__setattr__(self, "profile_id", profile_id)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "endpoint", endpoint)
        object.__setattr__(self, "username", username)
        object.__setattr__(self, "credential_id", credential_id)
        object.__setattr__(self, "ca_file", ca_file)

    def to_public_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "endpoint": self.endpoint,
            "auth_mode": self.auth_mode.value,
            "username": self.username,
            "credential_id": self.credential_id,
            "verify_tls": self.verify_tls,
            "allow_insecure_localhost": self.allow_insecure_localhost,
            "ca_file": self.ca_file,
            "open_timeout_seconds": self.open_timeout_seconds,
            "request_timeout_seconds": self.request_timeout_seconds,
            "close_timeout_seconds": self.close_timeout_seconds,
            "ping_interval_seconds": self.ping_interval_seconds,
            "ping_timeout_seconds": self.ping_timeout_seconds,
            "max_message_bytes": self.max_message_bytes,
            "request_acknowledgement": self.request_acknowledgement,
            "reconnect": {
                "max_attempts": self.reconnect.max_attempts,
                "initial_backoff_seconds": self.reconnect.initial_backoff_seconds,
                "max_backoff_seconds": self.reconnect.max_backoff_seconds,
                "multiplier": self.reconnect.multiplier,
            },
        }

    @classmethod
    def from_public_dict(cls, data: Mapping[str, object]) -> "Etp12ConnectionProfile":
        retry = data.get("reconnect")
        retry_map = retry if isinstance(retry, Mapping) else {}
        return cls(
            profile_id=str(data["profile_id"]),
            name=str(data["name"]),
            endpoint=str(data["endpoint"]),
            auth_mode=Etp12AuthMode(str(data.get("auth_mode", "none"))),
            username=str(data.get("username", "")),
            credential_id=(str(data["credential_id"]) if data.get("credential_id") else None),
            verify_tls=bool(data.get("verify_tls", True)),
            allow_insecure_localhost=bool(data.get("allow_insecure_localhost", False)),
            ca_file=(str(data["ca_file"]) if data.get("ca_file") else None),
            open_timeout_seconds=_public_float(
                data.get("open_timeout_seconds", 20.0), "open_timeout_seconds"
            ),
            request_timeout_seconds=_public_float(
                data.get("request_timeout_seconds", 30.0), "request_timeout_seconds"
            ),
            close_timeout_seconds=_public_float(
                data.get("close_timeout_seconds", 10.0), "close_timeout_seconds"
            ),
            ping_interval_seconds=_public_float(
                data.get("ping_interval_seconds", 20.0), "ping_interval_seconds"
            ),
            ping_timeout_seconds=_public_float(
                data.get("ping_timeout_seconds", 20.0), "ping_timeout_seconds"
            ),
            max_message_bytes=_public_int(
                data.get("max_message_bytes", 16 * 1024 * 1024), "max_message_bytes"
            ),
            request_acknowledgement=bool(data.get("request_acknowledgement", True)),
            reconnect=Etp12RetryPolicy(
                max_attempts=_public_int(retry_map.get("max_attempts", 8), "max_attempts"),
                initial_backoff_seconds=_public_float(
                    retry_map.get("initial_backoff_seconds", 0.5),
                    "initial_backoff_seconds",
                ),
                max_backoff_seconds=_public_float(
                    retry_map.get("max_backoff_seconds", 30.0),
                    "max_backoff_seconds",
                ),
                multiplier=_public_float(retry_map.get("multiplier", 2.0), "multiplier"),
            ),
        )


@dataclass(frozen=True, slots=True)
class Etp12SupportedProtocol:
    protocol: Etp12Protocol
    role: Etp12Role
    protocol_version: tuple[int, int, int, int] = (1, 2, 0, 0)


@dataclass(frozen=True, slots=True)
class Etp12NegotiatedSession:
    session_id: str
    server_application_name: str
    server_application_version: str
    server_instance_id: str
    supported_protocols: tuple[Etp12SupportedProtocol, ...]
    supported_data_objects: tuple[str, ...]
    supported_formats: tuple[str, ...]
    supported_compression: tuple[str, ...]
    endpoint_capabilities: Mapping[str, object]
    opened_at_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def supports(self, protocol: Etp12Protocol) -> bool:
        return any(item.protocol == protocol for item in self.supported_protocols)


@dataclass(frozen=True, slots=True)
class Etp12Resource:
    uri: str
    name: str
    data_object_type: str
    source_count: int | None = None
    target_count: int | None = None
    store_created: int | None = None
    store_last_write: int | None = None
    active_status: str | None = None
    alternate_uris: tuple[str, ...] = ()
    custom_data: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Etp12DataObject:
    uri: str
    resource: Etp12Resource | None
    format: str
    data: bytes
    blob_id: str | None = None


@dataclass(frozen=True, slots=True)
class Etp12DataArrayIdentifier:
    key: str
    uri: str
    path_in_resource: str


@dataclass(frozen=True, slots=True)
class Etp12DataArrayMetadata:
    key: str
    identifier: Etp12DataArrayIdentifier
    dimensions: tuple[int, ...]
    transport_array_type: str | None
    logical_array_type: str | None
    store_last_write: int | None = None


@dataclass(frozen=True, slots=True)
class Etp12DataArray:
    key: str
    identifier: Etp12DataArrayIdentifier
    dimensions: tuple[int, ...]
    values: object


@dataclass(frozen=True, slots=True)
class Etp12AttributeMetadata:
    attribute_id: int
    attribute_name: str
    data_kind: str | None = None
    uom: str | None = None
    depth_datum: str | None = None
    property_kind_uri: str | None = None
    axis_vector_lengths: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class Etp12ValueAttribute:
    attribute_id: int
    value: object
    name: str | None = None
    data_kind: str | None = None
    uom: str | None = None
    property_kind_uri: str | None = None


@dataclass(frozen=True, slots=True)
class Etp12PointQuality:
    level: Etp12QualityLevel = Etp12QualityLevel.UNKNOWN
    flags: tuple[str, ...] = ()
    message: str | None = None


@dataclass(frozen=True, slots=True)
class Etp12ChannelMetadata:
    channel_id: int
    channel_uri: str
    channel_name: str
    data_kind: str | None
    uom: str | None
    index_kind: str | None
    start_index: object | None
    end_index: object | None
    description: str | None = None
    index_uom: str | None = None
    index_name: str | None = None
    custom_data: Mapping[str, object] = field(default_factory=dict)
    attribute_metadata: tuple[Etp12AttributeMetadata, ...] = ()


@dataclass(frozen=True, slots=True)
class Etp12ChannelPoint:
    channel_id: int
    index: object
    value: object
    value_attributes: Mapping[str, object] = field(default_factory=dict)
    attributes: tuple[Etp12ValueAttribute, ...] = ()
    quality: Etp12PointQuality = field(default_factory=Etp12PointQuality)


@dataclass(frozen=True, slots=True)
class Etp12ChannelBatch:
    subscription_id: str
    points: tuple[Etp12ChannelPoint, ...]
    received_at_utc: datetime
    message_id: int
    correlation_id: int
    protocol: Etp12Protocol
    generation: int = 1
    channel_uris: Mapping[int, str] = field(default_factory=dict)
    wire_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.received_at_utc.tzinfo is None:
            raise ValueError("received_at_utc must be timezone-aware")
        if self.generation < 1:
            raise ValueError("generation must be positive")




@dataclass(frozen=True, slots=True)
class Etp12RangePage:
    page_number: int
    start_index: object
    end_index: object
    batches: tuple[Etp12ChannelBatch, ...]
    point_count: int


@dataclass(frozen=True, slots=True)
class Etp12RangeRecoveryResult:
    request_uuid: str
    subscription_id: str
    pages: tuple[Etp12RangePage, ...]
    completed: bool
    last_index: object | None
    diagnostics: tuple[str, ...] = ()

    @property
    def point_count(self) -> int:
        return sum(page.point_count for page in self.pages)

@dataclass(frozen=True, slots=True)
class Etp12SubscriptionDefinition:
    subscription_id: str
    channel_uris: tuple[str, ...]
    start_index: object | None = None
    end_index: object | None = None
    data_changes: bool = True
    request_latest_values: bool = True

    def __post_init__(self) -> None:
        token = self.subscription_id.strip()
        uris = tuple(item.strip() for item in self.channel_uris if item.strip())
        if not token or not uris:
            raise ValueError("subscription_id and at least one channel URI are required")
        if len(set(uris)) != len(uris):
            raise ValueError("channel_uris must be unique")
        object.__setattr__(self, "subscription_id", token)
        object.__setattr__(self, "channel_uris", uris)


@dataclass(frozen=True, slots=True)
class Etp12SubscriptionSnapshot:
    definition: Etp12SubscriptionDefinition
    state: Etp12SubscriptionState
    generation: int
    server_subscription_id: int | None = None
    channel_ids: Mapping[str, int] = field(default_factory=dict)
    last_indexes: Mapping[int, object] = field(default_factory=dict)
    last_error: str | None = None


@dataclass(frozen=True, slots=True)
class Etp12MessageHeader:
    protocol: int
    message_type: int
    correlation_id: int
    message_id: int
    message_flags: int

    MULTIPART = 0x01
    FIN = 0x02
    NO_DATA = 0x04
    COMPRESSED = 0x08
    ACK_REQUESTED = 0x10
    EXTENSION = 0x20

    @property
    def is_final(self) -> bool:
        return bool(self.message_flags & self.FIN)

    @property
    def requests_acknowledgement(self) -> bool:
        return bool(self.message_flags & self.ACK_REQUESTED)


@dataclass(frozen=True, slots=True)
class Etp12ReceivedMessage:
    header: Etp12MessageHeader
    body: object
    body_name: str


@dataclass(frozen=True, slots=True)
class Etp12AuditEvent:
    timestamp_utc: datetime
    event: str
    endpoint: str
    outcome: str
    state: Etp12SessionState
    attempt: int = 1
    message_id: int | None = None
    correlation_id: int | None = None
    protocol: int | None = None
    message_type: int | None = None
    duration_seconds: float | None = None
    detail: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Etp12SessionSnapshot:
    state: Etp12SessionState
    generation: int
    negotiated: Etp12NegotiatedSession | None
    reconnect_attempt: int
    sent_messages: int
    received_messages: int
    acknowledgements_sent: int
    acknowledgements_received: int
    pending_requests: int
    subscriptions: tuple[Etp12SubscriptionSnapshot, ...]
    last_error: str | None


def public_sequence(values: Sequence[Any]) -> tuple[Any, ...]:
    return tuple(values)
