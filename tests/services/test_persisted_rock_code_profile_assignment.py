from __future__ import annotations

import pytest

from geoworkbench.domain.rock_code_profiles import RockCodeProfileRecord
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.persisted_rock_code_profile_assignment import (
    assign_persisted_rock_code_profile,
)
from geoworkbench.services.persisted_rock_code_profiles import (
    PersistedRockCodeProfileResolver,
)
from geoworkbench.services.rock_code_dictionary import RockCodeDictionary, RockCodeEntry
from geoworkbench.services.rock_code_profile_registry import (
    RockCodeProfileRegistry,
    RockCodeProfileRegistryError,
    SupplierRockCodeProfile,
)
from geoworkbench.services.rock_code_source_binding import RockCodeSourceBindingError


SOURCE_SHA = "a" * 64


def _profile(
    supplier: str,
    *,
    name: str = "Profile v1",
    rock_name: str = "Sandstone",
    color: str = "#d2b48c",
) -> SupplierRockCodeProfile:
    dictionary = RockCodeDictionary(
        name=name,
        source="synthetic assignment test",
        entries=(
            RockCodeEntry(
                source_code=7,
                lithotype_id="las-code-7",
                code="7",
                name_ru=rock_name,
                name_kk=rock_name,
                name_en=rock_name,
                category="sedimentary",
                color=color,
                pattern_key="sandstone",
            ),
        ),
    )
    return SupplierRockCodeProfile(supplier, dictionary)


def test_assignment_persists_exact_revision_and_binding() -> None:
    session = ProjectSession()
    registry = RockCodeProfileRegistry((_profile("Vendor A"),))

    result = assign_persisted_rock_code_profile(
        session,
        source_sha256=SOURCE_SHA,
        supplier_name=" vendor a ",
        profiles=registry,
    )

    assert result.changed
    assert result.profile_revision_created
    assert result.binding_changed
    assert session.dirty
    assert session.rock_code_profiles == {
        result.profile.profile_sha256: result.profile,
    }
    assert session.rock_code_source_bindings == {SOURCE_SHA: result.binding}

    resolved = PersistedRockCodeProfileResolver.from_session(session).require(SOURCE_SHA)
    assert resolved.profile == result.profile
    assert resolved.binding == result.binding
    assert resolved.dictionary == registry.require_dictionary("Vendor A")


def test_repeating_same_assignment_is_idempotent_and_does_not_dirty_session() -> None:
    session = ProjectSession()
    registry = RockCodeProfileRegistry((_profile("Vendor A"),))
    first = assign_persisted_rock_code_profile(
        session,
        source_sha256=SOURCE_SHA,
        supplier_name="Vendor A",
        profiles=registry,
    )
    session.dirty = False

    second = assign_persisted_rock_code_profile(
        session,
        source_sha256=SOURCE_SHA,
        supplier_name="VENDOR A",
        profiles=registry,
    )

    assert second.profile == first.profile
    assert second.binding == first.binding
    assert not second.changed
    assert not second.profile_revision_created
    assert not second.binding_changed
    assert session.dirty is False
    assert len(session.rock_code_profiles) == 1
    assert len(session.rock_code_source_bindings) == 1


def test_reassignment_keeps_old_revision_and_moves_only_source_binding() -> None:
    session = ProjectSession()
    first_registry = RockCodeProfileRegistry((_profile("Vendor A"),))
    first = assign_persisted_rock_code_profile(
        session,
        source_sha256=SOURCE_SHA,
        supplier_name="Vendor A",
        profiles=first_registry,
    )
    session.dirty = False

    second_registry = RockCodeProfileRegistry(
        (_profile("Vendor A", name="Profile v2", rock_name="Limestone", color="#cccccc"),)
    )
    second = assign_persisted_rock_code_profile(
        session,
        source_sha256=SOURCE_SHA,
        supplier_name="Vendor A",
        profiles=second_registry,
    )

    assert second.changed
    assert second.profile_revision_created
    assert second.binding_changed
    assert session.dirty
    assert first.profile.profile_sha256 != second.profile.profile_sha256
    assert session.rock_code_profiles[first.profile.profile_sha256] == first.profile
    assert session.rock_code_profiles[second.profile.profile_sha256] == second.profile
    assert session.rock_code_source_bindings[SOURCE_SHA] == second.binding


def test_unknown_supplier_fails_without_mutating_session() -> None:
    session = ProjectSession()
    registry = RockCodeProfileRegistry((_profile("Vendor A"),))

    with pytest.raises(RockCodeProfileRegistryError, match="не зарегистрирован"):
        assign_persisted_rock_code_profile(
            session,
            source_sha256=SOURCE_SHA,
            supplier_name="Vendor B",
            profiles=registry,
        )

    assert session.rock_code_profiles == {}
    assert session.rock_code_source_bindings == {}
    assert session.dirty is False


def test_same_dictionary_sha_cannot_be_relabelled_to_another_supplier() -> None:
    session = ProjectSession()
    vendor_a = _profile("Vendor A")
    registry_a = RockCodeProfileRegistry((vendor_a,))
    first = assign_persisted_rock_code_profile(
        session,
        source_sha256=SOURCE_SHA,
        supplier_name="Vendor A",
        profiles=registry_a,
    )
    session.dirty = False
    original_profiles = dict(session.rock_code_profiles)
    original_bindings = dict(session.rock_code_source_bindings)

    # The dictionary bytes (and therefore SHA) are intentionally identical;
    # only supplier identity differs.  The immutable revision must not be
    # silently relabelled under the same content-addressed key.
    vendor_b = SupplierRockCodeProfile("Vendor B", vendor_a.dictionary)
    registry_b = RockCodeProfileRegistry((vendor_b,))

    with pytest.raises(RockCodeSourceBindingError, match="другой идентичностью"):
        assign_persisted_rock_code_profile(
            session,
            source_sha256="b" * 64,
            supplier_name="Vendor B",
            profiles=registry_b,
        )

    assert session.rock_code_profiles == original_profiles
    assert session.rock_code_source_bindings == original_bindings
    assert session.dirty is False
    assert session.rock_code_profiles[first.profile.profile_sha256] == first.profile


def test_malformed_existing_ledger_is_rejected_before_mutation() -> None:
    session = ProjectSession()
    profile = _profile("Vendor A")
    profile_json = profile.dictionary.to_json()
    valid = assign_persisted_rock_code_profile(
        session,
        source_sha256=SOURCE_SHA,
        supplier_name="Vendor A",
        profiles=RockCodeProfileRegistry((profile,)),
    )
    session.rock_code_profiles["b" * 64] = RockCodeProfileRecord(
        supplier_name="Vendor A",
        profile_json=profile_json,
        profile_sha256=valid.profile.profile_sha256,
    )
    session.dirty = False

    with pytest.raises(RockCodeSourceBindingError, match="Ключ persisted profile"):
        assign_persisted_rock_code_profile(
            session,
            source_sha256="c" * 64,
            supplier_name="Vendor A",
            profiles=RockCodeProfileRegistry((profile,)),
        )

    assert "c" * 64 not in session.rock_code_source_bindings
    assert session.dirty is False
