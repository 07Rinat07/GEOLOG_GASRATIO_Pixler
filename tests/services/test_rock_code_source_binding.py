from __future__ import annotations

import pytest

from geoworkbench.services.rock_code_dictionary import RockCodeDictionary, RockCodeEntry
from geoworkbench.services.rock_code_profile_registry import (
    RockCodeProfileRegistry,
    SupplierRockCodeProfile,
)
from geoworkbench.services.rock_code_source_binding import (
    RockCodeSourceBindingError,
    RockCodeSourceBindingRegistry,
    SourceRockProfileBinding,
    bind_source_profile,
    rock_code_dictionary_sha256,
)


_SOURCE_A = "a" * 64
_SOURCE_B = "b" * 64


def _profile(
    supplier: str,
    *,
    lithotype_id: str,
    rock_name: str,
    color: str,
) -> SupplierRockCodeProfile:
    dictionary = RockCodeDictionary(
        name=f"{supplier} profile",
        source="synthetic test profile",
        entries=(
            RockCodeEntry(
                source_code=7,
                lithotype_id=lithotype_id,
                code="7",
                name_ru=rock_name,
                name_kk=rock_name,
                name_en=rock_name,
                category="sedimentary",
                color=color,
                pattern_key=f"pattern_{lithotype_id}",
            ),
        ),
    )
    return SupplierRockCodeProfile(supplier, dictionary)


def _profiles() -> RockCodeProfileRegistry:
    return RockCodeProfileRegistry(
        (
            _profile(
                "Vendor A",
                lithotype_id="vendor_a_rock",
                rock_name="Rock A",
                color="#112233",
            ),
            _profile(
                "Vendor B",
                lithotype_id="vendor_b_rock",
                rock_name="Rock B",
                color="#445566",
            ),
        )
    )


def test_bind_source_profile_pins_normalized_supplier_and_exact_revision() -> None:
    profiles = _profiles()

    binding = bind_source_profile(_SOURCE_A, "  vEnDoR a  ", profiles)

    assert binding.source_sha256 == _SOURCE_A
    assert binding.supplier_name == "Vendor A"
    assert binding.profile_sha256 == rock_code_dictionary_sha256(
        profiles.require_dictionary("Vendor A")
    )


def test_same_raw_code_resolves_independently_by_source_binding() -> None:
    profiles = _profiles()
    bindings = RockCodeSourceBindingRegistry(
        (
            bind_source_profile(_SOURCE_A, "Vendor A", profiles),
            bind_source_profile(_SOURCE_B, "Vendor B", profiles),
        )
    )

    entry_a = bindings.require_dictionary(_SOURCE_A, profiles).entries[0]
    entry_b = bindings.require_dictionary(_SOURCE_B, profiles).entries[0]

    assert entry_a.source_code == entry_b.source_code == 7
    assert entry_a.lithotype_id == "vendor_a_rock"
    assert entry_b.lithotype_id == "vendor_b_rock"


def test_unknown_source_fails_closed_without_profile_guessing() -> None:
    profiles = _profiles()
    bindings = RockCodeSourceBindingRegistry(
        (bind_source_profile(_SOURCE_A, "Vendor A", profiles),)
    )

    with pytest.raises(RockCodeSourceBindingError, match="не назначен профиль"):
        bindings.require_dictionary(_SOURCE_B, profiles)


def test_duplicate_source_bindings_are_rejected_even_for_same_supplier() -> None:
    profiles = _profiles()
    first = bind_source_profile(_SOURCE_A, "Vendor A", profiles)
    second = bind_source_profile(_SOURCE_A, "Vendor A", profiles)

    with pytest.raises(RockCodeSourceBindingError, match="уже имеет профиль"):
        RockCodeSourceBindingRegistry((first, second))


def test_changed_supplier_profile_invalidates_existing_source_binding() -> None:
    initial_profiles = _profiles()
    binding = bind_source_profile(_SOURCE_A, "Vendor A", initial_profiles)
    bindings = RockCodeSourceBindingRegistry((binding,))
    changed_profiles = RockCodeProfileRegistry(
        (
            _profile(
                "Vendor A",
                lithotype_id="vendor_a_new_rock",
                rock_name="Rock A revised",
                color="#778899",
            ),
        )
    )

    with pytest.raises(RockCodeSourceBindingError, match="изменился после привязки"):
        bindings.require_dictionary(_SOURCE_A, changed_profiles)


def test_binding_requires_registered_supplier_and_lowercase_sha256() -> None:
    profiles = _profiles()

    with pytest.raises(RockCodeSourceBindingError, match="не зарегистрирован"):
        bind_source_profile(_SOURCE_A, "Unknown Vendor", profiles)

    with pytest.raises(RockCodeSourceBindingError, match="source_sha256"):
        bind_source_profile("A" * 64, "Vendor A", profiles)

    with pytest.raises(RockCodeSourceBindingError, match="profile_sha256"):
        SourceRockProfileBinding(_SOURCE_A, "Vendor A", "invalid")
