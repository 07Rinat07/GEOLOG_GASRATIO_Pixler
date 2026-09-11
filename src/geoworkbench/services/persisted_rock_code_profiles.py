"""Resolve persisted rock-code bindings by exact immutable profile revision.

The live supplier registry intentionally models one current profile per supplier.
Project persistence is different: a project may retain multiple historical
revisions for the same supplier so old immutable sources remain reproducible.
This module is the narrow bridge between those persisted ledgers and import
services. It never falls back to a supplier's newest profile.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING, Mapping

from geoworkbench.domain.rock_code_profiles import (
    RockCodeProfileRecord,
    RockCodeSourceBindingRecord,
)
from geoworkbench.services.rock_code_dictionary import (
    RockCodeDictionary,
    RockCodeDictionaryError,
)
from geoworkbench.services.rock_code_source_binding import RockCodeSourceBindingError

if TYPE_CHECKING:
    from geoworkbench.project.session import ProjectSession


@dataclass(frozen=True, slots=True)
class ResolvedPersistedRockCodeProfile:
    """One source binding resolved to the exact persisted dictionary revision."""

    binding: RockCodeSourceBindingRecord
    profile: RockCodeProfileRecord
    dictionary: RockCodeDictionary


class PersistedRockCodeProfileResolver:
    """Fail-closed resolver for project-level immutable profile ledgers."""

    __slots__ = ("_profiles", "_bindings")

    def __init__(
        self,
        profiles: Mapping[str, RockCodeProfileRecord],
        bindings: Mapping[str, RockCodeSourceBindingRecord],
    ) -> None:
        parsed_profiles: dict[str, tuple[RockCodeProfileRecord, RockCodeDictionary]] = {}
        for profile_sha256, record in profiles.items():
            if not isinstance(record, RockCodeProfileRecord):
                raise RockCodeSourceBindingError(
                    "Persisted profile ledger принимает только RockCodeProfileRecord"
                )
            if profile_sha256 != record.profile_sha256:
                raise RockCodeSourceBindingError(
                    "Ключ persisted profile не совпадает с profile_sha256"
                )
            try:
                dictionary = RockCodeDictionary.from_json(record.profile_json)
            except RockCodeDictionaryError as exc:
                raise RockCodeSourceBindingError(
                    "Persisted profile содержит некорректный rock-code dictionary"
                ) from exc
            canonical_json = dictionary.to_json()
            if canonical_json != record.profile_json:
                raise RockCodeSourceBindingError(
                    "Persisted profile_json должен использовать канонический формат"
                )
            digest = sha256(canonical_json.encode("utf-8")).hexdigest()
            if digest != record.profile_sha256:
                raise RockCodeSourceBindingError(
                    "Persisted profile SHA-256 не соответствует dictionary"
                )
            parsed_profiles[profile_sha256] = (record, dictionary)

        validated_bindings: dict[str, RockCodeSourceBindingRecord] = {}
        for source_sha256, binding in bindings.items():
            if not isinstance(binding, RockCodeSourceBindingRecord):
                raise RockCodeSourceBindingError(
                    "Persisted binding ledger принимает только RockCodeSourceBindingRecord"
                )
            if source_sha256 != binding.source_sha256:
                raise RockCodeSourceBindingError(
                    "Ключ persisted source binding не совпадает с source_sha256"
                )
            resolved = parsed_profiles.get(binding.profile_sha256)
            if resolved is None:
                raise RockCodeSourceBindingError(
                    "Persisted source binding ссылается на отсутствующую ревизию профиля"
                )
            profile, _ = resolved
            if profile.supplier_name != binding.supplier_name:
                raise RockCodeSourceBindingError(
                    "Поставщик persisted binding не совпадает с ревизией профиля"
                )
            validated_bindings[source_sha256] = binding

        self._profiles = parsed_profiles
        self._bindings = validated_bindings

    @classmethod
    def from_session(cls, session: ProjectSession) -> PersistedRockCodeProfileResolver:
        """Build the resolver from the document-level ledgers of one session."""

        return cls(session.rock_code_profiles, session.rock_code_source_bindings)

    def require(self, source_sha256: str) -> ResolvedPersistedRockCodeProfile:
        """Resolve one immutable source without supplier/profile fallback."""

        try:
            binding = self._bindings[source_sha256]
        except KeyError as exc:
            raise RockCodeSourceBindingError(
                f"Для источника не сохранена привязка профиля кодов пород: {source_sha256}"
            ) from exc
        profile, dictionary = self._profiles[binding.profile_sha256]
        return ResolvedPersistedRockCodeProfile(binding, profile, dictionary)

    def require_dictionary(self, source_sha256: str) -> RockCodeDictionary:
        """Return the exact dictionary revision pinned to ``source_sha256``."""

        return self.require(source_sha256).dictionary
