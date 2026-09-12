"""Persist explicit rock-code profile assignments for immutable source revisions."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING

from geoworkbench.domain.rock_code_profiles import (
    RockCodeProfileRecord,
    RockCodeSourceBindingRecord,
)
from geoworkbench.services.persisted_rock_code_profiles import (
    PersistedRockCodeProfileResolver,
)
from geoworkbench.services.rock_code_dictionary import RockCodeDictionary
from geoworkbench.services.rock_code_profile_registry import SupplierRockCodeProfile
from geoworkbench.services.rock_code_source_binding import RockCodeSourceBindingError

if TYPE_CHECKING:
    from geoworkbench.project.session import ProjectSession


@dataclass(frozen=True, slots=True)
class PersistedRockCodeProfileAssignment:
    """Result of assigning one immutable source to one immutable profile revision."""

    profile: RockCodeProfileRecord
    binding: RockCodeSourceBindingRecord
    profile_created: bool
    binding_changed: bool


def assign_persisted_rock_code_profile(
    session: ProjectSession,
    *,
    source_sha256: str,
    supplier_name: str,
    dictionary: RockCodeDictionary,
) -> PersistedRockCodeProfileAssignment:
    """Persist one exact source/profile assignment without silent replacement.

    Profile revisions are content-addressed by canonical dictionary JSON. Repeating
    the same assignment is idempotent. Reassigning a source updates only its binding;
    historical profile revisions remain available for audit/reproducibility.

    Existing persisted ledgers are validated before any mutation so new provenance
    can never be written on top of malformed project state.
    """

    # Fail closed before constructing or writing any new assignment.  This keeps the
    # persisted profile/binding ledgers a single validated provenance boundary.
    PersistedRockCodeProfileResolver.from_session(session)

    supplier_profile = SupplierRockCodeProfile(supplier_name, dictionary)
    canonical_json = supplier_profile.dictionary.to_json()
    profile_sha256 = sha256(canonical_json.encode("utf-8")).hexdigest()

    profile = RockCodeProfileRecord(
        supplier_name=supplier_profile.supplier_name,
        profile_json=canonical_json,
        profile_sha256=profile_sha256,
    )
    binding = RockCodeSourceBindingRecord(
        source_sha256=source_sha256,
        supplier_name=supplier_profile.supplier_name,
        profile_sha256=profile_sha256,
    )

    existing_profile = session.rock_code_profiles.get(profile_sha256)
    if existing_profile is not None and existing_profile != profile:
        raise RockCodeSourceBindingError(
            "Ревизия профиля с тем же SHA-256 уже сохранена с другой идентичностью поставщика"
        )

    existing_binding = session.rock_code_source_bindings.get(source_sha256)
    profile_created = existing_profile is None
    binding_changed = existing_binding != binding
    if not profile_created and not binding_changed:
        return PersistedRockCodeProfileAssignment(
            profile=profile,
            binding=binding,
            profile_created=False,
            binding_changed=False,
        )

    if profile_created:
        session.rock_code_profiles[profile_sha256] = profile
    if binding_changed:
        session.rock_code_source_bindings[source_sha256] = binding
    session.dirty = True

    return PersistedRockCodeProfileAssignment(
        profile=profile,
        binding=binding,
        profile_created=profile_created,
        binding_changed=binding_changed,
    )
