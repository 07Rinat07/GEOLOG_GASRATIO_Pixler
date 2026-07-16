import pytest

from geoworkbench.storage.project_migrations import (
    ProjectMigrationError,
    ProjectMigrationRegistry,
    migrate_project_payload,
)


def test_default_registry_migrates_legacy_payload_through_every_version() -> None:
    legacy = {"project_id": "p", "name": "Project", "wells": {}}

    migrated = migrate_project_payload(legacy, 4)

    assert migrated == {
        "format_version": 4,
        "project": {**legacy, "lithotypes": {}, "description_templates": {}},
        "tablet_layouts": {},
    }
    assert "format_version" not in legacy


def test_default_registry_migrates_v1_payload_to_v2() -> None:
    project = {"project_id": "p", "name": "Project", "wells": {}}

    migrated = migrate_project_payload({"format_version": 1, "project": project}, 4)

    assert migrated["project"] == {
        **project,
        "lithotypes": {},
        "description_templates": {},
    }
    assert migrated["tablet_layouts"] == {}


def test_v7_project_migrates_with_empty_masterlog_templates() -> None:
    payload = {
        "format_version": 7,
        "project": {"project_id": "p", "name": "Project", "wells": {}},
        "tablet_layouts": {},
        "source_artifacts": {},
        "import_reports": {},
    }

    migrated = migrate_project_payload(payload, 8)

    assert migrated["format_version"] == 8
    assert migrated["project"]["masterlog_templates"] == {}
    assert "masterlog_templates" not in payload["project"]


def test_v8_project_migrates_with_empty_custom_formulas() -> None:
    payload = {
        "format_version": 8,
        "project": {"project_id": "p", "name": "Project", "wells": {}},
        "tablet_layouts": {}, "source_artifacts": {}, "import_reports": {},
    }

    migrated = migrate_project_payload(payload, 9)

    assert migrated["project"]["custom_formulas"] == {}


def test_v9_project_migrates_with_empty_tablet_presets() -> None:
    payload = {"format_version": 9, "project": {}}

    migrated = migrate_project_payload(payload, 10)

    assert migrated["format_version"] == 10
    assert migrated["tablet_presets"] == {}
    assert "tablet_presets" not in payload


def test_registry_rejects_missing_migration_step() -> None:
    registry = ProjectMigrationRegistry()

    with pytest.raises(ProjectMigrationError, match="0 → 1"):
        registry.migrate({"project_id": "p"}, 1)


def test_registry_rejects_migration_that_skips_version() -> None:
    registry = ProjectMigrationRegistry()
    registry.register(0, lambda payload: {"format_version": 2})

    with pytest.raises(ProjectMigrationError, match="создать версию 1"):
        registry.migrate({}, 2)


def test_registry_rejects_duplicate_source_version() -> None:
    registry = ProjectMigrationRegistry()
    registry.register(0, lambda payload: {"format_version": 1})

    with pytest.raises(ValueError, match="уже зарегистрирована"):
        registry.register(0, lambda payload: {"format_version": 1})


@pytest.mark.parametrize("version", [5, "2", True, -1])
def test_registry_rejects_unsupported_or_invalid_version(version: object) -> None:
    with pytest.raises(ProjectMigrationError):
        migrate_project_payload({"format_version": version}, 4)  # type: ignore[dict-item]
