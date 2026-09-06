from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json
import shutil

import pytest

from geoworkbench.domain.models import MasterlogTemplate, Project, Well
from geoworkbench.domain.well_passport import (
    DATE_FIELDS,
    LOCALIZED_FIELDS,
    NUMERIC_FIELDS,
    SHARED_TEXT_FIELDS,
    PassportValidationError,
    WellPassport,
    validate_passport,
)
from geoworkbench.printing.image_assets import ImageAsset, SVG_MEDIA_TYPE
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.package_project_repository import PackageProjectRepository
from geoworkbench.storage.project_codec import (
    PROJECT_FORMAT_VERSION,
    ProjectDocument,
    ProjectFormatError,
    load_project_document,
    project_document_from_dict,
)
from geoworkbench.storage.project_migrations import migrate_project_payload


def _passport() -> WellPassport:
    return WellPassport(
        values={
            "header.well_number": "TEST-101",
            "header.actual_depth": 1030.5,
            "header.project_depth": 1500.0,
            "header.wellhead_altitude": -15.129,
            "header.latitude": 46.435,
            "header.longitude": 53.59,
            "header.start_date": "2026-09-05",
            "header.end_date": "",
            "header.casing_0_diameter": 177.8,
            "header.casing_0_depth": 1030.5,
        },
        texts_i18n={
            "header.casing_0_name": {"ru": "Колонна", "kk": "Бағана", "en": "Casing"},
            "header.country": {"ru": "Казахстан", "kk": "Қазақстан", "en": "Kazakhstan"},
            "header.well_construction": {
                "ru": "Кондуктор 473 мм",
                "kk": "Кондуктор 473 мм",
                "en": "Surface casing 473 mm",
            },
        },
        logo_refs={"customer": ""},
    )


def _document() -> ProjectDocument:
    first = Well("well-1", "TEST-101", passport=_passport())
    second = Well("well-2", "TEST-102")
    templates = {
        name: MasterlogTemplate(
            name,
            name,
            properties={"header_fields": {"header.actual_depth": depth}},
        )
        for name, depth in (("portrait", "1100 м"), ("landscape", "1150 м"))
    }
    return ProjectDocument(
        Project(
            "project",
            "Test",
            wells={first.well_id: first, second.well_id: second},
            masterlog_templates=templates,
        )
    )


def test_passport_validator_returns_independent_normalized_copy() -> None:
    passport = _passport()
    passport.values["header.rig"] = "  Rig-4  "
    passport.texts_i18n["header.notes"] = {"und": " legacy text "}
    before = deepcopy(passport)

    normalized = validate_passport(passport)

    assert normalized.values["header.rig"] == "Rig-4"
    assert normalized.texts_i18n["header.notes"] == {"und": "legacy text"}
    normalized.texts_i18n["header.notes"]["en"] = "Note"
    assert passport == before


def test_passport_schema_excludes_print_specific_fields() -> None:
    fields = DATE_FIELDS | LOCALIZED_FIELDS | NUMERIC_FIELDS | SHARED_TEXT_FIELDS
    assert not fields & {
        "header.interval",
        "header.interval_start",
        "header.interval_end",
        "header.scale",
    }


def test_passport_rejects_end_date_before_start_date() -> None:
    with pytest.raises(PassportValidationError) as caught:
        validate_passport(
            WellPassport(
                values={"header.start_date": "2026-09-05", "header.end_date": "2026-09-04"}
            )
        )
    assert caught.value.field_name == "header.end_date"


def test_passport_allows_actual_depth_beyond_plan_and_same_day_dates() -> None:
    passport = WellPassport(
        values={
            "header.start_date": "2026-09-05",
            "header.end_date": "2026-09-05",
            "header.actual_depth": 1501.0,
            "header.project_depth": 1500.0,
        }
    )
    assert validate_passport(passport) == passport


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("header.actual_depth", True),
        ("header.actual_depth", -1),
        ("header.project_depth", "1500"),
        ("header.rig_floor", float("nan")),
        ("header.wellhead_altitude", float("inf")),
        ("header.latitude", 90.01),
        ("header.longitude", -180.01),
        ("header.start_date", "05.09.2026"),
        ("header.start_date", "2026-02-30"),
        ("header.start_date", 20260905),
        ("header.rig", []),
        ("header.scale", "1:500"),
        ("header.casing_0_diameter", 0),
        ("header.casing_0_diameter", -1),
        ("header.casing_0_depth", -1),
        ("header.casing_0_depth", float("inf")),
    ],
)
def test_passport_rejects_invalid_field_with_predictable_error(field_name, value) -> None:
    with pytest.raises(PassportValidationError) as caught:
        validate_passport(WellPassport(values={field_name: value}))
    assert caught.value.field_name == field_name


@pytest.mark.parametrize("translations", [{"de": "Text"}, {"en": 3}, None, {"ru": "x" * 20_001}])
def test_passport_rejects_invalid_translations(translations) -> None:
    with pytest.raises(PassportValidationError) as caught:
        validate_passport(WellPassport(texts_i18n={"header.notes": translations}))
    assert caught.value.field_name == "header.notes"


@pytest.mark.parametrize("refs", [{"other": ""}, {"customer": "../../logo.png"}, {"contractor": 1}])
def test_passport_rejects_invalid_logo_reference(refs) -> None:
    with pytest.raises(PassportValidationError):
        validate_passport(WellPassport(logo_refs=refs))


def test_v24_migration_preserves_conflicting_headers_and_source_payload() -> None:
    project = asdict(_document().project)
    for well in project["wells"].values():
        well.pop("passport")
    raw = {"format_version": 24, "project": project, "tablet_layouts": {}, "tablet_presets": {}}
    original = deepcopy(raw)

    migrated = migrate_project_payload(raw, PROJECT_FORMAT_VERSION)
    restored = project_document_from_dict(migrated)

    assert migrated["format_version"] == 25
    assert raw == original
    assert migrated["project"]["masterlog_templates"] == project["masterlog_templates"]
    assert all(well.passport is None for well in restored.project.wells.values())
    assert set(restored.project.wells) == {"well-1", "well-2"}


@pytest.mark.parametrize(
    "raw_passport", [[], 0, {"extra": {}}, {"values": None}, {"values": {"header.latitude": 91}}]
)
def test_codec_rejects_invalid_passport(raw_passport) -> None:
    project = asdict(_document().project)
    project["wells"]["well-1"]["passport"] = raw_passport
    with pytest.raises(ProjectFormatError, match="паспорт"):
        project_document_from_dict(
            {"format_version": PROJECT_FORMAT_VERSION, "project": project, "tablet_layouts": {}}
        )


def test_passport_json_and_package_transfer_recovery_preserve_values_and_assets(tmp_path) -> None:
    document = _document()
    payload = b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10"><rect width="20" height="10"/></svg>'
    asset = ImageAsset(f"sha256:{sha256(payload).hexdigest()}", "logo.svg", SVG_MEDIA_TYPE, payload)
    document.image_assets[asset.asset_id] = asset
    document.project.wells["well-1"].passport.logo_refs["contractor"] = asset.asset_id
    original = deepcopy(document.project)
    json_path = tmp_path / "test.geolog.json"
    save_project(document.project, json_path, image_assets=document.image_assets)
    json_loaded = load_project_document(json_path)
    assert json_loaded.project == original
    assert json_loaded.image_assets == document.image_assets

    package = tmp_path / "test.geologpkg"
    repository = PackageProjectRepository()
    repository.save(document, package)
    transferred = tmp_path / "transferred.geologpkg"
    shutil.copy2(package, transferred)
    transferred.replace(repository.pending_path(transferred))

    restored = repository.load(transferred)

    assert transferred.is_file()
    assert not repository.pending_path(transferred).exists()
    assert restored.project == original
    assert restored.image_assets == document.image_assets
    assert document.project == original


def test_missing_passport_asset_cannot_replace_existing_saved_project(tmp_path) -> None:
    document = _document()
    path = tmp_path / "test.geolog.json"
    save_project(document.project, path)
    before = path.read_bytes()
    document.project.wells["well-1"].passport.logo_refs["contractor"] = "sha256:" + "0" * 64

    with pytest.raises(ValueError, match="отсутствующие image assets"):
        save_project(document.project, path)

    assert path.read_bytes() == before


def test_loader_rejects_missing_passport_asset(tmp_path) -> None:
    path = tmp_path / "test.geolog.json"
    save_project(_document().project, path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["project"]["wells"]["well-1"]["passport"]["logo_refs"]["contractor"] = "sha256:" + "0" * 64
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ProjectFormatError, match="отсутствующие image assets"):
        load_project_document(path)


def test_v24_construction_migration_preserves_all_source_texts_geometry_and_ids() -> None:
    from geoworkbench.printing.masterlog_header_forms import masterlog_header_elements
    from geoworkbench.printing.masterlog_renderer import _header_text
    from geoworkbench.project.session import ProjectSession
    from geoworkbench.project.well_passport_controller import WellPassportController
    from geoworkbench.services.localization import AppLanguage

    project = _document().project
    template = project.masterlog_templates["portrait"]
    template.header_elements = list(masterlog_header_elements("portrait"))
    original_elements = {}
    for element in template.header_elements:
        if element.element_id.startswith("casing_"):
            element.element_type = "text"
            element.properties.pop("field")
            original_elements[element.element_id] = deepcopy(element)
    raw = {
        "format_version": 24,
        "project": asdict(project),
        "tablet_layouts": {},
        "tablet_presets": {},
    }
    for well in raw["project"]["wells"].values():
        well.pop("passport")
    before = deepcopy(raw)
    restored = project_document_from_dict(raw)
    session = ProjectSession(project=restored.project, current_well_id="well-1")
    migrated = session.project.masterlog_templates["portrait"]
    for element in migrated.header_elements:
        if element.element_id not in original_elements:
            continue
        original = original_elements[element.element_id]
        assert element.element_type == "field"
        assert element.x_mm == original.x_mm
        assert element.height_mm == original.height_mm
        assert {k: v for k, v in element.properties.items() if k != "field"} == original.properties
        for language in AppLanguage:
            assert (
                _header_text(element, session, migrated, language)
                == original.properties["text_" + language.value]
            )
    assert raw == before
    WellPassportController(session).save(WellPassport(values={"header.casing_0_depth": 123.45}))
    depth = next(e for e in migrated.header_elements if e.element_id == "casing_0_depth")
    assert _header_text(depth, session, migrated, AppLanguage.EN) == "123.45 m"


@pytest.mark.parametrize(
    "templates",
    [
        None,
        [],
        {"t": None},
        {"t": {"header_elements": None}},
        {"t": {"header_elements": [None]}},
        {"t": {"header_elements": [{"properties": None}]}},
    ],
)
def test_v24_migration_rejects_malformed_header_structure(templates) -> None:
    from geoworkbench.storage.project_migrations import ProjectMigrationError

    raw = {"format_version": 24, "project": {"wells": {}, "masterlog_templates": templates}}
    with pytest.raises(ProjectMigrationError):
        migrate_project_payload(raw, PROJECT_FORMAT_VERSION)
