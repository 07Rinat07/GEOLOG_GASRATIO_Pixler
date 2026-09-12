from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace

import pytest

from geoworkbench.domain.rock_code_profiles import (
    RockCodeProfileRecord,
    RockCodeSourceBindingRecord,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.daily_las_growth import DailyLasGrowthError
from geoworkbench.services.persisted_well_geology_update import (
    analyze_persisted_well_geology_update,
    prepare_persisted_well_geology_update,
)
from geoworkbench.services.rock_code_dictionary import (
    RockCodeDictionary,
    RockCodeEntry,
)
from geoworkbench.services.rock_code_source_binding import RockCodeSourceBindingError


_SOURCE_A = "a" * 64
_SOURCE_B = "b" * 64


def _dictionary(name: str, rock_name: str) -> RockCodeDictionary:
    return RockCodeDictionary(
        name=name,
        source="tests",
        entries=(
            RockCodeEntry(
                source_code=7,
                lithotype_id=rock_name.casefold(),
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


def _record(supplier: str, dictionary: RockCodeDictionary) -> RockCodeProfileRecord:
    payload = dictionary.to_json()
    return RockCodeProfileRecord(
        supplier_name=supplier,
        profile_json=payload,
        profile_sha256=sha256(payload.encode("utf-8")).hexdigest(),
    )


def _session_with_two_revisions() -> tuple[ProjectSession, RockCodeProfileRecord, RockCodeProfileRecord]:
    first = _record("Vendor A", _dictionary("Vendor A r1", "Sandstone"))
    second = _record("Vendor A", _dictionary("Vendor A r2", "Shale"))
    session = ProjectSession()
    session.rock_code_profiles = {
        first.profile_sha256: first,
        second.profile_sha256: second,
    }
    session.rock_code_source_bindings = {
        _SOURCE_A: RockCodeSourceBindingRecord(_SOURCE_A, "Vendor A", first.profile_sha256),
        _SOURCE_B: RockCodeSourceBindingRecord(_SOURCE_B, "Vendor A", second.profile_sha256),
    }
    return session, first, second


def test_analysis_uses_exact_persisted_revision_for_source(monkeypatch: pytest.MonkeyPatch) -> None:
    session, first, second = _session_with_two_revisions()
    captured: list[str] = []

    def fake_analyze(session_arg, target, source, dictionary, *, source_name, source_sha256):
        del session_arg, target, source, source_name
        captured.append(dictionary.entries[0].name_en)
        payload = dictionary.to_json()
        return SimpleNamespace(
            source_sha256=source_sha256,
            profile_json=payload,
            profile_sha256=sha256(payload.encode("utf-8")).hexdigest(),
        )

    monkeypatch.setattr(
        "geoworkbench.services.persisted_well_geology_update.analyze_well_geology_update",
        fake_analyze,
    )

    first_plan = analyze_persisted_well_geology_update(
        session, object(), object(), source_name="first.las", source_sha256=_SOURCE_A
    )
    second_plan = analyze_persisted_well_geology_update(
        session, object(), object(), source_name="second.las", source_sha256=_SOURCE_B
    )

    assert captured == ["Sandstone", "Shale"]
    assert first_plan.profile_sha256 == first.profile_sha256
    assert second_plan.profile_sha256 == second.profile_sha256


def test_analysis_fails_closed_when_source_has_no_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    session, _, _ = _session_with_two_revisions()
    called = False

    def fake_analyze(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("low-level analyzer must not run")

    monkeypatch.setattr(
        "geoworkbench.services.persisted_well_geology_update.analyze_well_geology_update",
        fake_analyze,
    )

    with pytest.raises(RockCodeSourceBindingError, match="не сохранена привязка"):
        analyze_persisted_well_geology_update(
            session, object(), object(), source_name="unknown.las", source_sha256="c" * 64
        )
    assert called is False


def test_prepare_rejects_binding_changed_after_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    session, first, second = _session_with_two_revisions()
    plan = SimpleNamespace(profile_sha256=first.profile_sha256)
    session.rock_code_source_bindings[_SOURCE_A] = replace(
        session.rock_code_source_bindings[_SOURCE_A],
        profile_sha256=second.profile_sha256,
    )
    called = False

    def fake_prepare(*args, **kwargs):
        nonlocal called
        called = True
        return object()

    monkeypatch.setattr(
        "geoworkbench.services.persisted_well_geology_update.prepare_well_geology_update",
        fake_prepare,
    )

    with pytest.raises(DailyLasGrowthError, match="Привязка источника.*изменилась"):
        prepare_persisted_well_geology_update(
            session,
            object(),
            object(),
            plan,
            source_name="daily.las",
            source_sha256=_SOURCE_A,
            append_rows=False,
        )
    assert called is False


def test_prepare_revalidates_binding_then_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    session, first, _ = _session_with_two_revisions()
    plan = SimpleNamespace(profile_sha256=first.profile_sha256)
    sentinel = object()
    captured: dict[str, object] = {}

    def fake_prepare(session_arg, target, source, plan_arg, *, source_name, source_sha256, append_rows):
        captured.update(
            session=session_arg,
            target=target,
            source=source,
            plan=plan_arg,
            source_name=source_name,
            source_sha256=source_sha256,
            append_rows=append_rows,
        )
        return sentinel

    monkeypatch.setattr(
        "geoworkbench.services.persisted_well_geology_update.prepare_well_geology_update",
        fake_prepare,
    )
    target = object()
    source = object()

    result = prepare_persisted_well_geology_update(
        session,
        target,
        source,
        plan,
        source_name="daily.las",
        source_sha256=_SOURCE_A,
        append_rows=True,
    )

    assert result is sentinel
    assert captured == {
        "session": session,
        "target": target,
        "source": source,
        "plan": plan,
        "source_name": "daily.las",
        "source_sha256": _SOURCE_A,
        "append_rows": True,
    }
