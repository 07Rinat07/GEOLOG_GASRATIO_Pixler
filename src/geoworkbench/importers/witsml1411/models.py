from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from ipaddress import ip_address
from typing import Any, Mapping, cast
from urllib.parse import urlsplit


class Witsml1411AuthMode(StrEnum):
    NONE = "none"
    BASIC = "basic"


@dataclass(frozen=True, slots=True)
class Witsml1411Credentials:
    username: str = ""
    password: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "username", self.username.strip())


@dataclass(frozen=True, slots=True)
class Witsml1411RetryPolicy:
    max_attempts: int = 3
    backoff_seconds: float = 0.5
    max_backoff_seconds: float = 4.0
    retry_http_statuses: tuple[int, ...] = (408, 425, 429, 500, 502, 503, 504)

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.backoff_seconds < 0 or self.max_backoff_seconds < 0:
            raise ValueError("retry backoff values must be non-negative")
        if self.max_backoff_seconds < self.backoff_seconds:
            raise ValueError("max_backoff_seconds must be >= backoff_seconds")


@dataclass(frozen=True, slots=True)
class Witsml1411ConnectionProfile:
    profile_id: str
    name: str
    endpoint: str
    auth_mode: Witsml1411AuthMode = Witsml1411AuthMode.BASIC
    username: str = ""
    credential_id: str | None = None
    timeout_seconds: float = 20.0
    verify_tls: bool = True
    retry: Witsml1411RetryPolicy = field(default_factory=Witsml1411RetryPolicy)
    data_version: str = "1.4.1.1"

    def __post_init__(self) -> None:
        profile_id = self.profile_id.strip()
        name = self.name.strip()
        endpoint = self.endpoint.strip()
        username = self.username.strip()
        credential_id = self.credential_id.strip() if self.credential_id else None
        data_version = self.data_version.strip()
        if not profile_id or not name or not endpoint:
            raise ValueError("profile_id, name and endpoint must be non-empty")
        parts = urlsplit(endpoint)
        scheme = parts.scheme.casefold()
        if scheme not in {"http", "https"}:
            raise ValueError("WITSML endpoint must use HTTP or HTTPS")
        if not parts.hostname:
            raise ValueError("WITSML endpoint must contain a host")
        if parts.username is not None or parts.password is not None:
            raise ValueError("Credentials must not be embedded in the WITSML endpoint URL")
        if parts.fragment:
            raise ValueError("WITSML endpoint must not contain a URL fragment")
        local = _is_loopback_host(parts.hostname)
        if scheme == "http" and not local:
            raise ValueError("Remote WITSML endpoints must use HTTPS")
        if scheme == "https" and not self.verify_tls and not local:
            raise ValueError("TLS verification can be disabled only for localhost")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not data_version:
            raise ValueError("data_version must be non-empty")
        object.__setattr__(self, "profile_id", profile_id)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "endpoint", endpoint)
        object.__setattr__(self, "username", username)
        object.__setattr__(self, "credential_id", credential_id)
        object.__setattr__(self, "data_version", data_version)
        if not isinstance(self.auth_mode, Witsml1411AuthMode):
            object.__setattr__(self, "auth_mode", Witsml1411AuthMode(str(self.auth_mode)))

    def to_public_dict(self) -> dict[str, object]:
        """Serialize connection metadata without any password or bearer token."""

        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "endpoint": self.endpoint,
            "auth_mode": self.auth_mode.value,
            "username": self.username,
            "credential_id": self.credential_id,
            "timeout_seconds": self.timeout_seconds,
            "verify_tls": self.verify_tls,
            "data_version": self.data_version,
            "retry": {
                "max_attempts": self.retry.max_attempts,
                "backoff_seconds": self.retry.backoff_seconds,
                "max_backoff_seconds": self.retry.max_backoff_seconds,
                "retry_http_statuses": list(self.retry.retry_http_statuses),
            },
        }

    @classmethod
    def from_public_dict(cls, data: Mapping[str, object]) -> "Witsml1411ConnectionProfile":
        retry_data = data.get("retry")
        if not isinstance(retry_data, Mapping):
            retry_data = {}
        statuses = retry_data.get("retry_http_statuses", (408, 425, 429, 500, 502, 503, 504))
        return cls(
            profile_id=str(data["profile_id"]),
            name=str(data["name"]),
            endpoint=str(data["endpoint"]),
            auth_mode=Witsml1411AuthMode(str(data.get("auth_mode", "basic"))),
            username=str(data.get("username", "")),
            credential_id=(str(data["credential_id"]) if data.get("credential_id") else None),
            timeout_seconds=_coerce_float(data.get("timeout_seconds", 20.0)),
            verify_tls=bool(data.get("verify_tls", True)),
            data_version=str(data.get("data_version", "1.4.1.1")),
            retry=Witsml1411RetryPolicy(
                max_attempts=int(retry_data.get("max_attempts", 3)),
                backoff_seconds=float(retry_data.get("backoff_seconds", 0.5)),
                max_backoff_seconds=float(retry_data.get("max_backoff_seconds", 4.0)),
                retry_http_statuses=tuple(int(item) for item in statuses),
            ),
        )


def _is_loopback_host(host: str) -> bool:
    normalized = host.rstrip(".").casefold()
    if normalized == "localhost":
        return True
    try:
        return ip_address(normalized).is_loopback
    except ValueError:
        return False


def _coerce_float(value: object) -> float:
    """Preserve ``float`` input semantics while narrowing an untyped payload."""

    return float(cast(Any, value))


@dataclass(frozen=True, slots=True)
class Witsml1411Capabilities:
    data_version: str
    description: str | None
    vendor: str | None
    functions: tuple[str, ...]
    data_objects: tuple[str, ...]
    raw_xml: str

    @property
    def supports_get_from_store(self) -> bool:
        return any(item.casefold() == "wmls_getfromstore" for item in self.functions)


@dataclass(frozen=True, slots=True)
class Witsml1411Well:
    uid: str
    name: str
    field: str | None = None
    operator: str | None = None
    d_tim_last_change: str | None = None


@dataclass(frozen=True, slots=True)
class Witsml1411Wellbore:
    uid: str
    uid_well: str
    name: str
    name_well: str | None = None
    status: str | None = None
    purpose: str | None = None
    d_tim_last_change: str | None = None


@dataclass(frozen=True, slots=True)
class Witsml1411LogCurve:
    uid: str | None
    mnemonic: str
    unit: str | None
    curve_description: str | None = None
    type_log_data: str | None = None
    min_index: str | None = None
    max_index: str | None = None
    null_value: str | None = None


@dataclass(frozen=True, slots=True)
class Witsml1411LogHeader:
    uid: str
    uid_well: str
    uid_wellbore: str
    name: str
    name_well: str | None
    name_wellbore: str | None
    index_type: str | None
    index_curve: str | None
    start_index: str | None
    end_index: str | None
    start_datetime_index: str | None
    end_datetime_index: str | None
    direction: str | None
    curves: tuple[Witsml1411LogCurve, ...]
    d_tim_last_change: str | None = None


@dataclass(frozen=True, slots=True)
class Witsml1411LogData:
    header: Witsml1411LogHeader
    mnemonic_list: tuple[str, ...]
    unit_list: tuple[str | None, ...]
    rows: tuple[tuple[str | None, ...], ...]
    raw_xml: str
    source_sha256: str


@dataclass(frozen=True, slots=True)
class Witsml1411SoapCallResult:
    operation: str
    result: int | None
    xml_out: str | None
    supplementary_message: str | None
    raw_response: bytes
    http_status: int
    request_id: str
    attempts: int
    duration_seconds: float


@dataclass(frozen=True, slots=True)
class Witsml1411AuditEvent:
    timestamp_utc: datetime
    request_id: str
    operation: str
    endpoint: str
    attempt: int
    outcome: str
    duration_seconds: float
    http_status: int | None = None
    witsml_result: int | None = None
    supplementary_message: str | None = None
    object_type: str | None = None
    selection: Mapping[str, str] = field(default_factory=dict)
