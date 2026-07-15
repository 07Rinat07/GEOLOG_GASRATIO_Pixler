from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable


ProjectPayload = dict[str, Any]
ProjectMigration = Callable[[ProjectPayload], ProjectPayload]


class ProjectMigrationError(ValueError):
    """Raised when a project payload cannot be migrated safely."""


@dataclass(slots=True)
class ProjectMigrationRegistry:
    """Ordered registry where every migration advances exactly one format version."""

    migrations: dict[int, ProjectMigration] = field(default_factory=dict)

    def register(self, source_version: int, migration: ProjectMigration) -> None:
        if source_version < 0:
            raise ValueError("Версия-источник миграции не может быть отрицательной")
        if source_version in self.migrations:
            raise ValueError(f"Миграция из версии {source_version} уже зарегистрирована")
        self.migrations[source_version] = migration

    def migrate(self, payload: ProjectPayload, target_version: int) -> ProjectPayload:
        current = deepcopy(payload)
        source_version = self._read_version(current)
        if source_version > target_version:
            raise ProjectMigrationError(
                f"Версия проекта {source_version} новее поддерживаемой {target_version}"
            )

        while source_version < target_version:
            migration = self.migrations.get(source_version)
            if migration is None:
                raise ProjectMigrationError(
                    f"Не найдена миграция проекта {source_version} → {source_version + 1}"
                )
            current = migration(current)
            migrated_version = self._read_version(current)
            expected_version = source_version + 1
            if migrated_version != expected_version:
                raise ProjectMigrationError(
                    f"Миграция {source_version} должна создать версию {expected_version}"
                )
            source_version = migrated_version
        return current

    @staticmethod
    def _read_version(payload: ProjectPayload) -> int:
        if "format_version" not in payload:
            return 0
        version = payload["format_version"]
        if not isinstance(version, int) or isinstance(version, bool) or version < 0:
            raise ProjectMigrationError("Версия формата проекта должна быть целым числом")
        return version


def _migrate_legacy_to_v1(payload: ProjectPayload) -> ProjectPayload:
    legacy_project = dict(payload)
    legacy_project.pop("format_version", None)
    return {
        "format_version": 1,
        "project": legacy_project,
    }


def _migrate_v1_to_v2(payload: ProjectPayload) -> ProjectPayload:
    project = payload.get("project")
    if not isinstance(project, dict):
        raise ProjectMigrationError("Проект версии 1 не содержит объекта 'project'")
    return {
        "format_version": 2,
        "project": project,
        "tablet_layouts": {},
    }


def _migrate_v2_to_v3(payload: ProjectPayload) -> ProjectPayload:
    migrated = deepcopy(payload)
    project = migrated.get("project")
    if not isinstance(project, dict):
        raise ProjectMigrationError("Проект версии 2 не содержит объекта 'project'")
    project.setdefault("lithotypes", {})
    migrated["format_version"] = 3
    return migrated


def _migrate_v3_to_v4(payload: ProjectPayload) -> ProjectPayload:
    migrated = deepcopy(payload)
    project = migrated.get("project")
    if not isinstance(project, dict):
        raise ProjectMigrationError("Проект версии 3 не содержит объекта 'project'")
    project.setdefault("description_templates", {})
    migrated["format_version"] = 4
    return migrated


def _migrate_v4_to_v5(payload: ProjectPayload) -> ProjectPayload:
    migrated = deepcopy(payload)
    project = migrated.get("project")
    if not isinstance(project, dict):
        raise ProjectMigrationError("Проект версии 4 не содержит объекта 'project'")
    migrated.setdefault("source_artifacts", {})
    migrated["format_version"] = 5
    return migrated


def _migrate_v5_to_v6(payload: ProjectPayload) -> ProjectPayload:
    migrated = deepcopy(payload)
    project = migrated.get("project")
    if not isinstance(project, dict):
        raise ProjectMigrationError("Проект версии 5 не содержит объекта 'project'")
    wells = project.get("wells")
    if not isinstance(wells, dict):
        raise ProjectMigrationError("Проект версии 5 не содержит объекта wells")
    for well in wells.values():
        if not isinstance(well, dict) or not isinstance(well.get("datasets"), dict):
            raise ProjectMigrationError("Некорректная структура datasets версии 5")
        for dataset_id, dataset in well["datasets"].items():
            if not isinstance(dataset_id, str) or not isinstance(dataset, dict):
                raise ProjectMigrationError("Некорректный dataset версии 5")
            depth = dataset.get("depth")
            domain = dataset.get("depth_domain")
            if not isinstance(depth, list) or domain not in {"md", "tvd", "tvdss", "time"}:
                raise ProjectMigrationError("Dataset версии 5 не содержит depth/depth_domain")
            index_id = f"{dataset_id}:primary-index"
            is_time = domain == "time"
            dataset["indexes"] = {
                index_id: {
                    "index_id": index_id,
                    "mnemonic": "TIME" if is_time else "DEPT",
                    "index_type": "relative_time" if is_time else domain,
                    "role": "time" if is_time else "depth",
                    "unit": "ms" if is_time else "m",
                    "values": depth,
                    "confidence": 1.0,
                    "evidence": ["project v5 depth/depth_domain migration"],
                    "datetime_format": None,
                    "timezone": None,
                }
            }
            dataset["active_index_id"] = index_id
    migrated["format_version"] = 6
    return migrated


DEFAULT_PROJECT_MIGRATIONS = ProjectMigrationRegistry()
DEFAULT_PROJECT_MIGRATIONS.register(0, _migrate_legacy_to_v1)
DEFAULT_PROJECT_MIGRATIONS.register(1, _migrate_v1_to_v2)
DEFAULT_PROJECT_MIGRATIONS.register(2, _migrate_v2_to_v3)
DEFAULT_PROJECT_MIGRATIONS.register(3, _migrate_v3_to_v4)
DEFAULT_PROJECT_MIGRATIONS.register(4, _migrate_v4_to_v5)
DEFAULT_PROJECT_MIGRATIONS.register(5, _migrate_v5_to_v6)


def migrate_project_payload(payload: ProjectPayload, target_version: int) -> ProjectPayload:
    return DEFAULT_PROJECT_MIGRATIONS.migrate(payload, target_version)
