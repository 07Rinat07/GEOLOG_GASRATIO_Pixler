from hashlib import sha256

import pytest

from geoworkbench.services.rock_code_dictionary import RockCodeDictionary, RockCodeEntry
from geoworkbench.services.rock_code_profile_registry import (
    RockCodeProfileRegistry,
    RockCodeProfileRegistryError,
    SupplierRockCodeProfile,
)


def _dictionary(*, name: str, lithotype_id: str, rock_name: str, color: str) -> RockCodeDictionary:
    return RockCodeDictionary(
        name=name,
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


def _profile(supplier: str, *, lithotype_id: str, rock_name: str, color: str) -> SupplierRockCodeProfile:
    return SupplierRockCodeProfile(
        supplier_name=supplier,
        dictionary=_dictionary(
            name=f"{supplier} profile",
            lithotype_id=lithotype_id,
            rock_name=rock_name,
            color=color,
        ),
    )


def test_same_raw_code_remains_independent_between_suppliers() -> None:
    vendor_a = _profile(
        "Vendor A", lithotype_id="vendor_a_rock", rock_name="Rock A", color="#112233"
    )
    vendor_b = _profile(
        "Vendor B", lithotype_id="vendor_b_rock", rock_name="Rock B", color="#445566"
    )
    registry = RockCodeProfileRegistry((vendor_a, vendor_b))

    entry_a = registry.require_dictionary("Vendor A").entries[0]
    entry_b = registry.require_dictionary("Vendor B").entries[0]

    assert entry_a.source_code == entry_b.source_code == 7
    assert entry_a.lithotype_id != entry_b.lithotype_id
    assert entry_a.name_ru != entry_b.name_ru

    hash_a = sha256(registry.require_dictionary("Vendor A").to_json().encode("utf-8")).hexdigest()
    hash_b = sha256(registry.require_dictionary("Vendor B").to_json().encode("utf-8")).hexdigest()
    assert hash_a != hash_b


def test_supplier_lookup_is_trimmed_and_case_insensitive() -> None:
    profile = _profile(
        "Vendor A", lithotype_id="vendor_a_rock", rock_name="Rock A", color="#112233"
    )
    registry = RockCodeProfileRegistry((profile,))

    assert registry.require("  vEnDoR a  ") is profile
    assert registry.suppliers == ("Vendor A",)


def test_unknown_supplier_fails_closed_without_default_profile() -> None:
    profile = _profile(
        "Vendor A", lithotype_id="vendor_a_rock", rock_name="Rock A", color="#112233"
    )
    registry = RockCodeProfileRegistry((profile,))

    with pytest.raises(RockCodeProfileRegistryError, match="не зарегистрирован"):
        registry.require_dictionary("Vendor B")


def test_blank_supplier_name_is_rejected() -> None:
    dictionary = _dictionary(
        name="Synthetic profile",
        lithotype_id="vendor_a_rock",
        rock_name="Rock A",
        color="#112233",
    )

    with pytest.raises(RockCodeProfileRegistryError, match="Некорректное имя поставщика"):
        SupplierRockCodeProfile("   ", dictionary)

    with pytest.raises(RockCodeProfileRegistryError, match="Некорректное имя поставщика"):
        RockCodeProfileRegistry().require("   ")


def test_duplicate_supplier_names_after_normalization_are_rejected() -> None:
    first = _profile(
        "Vendor A", lithotype_id="vendor_a_rock", rock_name="Rock A", color="#112233"
    )
    second = _profile(
        " vendor a ", lithotype_id="vendor_b_rock", rock_name="Rock B", color="#445566"
    )

    with pytest.raises(RockCodeProfileRegistryError, match="уже зарегистрирован"):
        RockCodeProfileRegistry((first, second))
