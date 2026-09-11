from __future__ import annotations

from dataclasses import FrozenInstanceError
from hashlib import sha256

import pytest

from geoworkbench.domain.rock_code_profiles import (
    RockCodeProfileRecord,
    RockCodeSourceBindingRecord,
)


_SOURCE_SHA = "a" * 64


def _profile(payload: str = '{"entries":[]}') -> RockCodeProfileRecord:
    return RockCodeProfileRecord(
        supplier_name="Vendor A",
        profile_json=payload,
        profile_sha256=sha256(payload.encode("utf-8")).hexdigest(),
    )


def test_profile_record_pins_exact_json_bytes_and_is_immutable() -> None:
    record = _profile()

    assert record.profile_sha256 == sha256(record.profile_json.encode("utf-8")).hexdigest()
    with pytest.raises(FrozenInstanceError):
        record.supplier_name = "Vendor B"  # type: ignore[misc]


def test_profile_record_rejects_payload_hash_mismatch() -> None:
    payload = '{"entries":[]}'

    with pytest.raises(ValueError, match="не соответствует profile_json"):
        RockCodeProfileRecord(
            supplier_name="Vendor A",
            profile_json=payload,
            profile_sha256="b" * 64,
        )


def test_profile_record_rejects_non_normalized_supplier_and_uppercase_hash() -> None:
    payload = '{"entries":[]}'
    digest = sha256(payload.encode("utf-8")).hexdigest()

    with pytest.raises(ValueError, match="Некорректное имя поставщика"):
        RockCodeProfileRecord(" Vendor A ", payload, digest)
    with pytest.raises(ValueError, match="profile_sha256"):
        RockCodeProfileRecord("Vendor A", payload, digest.upper())


def test_multiple_revisions_for_same_supplier_remain_distinct() -> None:
    first = _profile('{"revision":1}')
    second = _profile('{"revision":2}')

    assert first.supplier_name == second.supplier_name == "Vendor A"
    assert first.profile_sha256 != second.profile_sha256
    assert first != second


def test_source_binding_requires_normalized_supplier_and_lowercase_sha256() -> None:
    profile = _profile()
    binding = RockCodeSourceBindingRecord(
        source_sha256=_SOURCE_SHA,
        supplier_name=profile.supplier_name,
        profile_sha256=profile.profile_sha256,
    )

    assert binding.source_sha256 == _SOURCE_SHA
    assert binding.profile_sha256 == profile.profile_sha256

    with pytest.raises(ValueError, match="source_sha256"):
        RockCodeSourceBindingRecord("A" * 64, "Vendor A", profile.profile_sha256)
    with pytest.raises(ValueError, match="Некорректное имя поставщика"):
        RockCodeSourceBindingRecord(_SOURCE_SHA, " Vendor A", profile.profile_sha256)
