from __future__ import annotations

import json
from dataclasses import asdict
from hashlib import sha256

import pytest

from geoworkbench.domain.models import Project
from geoworkbench.domain.rock_code_profiles import (
    RockCodeProfileRecord,
    RockCodeSourceBindingRecord,
)
from geoworkbench.services.rock_code_dictionary import RockCodeDictionary, RockCodeEntry
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.package_project_repository import PackageProjectRepository
from geoworkbench.storage.project_codec import (
    PROJECT_FORMAT_VERSION,
    ProjectDocument,
    ProjectFormatError,
    load_project_document,
)


_SOURCE_SHA = "a" * 64


def _profile() -> RockCodeProfileRecord:
    dictionary = RockCodeDictionary(
        name="Vendor A profile",
        source="synthetic test profile",
        entries=(
            RockCodeEntry(
                source_code=7,
                lithotype_id="vendor_a_rock",
                code="7",
                name_ru="Порода A",
                name_kk="Порода A",
                name_en="Rock A",
                category="sedimentary",
                color="#112233",
                pattern_key="pattern_vendor_a_rock",
            ),
        ),
    )
    profile_json = dictionary.to_json()
    return RockCodeProfileRecord(
        supplier_name="Vendor A",
        profile_json=profile_json,
        profile_sha256=sha256(profile_json.encode("utf-8")).hexdigest(),
    )


def _document() -> ProjectDocument:
    profile = _profile()
    binding = RockCodeSourceBindingRecord(
        source_sha256=_SOURCE_SHA,
        supplier_name=profile.supplier_name,
        profile_sha256=profile.profile_sha256,
    )
    return ProjectDocument(
        project=Project("project-1", "Project"),
        rock_code_profiles={profile.profile_sha256: profile},
        rock_code_source_bindings={binding.source_sha256: binding},
    )


def test_v29_json_round_trip_preserves_profile_revision_and_binding(tmp_path) -> None:
    document = _document()
    target = tmp_path / "project.geolog.json"

    save_project(
        document.project,
        target,
        rock_code_profiles=document.rock_code_profiles,
        rock_code_source_bindings=document.rock_code_source_bindings,
    )
    loaded = load_project_document(target)

    assert PROJECT_FORMAT_VERSION == 35
    assert loaded.rock_code_profiles == document.rock_code_profiles
    assert loaded.rock_code_source_bindings == document.rock_code_source_bindings


def test_v28_payload_migrates_without_guessing_supplier_profile(tmp_path) -> None:
    document = _document()
    target = tmp_path / "legacy.geolog.json"
    save_project(
        document.project,
        target,
        rock_code_profiles=document.rock_code_profiles,
        rock_code_source_bindings=document.rock_code_source_bindings,
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["format_version"] = 28
    payload.pop("rock_code_profiles")
    payload.pop("rock_code_source_bindings")
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    loaded = load_project_document(target)

    assert loaded.rock_code_profiles == {}
    assert loaded.rock_code_source_bindings == {}


def test_v29_rejects_binding_to_missing_profile(tmp_path) -> None:
    document = _document()
    target = tmp_path / "malformed.geolog.json"
    save_project(
        document.project,
        target,
        rock_code_profiles=document.rock_code_profiles,
        rock_code_source_bindings=document.rock_code_source_bindings,
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    binding = payload["rock_code_source_bindings"][_SOURCE_SHA]
    binding["profile_sha256"] = "b" * 64
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ProjectFormatError, match="отсутствующий профиль"):
        load_project_document(target)


def test_v29_rejects_noncanonical_profile_json(tmp_path) -> None:
    document = _document()
    target = tmp_path / "noncanonical.geolog.json"
    save_project(
        document.project,
        target,
        rock_code_profiles=document.rock_code_profiles,
        rock_code_source_bindings=document.rock_code_source_bindings,
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    old_digest, raw_profile = next(iter(payload["rock_code_profiles"].items()))
    noncanonical_json = json.dumps(json.loads(raw_profile["profile_json"]), ensure_ascii=False)
    new_digest = sha256(noncanonical_json.encode("utf-8")).hexdigest()
    raw_profile["profile_json"] = noncanonical_json
    raw_profile["profile_sha256"] = new_digest
    payload["rock_code_profiles"] = {new_digest: raw_profile}
    raw_binding = payload["rock_code_source_bindings"][_SOURCE_SHA]
    raw_binding["profile_sha256"] = new_digest
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    assert old_digest != new_digest
    with pytest.raises(ProjectFormatError, match="канонический формат"):
        load_project_document(target)


def test_v29_package_round_trip_preserves_profile_provenance(tmp_path) -> None:
    document = _document()
    target = tmp_path / "project.geologpkg"
    repository = PackageProjectRepository()

    repository.save(document, target)
    loaded = repository.load(target)

    assert loaded.rock_code_profiles == document.rock_code_profiles
    assert loaded.rock_code_source_bindings == document.rock_code_source_bindings


def test_save_rejects_inconsistent_binding_before_writing(tmp_path) -> None:
    document = _document()
    target = tmp_path / "invalid.geolog.json"
    binding = next(iter(document.rock_code_source_bindings.values()))
    broken = RockCodeSourceBindingRecord(
        binding.source_sha256,
        binding.supplier_name,
        "b" * 64,
    )

    with pytest.raises(ValueError, match="отсутствующий профиль"):
        save_project(
            document.project,
            target,
            rock_code_profiles=document.rock_code_profiles,
            rock_code_source_bindings={broken.source_sha256: broken},
        )

    assert not target.exists()


def test_records_remain_plain_persistence_data() -> None:
    document = _document()

    profile = next(iter(document.rock_code_profiles.values()))
    binding = next(iter(document.rock_code_source_bindings.values()))
    assert set(asdict(profile)) == {"supplier_name", "profile_json", "profile_sha256"}
    assert set(asdict(binding)) == {"source_sha256", "supplier_name", "profile_sha256"}
