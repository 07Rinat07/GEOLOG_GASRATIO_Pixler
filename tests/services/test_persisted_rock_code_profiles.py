from __future__ import annotations

import json
from hashlib import sha256

import pytest

from geoworkbench.domain.rock_code_profiles import (
    RockCodeProfileRecord,
    RockCodeSourceBindingRecord,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.persisted_rock_code_profiles import (
    PersistedRockCodeProfileResolver,
)
from geoworkbench.services.rock_code_dictionary import (
    RockCodeDictionary,
    RockCodeEntry,
)
from geoworkbench.services.rock_code_source_binding import RockCodeSourceBindingError


_SOURCE_A = "a" * 64
_SOURCE_B = "b" * 64


def _dictionary(*, name: str, lithotype_id: str, rock_name: str) -> RockCodeDictionary:
    return RockCodeDictionary(
        name=name,
        source="tests",
        entries=(
            RockCodeEntry(
                source_code=7,
                lithotype_id=lithotype_id,
                code="7",
                name_ru=rock_name,
                name_kk=rock_name,
                name_en=rock_name,
                category="sedimentary",
                color="#AABBCC",
                pattern_key="solid",
            ),
        ),
    )


def _profile(supplier_name: str, dictionary: RockCodeDictionary) -> RockCodeProfileRecord:
    payload = dictionary.to_json()
    return RockCodeProfileRecord(
        supplier_name=supplier_name,
        profile_json=payload,
        profile_sha256=sha256(payload.encode("utf-8")).hexdigest(),
    )


def test_same_supplier_can_keep_multiple_pinned_revisions() -> None:
    first = _profile(
        "Vendor A",
        _dictionary(name="Vendor A r1", lithotype_id="sandstone", rock_name="Sandstone"),
    )
    second = _profile(
        "Vendor A",
        _dictionary(name="Vendor A r2", lithotype_id="shale", rock_name="Shale"),
    )
    session = ProjectSession()
    session.rock_code_profiles = {
        first.profile_sha256: first,
        second.profile_sha256: second,
    }
    session.rock_code_source_bindings = {
        _SOURCE_A: RockCodeSourceBindingRecord(
            _SOURCE_A, first.supplier_name, first.profile_sha256
        ),
        _SOURCE_B: RockCodeSourceBindingRecord(
            _SOURCE_B, second.supplier_name, second.profile_sha256
        ),
    }

    resolver = PersistedRockCodeProfileResolver.from_session(session)

    first_dictionary = resolver.require_dictionary(_SOURCE_A)
    second_dictionary = resolver.require_dictionary(_SOURCE_B)
    assert first_dictionary.entries[0].lithotype_id == "sandstone"
    assert second_dictionary.entries[0].lithotype_id == "shale"
    assert first_dictionary.entries[0].source_code == second_dictionary.entries[0].source_code == 7


def test_unknown_source_fails_without_supplier_fallback() -> None:
    resolver = PersistedRockCodeProfileResolver({}, {})

    with pytest.raises(RockCodeSourceBindingError, match="не сохранена привязка"):
        resolver.require_dictionary(_SOURCE_A)


def test_profile_ledger_key_must_match_exact_revision_sha() -> None:
    profile = _profile(
        "Vendor A",
        _dictionary(name="Vendor A", lithotype_id="sandstone", rock_name="Sandstone"),
    )

    with pytest.raises(RockCodeSourceBindingError, match="Ключ persisted profile"):
        PersistedRockCodeProfileResolver({_SOURCE_A: profile}, {})


def test_binding_must_reference_existing_revision() -> None:
    missing_profile_sha = "c" * 64
    binding = RockCodeSourceBindingRecord(_SOURCE_A, "Vendor A", missing_profile_sha)

    with pytest.raises(RockCodeSourceBindingError, match="отсутствующую ревизию"):
        PersistedRockCodeProfileResolver({}, {_SOURCE_A: binding})


def test_binding_supplier_must_match_persisted_revision() -> None:
    profile = _profile(
        "Vendor A",
        _dictionary(name="Vendor A", lithotype_id="sandstone", rock_name="Sandstone"),
    )
    binding = RockCodeSourceBindingRecord(_SOURCE_A, "Vendor B", profile.profile_sha256)

    with pytest.raises(RockCodeSourceBindingError, match="Поставщик persisted binding"):
        PersistedRockCodeProfileResolver(
            {profile.profile_sha256: profile},
            {_SOURCE_A: binding},
        )


def test_noncanonical_profile_json_is_rejected_even_with_matching_hash() -> None:
    dictionary = _dictionary(
        name="Vendor A",
        lithotype_id="sandstone",
        rock_name="Sandstone",
    )
    compact_json = json.dumps(dictionary.to_dict(), ensure_ascii=False, separators=(",", ":"))
    profile = RockCodeProfileRecord(
        supplier_name="Vendor A",
        profile_json=compact_json,
        profile_sha256=sha256(compact_json.encode("utf-8")).hexdigest(),
    )

    with pytest.raises(RockCodeSourceBindingError, match="канонический формат"):
        PersistedRockCodeProfileResolver({profile.profile_sha256: profile}, {})
