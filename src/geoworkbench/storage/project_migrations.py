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


DEFAULT_PROJECT_MIGRATIONS = ProjectMigrationRegistry()
DEFAULT_PROJECT_MIGRATIONS.register(0, _migrate_legacy_to_v1)
DEFAULT_PROJECT_MIGRATIONS.register(1, _migrate_v1_to_v2)
DEFAULT_PROJECT_MIGRATIONS.register(2, _migrate_v2_to_v3)


def migrate_project_payload(payload: ProjectPayload, target_version: int) -> ProjectPayload:
    return DEFAULT_PROJECT_MIGRATIONS.migrate(payload, target_version)
