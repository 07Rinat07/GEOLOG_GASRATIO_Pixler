from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

from geoworkbench.acquisition.wits0 import Wits0FieldDefinition, Wits0ProfileError


WITS0_CATALOG_SCHEMA_VERSION = 1
_SUPPORTED_DECLARED_TYPES = {"A", "S", "L", "F", "D", "T"}
_SUPPORTED_VALUE_KINDS = {"text", "integer", "float", "date", "time"}


@dataclass(frozen=True, slots=True)
class Wits0CatalogField:
    record_no: int
    item_no: int
    description: str
    short_mnemonic: str
    long_mnemonic: str
    declared_type: str
    value_kind: str
    declared_length: int

    def __post_init__(self) -> None:
        for value, label in ((self.record_no, "record_no"), (self.item_no, "item_no")):
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 99:
                raise Wits0ProfileError(f"{label} must be an integer in the range 0..99")
        for value, label in (
            (self.description, "description"),
            (self.short_mnemonic, "short_mnemonic"),
            (self.long_mnemonic, "long_mnemonic"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise Wits0ProfileError(f"{label} must be a non-empty string")
        if self.declared_type not in _SUPPORTED_DECLARED_TYPES:
            raise Wits0ProfileError(
                f"Unsupported WITS0 catalog declared type: {self.declared_type}"
            )
        if self.value_kind not in _SUPPORTED_VALUE_KINDS:
            raise Wits0ProfileError(
                f"Unsupported WITS0 catalog value kind: {self.value_kind}"
            )
        if (
            isinstance(self.declared_length, bool)
            or not isinstance(self.declared_length, int)
            or self.declared_length < 0
        ):
            raise Wits0ProfileError("declared_length must be a non-negative integer")

    @property
    def source_id(self) -> str:
        return f"{self.record_no:02d}{self.item_no:02d}"

    @property
    def canonical_mnemonic(self) -> str:
        return self.long_mnemonic.strip().upper() or self.short_mnemonic.strip().upper()

    def to_definition(self) -> Wits0FieldDefinition:
        """Create a parser definition without inventing UOM or aggregation semantics."""

        return Wits0FieldDefinition(
            item_no=self.item_no,
            canonical_mnemonic=self.canonical_mnemonic,
            name_ru=self.description,
            source_unit=None,
            value_kind=self.value_kind,
            aggregation="exact",
        )


@dataclass(frozen=True, slots=True)
class Wits0FieldCatalog:
    catalog_id: str
    title: str
    version: int
    source: dict[str, Any]
    fields: tuple[Wits0CatalogField, ...]
    schema_version: int = WITS0_CATALOG_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != WITS0_CATALOG_SCHEMA_VERSION:
            raise Wits0ProfileError(
                f"Unsupported WITS0 catalog schema version: {self.schema_version}"
            )
        if not self.catalog_id.strip() or not self.title.strip():
            raise Wits0ProfileError("WITS0 catalog id/title must not be empty")
        if isinstance(self.version, bool) or self.version < 1:
            raise Wits0ProfileError("WITS0 catalog version must be positive")
        if not self.fields:
            raise Wits0ProfileError("WITS0 catalog must contain fields")
        keys = [(item.record_no, item.item_no) for item in self.fields]
        if len(keys) != len(set(keys)):
            raise Wits0ProfileError("WITS0 catalog contains duplicate record/item keys")

    @property
    def record_numbers(self) -> tuple[int, ...]:
        return tuple(sorted({item.record_no for item in self.fields}))

    def has_record(self, record_no: int) -> bool:
        return any(item.record_no == record_no for item in self.fields)

    def field(self, record_no: int, item_no: int) -> Wits0CatalogField | None:
        return next(
            (
                item
                for item in self.fields
                if item.record_no == record_no and item.item_no == item_no
            ),
            None,
        )


def load_builtin_wits0_catalog(
    catalog_id: str = "geosensor-wits-level0",
) -> Wits0FieldCatalog:
    resource = (
        files("geoworkbench.resources")
        .joinpath("wits")
        .joinpath("catalogs")
        .joinpath(f"{catalog_id}.json")
    )
    try:
        payload = json.loads(resource.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise Wits0ProfileError(f"Unknown built-in WITS0 catalog: {catalog_id}") from exc
    except json.JSONDecodeError as exc:
        raise Wits0ProfileError(f"Invalid built-in WITS0 catalog {catalog_id}: {exc}") from exc
    return _catalog_from_payload(payload)


def load_wits0_catalog(path: str | Path) -> Wits0FieldCatalog:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Wits0ProfileError(f"Cannot read WITS0 catalog {source}: {exc}") from exc
    return _catalog_from_payload(payload)


def _catalog_from_payload(payload: Any) -> Wits0FieldCatalog:
    if not isinstance(payload, dict):
        raise Wits0ProfileError("WITS0 catalog root must be an object")
    allowed = {"schemaVersion", "catalogId", "title", "version", "source", "fields"}
    unknown = set(payload) - allowed
    if unknown:
        raise Wits0ProfileError(
            f"WITS0 catalog contains unknown fields: {sorted(unknown)}"
        )
    source = payload.get("source")
    fields_payload = payload.get("fields")
    if not isinstance(source, dict):
        raise Wits0ProfileError("WITS0 catalog source must be an object")
    if not isinstance(fields_payload, list):
        raise Wits0ProfileError("WITS0 catalog fields must be an array")

    catalog_fields: list[Wits0CatalogField] = []
    allowed_field = {
        "record",
        "item",
        "description",
        "shortMnemonic",
        "longMnemonic",
        "declaredType",
        "valueKind",
        "declaredLength",
    }
    for item in fields_payload:
        if not isinstance(item, dict):
            raise Wits0ProfileError("Each WITS0 catalog field must be an object")
        unknown_field = set(item) - allowed_field
        if unknown_field:
            raise Wits0ProfileError(
                f"WITS0 catalog field contains unknown fields: {sorted(unknown_field)}"
            )
        catalog_fields.append(
            Wits0CatalogField(
                record_no=_required_int(item, "record"),
                item_no=_required_int(item, "item"),
                description=_required_str(item, "description"),
                short_mnemonic=_required_str(item, "shortMnemonic"),
                long_mnemonic=_required_str(item, "longMnemonic"),
                declared_type=_required_str(item, "declaredType"),
                value_kind=_required_str(item, "valueKind"),
                declared_length=_required_int(item, "declaredLength"),
            )
        )

    return Wits0FieldCatalog(
        catalog_id=_required_str(payload, "catalogId"),
        title=_required_str(payload, "title"),
        version=_required_int(payload, "version"),
        source=dict(source),
        fields=tuple(catalog_fields),
        schema_version=_required_int(payload, "schemaVersion"),
    )


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise Wits0ProfileError(f"{key} must be a non-empty string")
    return value.strip()


def _required_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise Wits0ProfileError(f"{key} must be an integer")
    return value
