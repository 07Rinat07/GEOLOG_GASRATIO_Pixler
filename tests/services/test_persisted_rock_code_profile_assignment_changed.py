from __future__ import annotations

from geoworkbench.project.session import ProjectSession
from geoworkbench.services.persisted_rock_code_profile_assignment import (
    assign_persisted_rock_code_profile,
)
from geoworkbench.services.rock_code_dictionary import RockCodeDictionary, RockCodeEntry


SOURCE_SHA = "a" * 64


def _dictionary() -> RockCodeDictionary:
    return RockCodeDictionary(
        name="Changed-state test profile",
        source="synthetic test",
        entries=(
            RockCodeEntry(
                source_code=7,
                lithotype_id="las-code-7",
                code="7",
                name_ru="Песчаник",
                name_kk="Құмтас",
                name_en="Sandstone",
                category="sedimentary",
                color="#d2b48c",
                pattern_key="sandstone",
            ),
        ),
    )


def test_changed_is_true_when_assignment_mutates_persisted_ledgers() -> None:
    session = ProjectSession()

    result = assign_persisted_rock_code_profile(
        session,
        source_sha256=SOURCE_SHA,
        supplier_name="Vendor A",
        dictionary=_dictionary(),
    )

    assert result.profile_created
    assert result.binding_changed
    assert result.changed


def test_changed_is_false_for_idempotent_repeat() -> None:
    session = ProjectSession()
    dictionary = _dictionary()
    assign_persisted_rock_code_profile(
        session,
        source_sha256=SOURCE_SHA,
        supplier_name="Vendor A",
        dictionary=dictionary,
    )
    session.dirty = False

    result = assign_persisted_rock_code_profile(
        session,
        source_sha256=SOURCE_SHA,
        supplier_name="Vendor A",
        dictionary=dictionary,
    )

    assert not result.profile_created
    assert not result.binding_changed
    assert not result.changed
    assert session.dirty is False
