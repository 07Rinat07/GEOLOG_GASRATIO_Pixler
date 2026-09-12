from hashlib import sha256

import pytest

from geoworkbench.domain.rock_code_profiles import RockCodeProfileRecord
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.persisted_rock_code_profile_assignment import (
    RockCodeProfileReassignmentRequired,
    assign_persisted_rock_code_profile,
)
from geoworkbench.services.rock_code_dictionary import RockCodeDictionary
from geoworkbench.services.rock_code_source_binding import RockCodeSourceBindingError


def _dictionary(*, name: str, source: str) -> RockCodeDictionary:
    return RockCodeDictionary(name=name, source=source, entries=())


def test_assignment_persists_canonical_profile_and_source_binding() -> None:
    session = ProjectSession()
    source_sha256 = "a" * 64
    dictionary = _dictionary(name="Supplier A profile", source="Supplier A")

    result = assign_persisted_rock_code_profile(
        session,
        source_sha256=source_sha256,
        supplier_name=" Supplier A ",
        dictionary=dictionary,
    )

    canonical_json = dictionary.to_json()
    expected_profile_sha256 = sha256(canonical_json.encode("utf-8")).hexdigest()
    assert result.profile_created is True
    assert result.binding_changed is True
    assert result.profile.profile_json == canonical_json
    assert result.profile.profile_sha256 == expected_profile_sha256
    assert session.rock_code_profiles == {expected_profile_sha256: result.profile}
    assert session.rock_code_source_bindings == {source_sha256: result.binding}
    assert result.binding.supplier_name == "Supplier A"
    assert session.dirty is True


def test_repeated_assignment_is_idempotent_and_does_not_dirty_session() -> None:
    session = ProjectSession()
    source_sha256 = "b" * 64
    dictionary = _dictionary(name="Supplier A profile", source="Supplier A")
    first = assign_persisted_rock_code_profile(
        session,
        source_sha256=source_sha256,
        supplier_name="Supplier A",
        dictionary=dictionary,
    )
    session.dirty = False

    second = assign_persisted_rock_code_profile(
        session,
        source_sha256=source_sha256,
        supplier_name="Supplier A",
        dictionary=dictionary,
    )

    assert second.profile == first.profile
    assert second.binding == first.binding
    assert second.profile_created is False
    assert second.binding_changed is False
    assert session.dirty is False
    assert len(session.rock_code_profiles) == 1
    assert len(session.rock_code_source_bindings) == 1


def test_reassignment_requires_explicit_consent_without_mutating_session() -> None:
    session = ProjectSession()
    source_sha256 = "c" * 64
    first = assign_persisted_rock_code_profile(
        session,
        source_sha256=source_sha256,
        supplier_name="Supplier A",
        dictionary=_dictionary(name="Profile v1", source="Supplier A"),
    )
    session.dirty = False
    profiles_before = dict(session.rock_code_profiles)
    bindings_before = dict(session.rock_code_source_bindings)

    with pytest.raises(RockCodeProfileReassignmentRequired) as exc_info:
        assign_persisted_rock_code_profile(
            session,
            source_sha256=source_sha256,
            supplier_name="Supplier A",
            dictionary=_dictionary(name="Profile v2", source="Supplier A"),
        )

    error = exc_info.value
    assert error.source_sha256 == source_sha256
    assert error.current_binding == first.binding
    assert error.requested_binding.source_sha256 == source_sha256
    assert error.requested_binding.profile_sha256 != first.binding.profile_sha256
    assert session.rock_code_profiles == profiles_before
    assert session.rock_code_source_bindings == bindings_before
    assert session.dirty is False


def test_explicit_reassignment_preserves_old_profile_revision() -> None:
    session = ProjectSession()
    source_sha256 = "d" * 64
    first = assign_persisted_rock_code_profile(
        session,
        source_sha256=source_sha256,
        supplier_name="Supplier A",
        dictionary=_dictionary(name="Profile v1", source="Supplier A"),
    )
    session.dirty = False

    second = assign_persisted_rock_code_profile(
        session,
        source_sha256=source_sha256,
        supplier_name="Supplier A",
        dictionary=_dictionary(name="Profile v2", source="Supplier A"),
        allow_reassignment=True,
    )

    assert second.profile_created is True
    assert second.binding_changed is True
    assert first.profile.profile_sha256 != second.profile.profile_sha256
    assert session.rock_code_profiles[first.profile.profile_sha256] == first.profile
    assert session.rock_code_profiles[second.profile.profile_sha256] == second.profile
    assert session.rock_code_source_bindings[source_sha256] == second.binding
    assert session.dirty is True


def test_same_profile_hash_cannot_be_relabelled_to_another_supplier() -> None:
    session = ProjectSession()
    dictionary = _dictionary(name="Shared profile", source="Vendor profile")
    assign_persisted_rock_code_profile(
        session,
        source_sha256="e" * 64,
        supplier_name="Supplier A",
        dictionary=dictionary,
    )
    session.dirty = False
    profiles_before = dict(session.rock_code_profiles)
    bindings_before = dict(session.rock_code_source_bindings)

    with pytest.raises(RockCodeSourceBindingError, match="тем же SHA-256"):
        assign_persisted_rock_code_profile(
            session,
            source_sha256="f" * 64,
            supplier_name="Supplier B",
            dictionary=dictionary,
        )

    assert session.rock_code_profiles == profiles_before
    assert session.rock_code_source_bindings == bindings_before
    assert session.dirty is False


def test_invalid_source_sha_fails_without_mutating_session() -> None:
    session = ProjectSession()

    with pytest.raises(ValueError, match="source_sha256"):
        assign_persisted_rock_code_profile(
            session,
            source_sha256="not-a-sha",
            supplier_name="Supplier A",
            dictionary=_dictionary(name="Profile", source="Supplier A"),
        )

    assert session.rock_code_profiles == {}
    assert session.rock_code_source_bindings == {}
    assert session.dirty is False


def test_malformed_existing_profile_ledger_is_rejected_before_mutation() -> None:
    session = ProjectSession()
    dictionary = _dictionary(name="Profile v1", source="Supplier A")
    first = assign_persisted_rock_code_profile(
        session,
        source_sha256="0" * 64,
        supplier_name="Supplier A",
        dictionary=dictionary,
    )
    session.rock_code_profiles["1" * 64] = RockCodeProfileRecord(
        supplier_name=first.profile.supplier_name,
        profile_json=first.profile.profile_json,
        profile_sha256=first.profile.profile_sha256,
    )
    session.dirty = False
    profiles_before = dict(session.rock_code_profiles)
    bindings_before = dict(session.rock_code_source_bindings)

    with pytest.raises(RockCodeSourceBindingError, match="Ключ persisted profile"):
        assign_persisted_rock_code_profile(
            session,
            source_sha256="2" * 64,
            supplier_name="Supplier A",
            dictionary=_dictionary(name="Profile v2", source="Supplier A"),
        )

    assert session.rock_code_profiles == profiles_before
    assert session.rock_code_source_bindings == bindings_before
    assert session.dirty is False
