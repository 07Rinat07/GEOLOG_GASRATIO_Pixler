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
        "tablet_layouts": {},
        "source_artifacts": {},
        "import_reports": {},
    }

    migrated = migrate_project_payload(payload, 9)

    assert migrated["project"]["custom_formulas"] == {}


def test_v9_project_migrates_with_empty_tablet_presets() -> None:
    payload = {"format_version": 9, "project": {}}

    migrated = migrate_project_payload(payload, 10)

    assert migrated["format_version"] == 10
    assert migrated["tablet_presets"] == {}
    assert "tablet_presets" not in payload


def test_v10_project_migrates_with_empty_export_profiles() -> None:
    payload = {"format_version": 10, "project": {}}

    migrated = migrate_project_payload(payload, 11)

    assert migrated["format_version"] == 11
    assert migrated["project"]["export_profiles"] == {}
    assert "export_profiles" not in payload["project"]


def test_v12_project_adds_kazakh_lithotype_name_without_mutating_source() -> None:
    payload = {
        "format_version": 12,
        "project": {"lithotypes": {"custom": {"name_ru": "Порода"}}},
    }

    migrated = migrate_project_payload(payload, 13)

    assert migrated["format_version"] == 13
    assert migrated["project"]["lithotypes"]["custom"]["name_kk"] == "Порода"
    assert "name_kk" not in payload["project"]["lithotypes"]["custom"]


def test_v13_project_migrates_with_empty_time_depth_mapping_profiles() -> None:
    payload = {"format_version": 13, "project": {}}

    migrated = migrate_project_payload(payload, 14)

    assert migrated["format_version"] == 14
    assert migrated["project"]["time_depth_mapping_profiles"] == {}
    assert "time_depth_mapping_profiles" not in payload["project"]


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


def test_v14_project_adds_empty_interpretations_to_every_well() -> None:
    payload = {
        "format_version": 14,
        "project": {"wells": {"well-1": {"well_id": "well-1", "name": "Well 1", "datasets": {}}}},
    }

    migrated = migrate_project_payload(payload, 15)

    assert migrated["format_version"] == 15
    assert migrated["project"]["wells"]["well-1"]["interpretations"] == {}
    assert "interpretations" not in payload["project"]["wells"]["well-1"]


def test_v15_project_advances_to_semantic_channel_format_without_mutating_curves() -> None:
    payload = {
        "format_version": 15,
        "project": {
            "project_id": "p",
            "name": "P",
            "wells": {},
        },
    }

    migrated = migrate_project_payload(payload, 16)

    assert migrated["format_version"] == 16
    assert migrated["project"] == payload["project"]
    assert payload["format_version"] == 15


def test_v16_project_adds_empty_operational_events_to_every_well() -> None:
    payload = {
        "format_version": 16,
        "project": {
            "project_id": "p",
            "name": "P",
            "wells": {
                "well-1": {"well_id": "well-1", "name": "Well 1", "datasets": {}}
            },
        },
    }

    migrated = migrate_project_payload(payload, 17)

    assert migrated["format_version"] == 17
    assert migrated["project"]["wells"]["well-1"]["operational_events"] == {}
    assert "operational_events" not in payload["project"]["wells"]["well-1"]


def test_v17_project_adds_empty_acquisition_sessions_to_every_well() -> None:
    payload = {
        "format_version": 17,
        "project": {
            "project_id": "p",
            "name": "P",
            "wells": {
                "well-1": {
                    "well_id": "well-1",
                    "name": "Well 1",
                    "datasets": {},
                    "operational_events": {},
                }
            },
        },
    }

    migrated = migrate_project_payload(payload, 18)

    assert migrated["format_version"] == 18
    assert migrated["project"]["wells"]["well-1"]["acquisition_sessions"] == {}
    assert "acquisition_sessions" not in payload["project"]["wells"]["well-1"]


def test_v18_project_adds_empty_lag_correction_profiles_to_every_well() -> None:
    payload = {
        "format_version": 18,
        "project": {
            "project_id": "p",
            "name": "P",
            "wells": {
                "well-1": {
                    "well_id": "well-1",
                    "name": "Well 1",
                    "datasets": {},
                    "operational_events": {},
                    "acquisition_sessions": {},
                }
            },
        },
    }

    migrated = migrate_project_payload(payload, 19)

    assert migrated["format_version"] == 19
    assert migrated["project"]["wells"]["well-1"]["lag_correction_profiles"] == {}
    assert "lag_correction_profiles" not in payload["project"]["wells"]["well-1"]


def test_v19_project_adds_independent_dataset_append_histories() -> None:
    payload = {
        "format_version": 19,
        "project": {
            "project_id": "p",
            "name": "P",
            "wells": {
                "w": {
                    "well_id": "w",
                    "name": "W",
                    "datasets": {
                        "depth-a": {"dataset_id": "depth-a"},
                        "time-a": {"dataset_id": "time-a"},
                    },
                }
            },
        },
    }

    migrated = migrate_project_payload(payload, 20)

    assert migrated["format_version"] == 20
    assert migrated["project"]["wells"]["w"]["datasets"]["depth-a"]["append_history"] == []
    assert migrated["project"]["wells"]["w"]["datasets"]["time-a"]["append_history"] == []
    assert "append_history" not in payload["project"]["wells"]["w"]["datasets"]["depth-a"]
