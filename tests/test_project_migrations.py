import pytest

from geoworkbench.storage.project_migrations import (
    ProjectMigrationError,
    ProjectMigrationRegistry,
    migrate_project_payload,
)


def test_default_registry_migrates_legacy_payload_through_every_version() -> None:
    legacy = {"project_id": "p", "name": "Project", "wells": {}}

    migrated = migrate_project_payload(legacy, 2)

    assert migrated == {
        "format_version": 2,
        "project": legacy,
        "tablet_layouts": {},
    }
    assert "format_version" not in legacy


def test_default_registry_migrates_v1_payload_to_v2() -> None:
    project = {"project_id": "p", "name": "Project", "wells": {}}

    migrated = migrate_project_payload({"format_version": 1, "project": project}, 2)

    assert migrated["project"] == project
    assert migrated["tablet_layouts"] == {}


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


@pytest.mark.parametrize("version", [3, "2", True, -1])
def test_registry_rejects_unsupported_or_invalid_version(version: object) -> None:
    with pytest.raises(ProjectMigrationError):
        migrate_project_payload({"format_version": version}, 2)  # type: ignore[dict-item]
