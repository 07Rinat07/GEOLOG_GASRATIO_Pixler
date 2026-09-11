"""Persistence-safe records for supplier rock profiles and source bindings.

These records intentionally live in the domain layer and store only primitive
values. Parsing a rock-code dictionary remains a service responsibility, so the
domain model does not depend on import/application services.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MAX_SUPPLIER_NAME = 500
_MAX_PROFILE_BYTES = 4 * 1024 * 1024


def _validate_sha256(value: str, *, label: str) -> None:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{label} должен быть SHA-256 в нижнем регистре")


def _validate_supplier_name(value: str) -> None:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
        or len(value) > _MAX_SUPPLIER_NAME
    ):
        raise ValueError("Некорректное имя поставщика профиля пород")


@dataclass(frozen=True, slots=True)
class RockCodeProfileRecord:
    """One immutable supplier dictionary revision pinned by its exact JSON hash."""

    supplier_name: str
    profile_json: str
    profile_sha256: str

    def __post_init__(self) -> None:
        _validate_supplier_name(self.supplier_name)
        _validate_sha256(self.profile_sha256, label="profile_sha256")
        if not isinstance(self.profile_json, str):
            raise ValueError("profile_json должен быть строкой")
        payload = self.profile_json.encode("utf-8")
        if not payload or len(payload) > _MAX_PROFILE_BYTES:
            raise ValueError("Некорректный размер profile_json")
        if sha256(payload).hexdigest() != self.profile_sha256:
            raise ValueError("profile_sha256 не соответствует profile_json")


@dataclass(frozen=True, slots=True)
class RockCodeSourceBindingRecord:
    """Persisted assignment of one immutable source to one profile revision."""

    source_sha256: str
    supplier_name: str
    profile_sha256: str

    def __post_init__(self) -> None:
        _validate_sha256(self.source_sha256, label="source_sha256")
        _validate_supplier_name(self.supplier_name)
        _validate_sha256(self.profile_sha256, label="profile_sha256")
