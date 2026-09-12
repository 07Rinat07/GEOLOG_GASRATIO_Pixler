"""Persist explicit source-to-rock-profile assignments.

Supplier profile selection is a mutable application concern, while geology
review must be reproducible from immutable project state.  This module is the
single write boundary that snapshots the selected supplier dictionary and
binds one immutable source SHA-256 to that exact profile revision.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from geoworkbench.domain.rock_code_profiles import (
    RockCodeProfileRecord,
    RockCodeSourceBindingRecord,
)
from geoworkbench.services.persisted_rock_code_profiles import (
    PersistedRockCodeProfileResolver,
)
from geoworkbench.services.rock_code_profile_registry import RockCodeProfileRegistry
from geoworkbench.services.rock_code_source_binding import (
    RockCodeSourceBindingError,
    bind_source_profile,
)

if TYPE_CHECKING:
    from geoworkbench.project.session import ProjectSession


@dataclass(frozen=True, slots=True)
class PersistedRockCodeProfileAssignment:
    """Result of one explicit profile assignment."""

    profile: RockCodeProfileRecord
    binding: RockCodeSourceBindingRecord
    profile_revision_created: bool
    binding_changed: bool

    @property
    def changed(self) -> bool:
        return self.profile_revision_created or self.binding_changed


def assign_persisted_rock_code_profile(
    session: ProjectSession,
    *,
    source_sha256: str,
    supplier_name: str,
    profiles: RockCodeProfileRegistry,
) -> PersistedRockCodeProfileAssignment:
    """Snapshot and bind the selected supplier profile to ``source_sha256``.

    The current project ledgers are validated before any mutation.  Repeating
    the same assignment is idempotent; assigning a newer revision replaces only
    the source binding and retains every older immutable profile revision.
    """

    # Refuse to build new state on top of a malformed persisted ledger.
    PersistedRockCodeProfileResolver.from_session(session)

    live_binding = bind_source_profile(source_sha256, supplier_name, profiles)
    selected = profiles.require(live_binding.supplier_name)
    profile_json = selected.dictionary.to_json()
    profile_record = RockCodeProfileRecord(
        supplier_name=selected.supplier_name,
        profile_json=profile_json,
        profile_sha256=live_binding.profile_sha256,
    )
    binding_record = RockCodeSourceBindingRecord(
        source_sha256=live_binding.source_sha256,
        supplier_name=live_binding.supplier_name,
        profile_sha256=live_binding.profile_sha256,
    )

    existing_profile = session.rock_code_profiles.get(profile_record.profile_sha256)
    if existing_profile is not None and existing_profile != profile_record:
        raise RockCodeSourceBindingError(
            "Ревизия профиля с таким SHA-256 уже сохранена с другой идентичностью поставщика"
        )

    existing_binding = session.rock_code_source_bindings.get(binding_record.source_sha256)
    profile_revision_created = existing_profile is None
    binding_changed = existing_binding != binding_record

    if profile_revision_created:
        session.rock_code_profiles[profile_record.profile_sha256] = profile_record
    if binding_changed:
        session.rock_code_source_bindings[binding_record.source_sha256] = binding_record
    if profile_revision_created or binding_changed:
        session.dirty = True

    return PersistedRockCodeProfileAssignment(
        profile=profile_record,
        binding=binding_record,
        profile_revision_created=profile_revision_created,
        binding_changed=binding_changed,
    )
