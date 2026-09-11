"""Explicit supplier-to-rock-profile policy for geology imports.

A raw numeric LAS rock code has no portable geological meaning by itself.
Supplier profiles therefore have to be selected explicitly; this registry has
no default profile and deliberately fails closed for unknown suppliers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from geoworkbench.services.rock_code_dictionary import (
    RockCodeDictionary,
    RockCodeDictionaryError,
)


_MAX_SUPPLIER_NAME = 500


class RockCodeProfileRegistryError(RockCodeDictionaryError):
    """Raised when a supplier profile cannot be registered or resolved."""


def _supplier_key(value: str) -> str:
    if not isinstance(value, str):
        raise RockCodeProfileRegistryError("Имя поставщика должно быть строкой")
    stripped = value.strip()
    if not stripped or len(stripped) > _MAX_SUPPLIER_NAME:
        raise RockCodeProfileRegistryError("Некорректное имя поставщика")
    return stripped.casefold()


@dataclass(frozen=True, slots=True)
class SupplierRockCodeProfile:
    """One explicitly named supplier and its validated rock-code dictionary."""

    supplier_name: str
    dictionary: RockCodeDictionary

    def __post_init__(self) -> None:
        _supplier_key(self.supplier_name)
        if not isinstance(self.dictionary, RockCodeDictionary):
            raise RockCodeProfileRegistryError("Профиль поставщика должен содержать RockCodeDictionary")
        object.__setattr__(self, "supplier_name", self.supplier_name.strip())


class RockCodeProfileRegistry:
    """Fail-closed registry for independent supplier rock-code profiles.

    Supplier names are matched after whitespace trimming and ``casefold`` only.
    There is intentionally no fallback/default dictionary: an import must name
    the supplier whose coding contract is being applied.
    """

    __slots__ = ("_by_supplier",)

    def __init__(self, profiles: Iterable[SupplierRockCodeProfile] = ()) -> None:
        by_supplier: dict[str, SupplierRockCodeProfile] = {}
        for profile in profiles:
            if not isinstance(profile, SupplierRockCodeProfile):
                raise RockCodeProfileRegistryError(
                    "Registry принимает только SupplierRockCodeProfile"
                )
            key = _supplier_key(profile.supplier_name)
            if key in by_supplier:
                raise RockCodeProfileRegistryError(
                    f"Профиль поставщика уже зарегистрирован: {profile.supplier_name}"
                )
            by_supplier[key] = profile
        self._by_supplier = by_supplier

    @property
    def suppliers(self) -> tuple[str, ...]:
        """Return registered display names in deterministic lookup order."""

        return tuple(profile.supplier_name for profile in self._by_supplier.values())

    def require(self, supplier_name: str) -> SupplierRockCodeProfile:
        """Resolve an explicitly named supplier or fail without a fallback."""

        key = _supplier_key(supplier_name)
        try:
            return self._by_supplier[key]
        except KeyError as exc:
            raise RockCodeProfileRegistryError(
                f"Профиль кодов пород для поставщика не зарегистрирован: {supplier_name.strip()}"
            ) from exc

    def require_dictionary(self, supplier_name: str) -> RockCodeDictionary:
        """Resolve only the dictionary for a supplier at an import boundary."""

        return self.require(supplier_name).dictionary
