"""Fail-closed source-to-supplier rock-profile bindings.

A supplier name alone is not enough to reproduce a geology import: the profile
may be edited later. Each binding therefore pins one immutable source SHA-256
to both the supplier identity and the exact dictionary SHA-256 used for it.
Persistence and UI live outside this policy layer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable

from geoworkbench.services.rock_code_dictionary import RockCodeDictionary
from geoworkbench.services.rock_code_profile_registry import (
    RockCodeProfileRegistry,
    RockCodeProfileRegistryError,
    SupplierRockCodeProfile,
)


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MAX_SUPPLIER_NAME = 500


class RockCodeSourceBindingError(RockCodeProfileRegistryError):
    """Raised when a source/profile binding is missing, ambiguous, or stale."""


def rock_code_dictionary_sha256(dictionary: RockCodeDictionary) -> str:
    """Return the canonical SHA-256 used to pin one dictionary revision."""

    if not isinstance(dictionary, RockCodeDictionary):
        raise RockCodeSourceBindingError("Профиль должен содержать RockCodeDictionary")
    return sha256(dictionary.to_json().encode("utf-8")).hexdigest()


def _validate_sha256(value: str, *, label: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise RockCodeSourceBindingError(f"{label} должен быть SHA-256 в нижнем регистре")
    return value


@dataclass(frozen=True, slots=True)
class SourceRockProfileBinding:
    """Exact supplier-profile revision assigned to one immutable source file."""

    source_sha256: str
    supplier_name: str
    profile_sha256: str

    def __post_init__(self) -> None:
        _validate_sha256(self.source_sha256, label="source_sha256")
        _validate_sha256(self.profile_sha256, label="profile_sha256")
        if (
            not isinstance(self.supplier_name, str)
            or not self.supplier_name.strip()
            or len(self.supplier_name) > _MAX_SUPPLIER_NAME
        ):
            raise RockCodeSourceBindingError("Некорректное имя поставщика")
        if self.supplier_name != self.supplier_name.strip():
            raise RockCodeSourceBindingError(
                "Имя поставщика в сохранённой привязке должно быть нормализовано"
            )


class RockCodeSourceBindingRegistry:
    """Resolve immutable sources only through their explicitly pinned profile."""

    __slots__ = ("_by_source",)

    def __init__(self, bindings: Iterable[SourceRockProfileBinding] = ()) -> None:
        by_source: dict[str, SourceRockProfileBinding] = {}
        for binding in bindings:
            if not isinstance(binding, SourceRockProfileBinding):
                raise RockCodeSourceBindingError(
                    "Registry принимает только SourceRockProfileBinding"
                )
            if binding.source_sha256 in by_source:
                raise RockCodeSourceBindingError(
                    f"Источник уже имеет профиль: {binding.source_sha256}"
                )
            by_source[binding.source_sha256] = binding
        self._by_source = by_source

    @property
    def bindings(self) -> tuple[SourceRockProfileBinding, ...]:
        return tuple(self._by_source.values())

    def require(self, source_sha256: str) -> SourceRockProfileBinding:
        source_sha256 = _validate_sha256(source_sha256, label="source_sha256")
        try:
            return self._by_source[source_sha256]
        except KeyError as exc:
            raise RockCodeSourceBindingError(
                f"Для источника не назначен профиль кодов пород: {source_sha256}"
            ) from exc

    def require_profile(
        self,
        source_sha256: str,
        profiles: RockCodeProfileRegistry,
    ) -> SupplierRockCodeProfile:
        """Resolve a binding and reject a changed/missing supplier profile."""

        binding = self.require(source_sha256)
        try:
            profile = profiles.require(binding.supplier_name)
        except RockCodeProfileRegistryError as exc:
            raise RockCodeSourceBindingError(str(exc)) from exc
        current_sha256 = rock_code_dictionary_sha256(profile.dictionary)
        if current_sha256 != binding.profile_sha256:
            raise RockCodeSourceBindingError(
                "Профиль кодов пород изменился после привязки источника; "
                "назначьте новую ревизию явно"
            )
        return profile

    def require_dictionary(
        self,
        source_sha256: str,
        profiles: RockCodeProfileRegistry,
    ) -> RockCodeDictionary:
        return self.require_profile(source_sha256, profiles).dictionary


def bind_source_profile(
    source_sha256: str,
    supplier_name: str,
    profiles: RockCodeProfileRegistry,
) -> SourceRockProfileBinding:
    """Create a binding pinned to the supplier's current dictionary revision."""

    source_sha256 = _validate_sha256(source_sha256, label="source_sha256")
    try:
        profile = profiles.require(supplier_name)
    except RockCodeProfileRegistryError as exc:
        raise RockCodeSourceBindingError(str(exc)) from exc
    return SourceRockProfileBinding(
        source_sha256=source_sha256,
        supplier_name=profile.supplier_name,
        profile_sha256=rock_code_dictionary_sha256(profile.dictionary),
    )
