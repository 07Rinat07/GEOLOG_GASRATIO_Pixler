from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path

from geoworkbench.domain.models import Dataset
from geoworkbench.project.repository import ProjectRepository
from geoworkbench.project.session import ProjectSession
from geoworkbench.storage.project_file_safety import (
    ProjectChangedExternallyError,
    ProjectBackupRecord,
    ProjectDiskState,
    ProjectFileSafetyError,
    ProjectFileSafetyService,
    SafeSaveResult,
    SaveMode,
)
from geoworkbench.storage.project_repository_router import ProjectRepositoryRouter
from geoworkbench.storage.project_codec import ProjectDocument


@dataclass(slots=True)
class ProjectController:
    """Application workflows for opening and saving projects, independent of Qt."""

    repository: ProjectRepository = field(default_factory=ProjectRepositoryRouter)
    session: ProjectSession = field(default_factory=ProjectSession)
    project_path: Path | None = None
    disk_state: ProjectDiskState | None = None
    last_save_result: SafeSaveResult | None = None
    file_safety: ProjectFileSafetyService | None = field(
        init=False,
        default=None,
        repr=False,
    )

    def __post_init__(self) -> None:
        # Custom repositories remain a lightweight test/plugin boundary. Only the
        # built-in router has the filesystem semantics required by verified saves.
        if isinstance(self.repository, ProjectRepositoryRouter):
            self.file_safety = ProjectFileSafetyService(repository=self.repository)

    def open_project(self, source: Path) -> ProjectSession:
        disk_state: ProjectDiskState | None = None
        if self.file_safety is not None:
            document, disk_state = self.file_safety.open_verified(source)
        else:
            document = self.repository.load(source)
        session = ProjectSession(
            project=document.project,
            tablet_layouts=document.tablet_layouts,
            tablet_presets=document.tablet_presets,
            source_documents=document.source_documents,
            import_reports=document.import_reports,
            image_assets=document.image_assets,
        )
        self._select_first_dataset(session)
        session.dirty = False
        self.session = session
        self.project_path = source
        self.disk_state = disk_state
        self.last_save_result = None
        return session

    def mark_open_migration_required(self, required: bool) -> None:
        """Record whether opening the project performed a save-worthy migration."""

        self.session.dirty = bool(required)

    def select_existing_dataset(
        self,
        dataset_id: str,
        *,
        mark_dirty: bool = False,
    ) -> Dataset:
        """Select a dataset in the current well through the project boundary.

        Acquisition callbacks use this method after appending rows to an existing
        dataset.  The Qt layer therefore does not mutate serialized session fields
        directly.
        """

        well = self.session.current_well
        if well is None:
            raise KeyError("No current well")
        dataset = well.datasets.get(dataset_id)
        if dataset is None:
            raise KeyError(dataset_id)
        self.session.current_dataset_id = dataset_id
        if mark_dirty:
            self.session.dirty = True
        return dataset

    def save_project(
        self,
        target: Path | None = None,
        *,
        mode: SaveMode = SaveMode.EXPLICIT,
        allow_existing_target: bool = False,
    ) -> Path:
        destination = target or self.project_path
        if destination is None:
            raise ValueError("Не указан путь сохранения проекта")
        document = ProjectDocument(
            project=self.session.project,
            tablet_layouts=self.session.tablet_layouts,
            tablet_presets=self.session.tablet_presets,
            source_documents=self.session.source_documents,
            import_reports=self.session.import_reports,
            image_assets=self.session.image_assets,
        )
        previous_revision = self.session.project.save_revision
        self.session.project.save_revision = previous_revision + 1
        self.last_save_result = None
        try:
            if self.file_safety is not None:
                same_target = self.project_path is not None and self._same_path(
                    destination,
                    self.project_path,
                )
                result = self.file_safety.save(
                    document,
                    destination,
                    expected=self.disk_state if same_target else None,
                    mode=mode,
                    allow_existing_target=allow_existing_target,
                )
            else:
                self.repository.save(document, destination)
                result = None
        except Exception:
            self.session.project.save_revision = previous_revision
            raise
        if result is not None:
            self.disk_state = result.disk_state
            self.last_save_result = result
        else:
            self.disk_state = None
        self.project_path = destination
        self.session.dirty = False
        return destination

    def assert_project_storage_current(self) -> None:
        """Raise a typed conflict when the verified project changed on disk."""

        if self.file_safety is None or self.project_path is None or self.disk_state is None:
            return
        try:
            current = self.file_safety.inspect(self.project_path)
        except ProjectChangedExternallyError:
            raise
        except Exception as exc:
            raise ProjectChangedExternallyError(
                "Не удалось подтвердить неизменность открытого файла проекта"
            ) from exc
        if not self._same_disk_state(self.disk_state, current):
            raise ProjectChangedExternallyError(
                "Файл проекта изменён после открытия. Сохраните текущую работу как копию."
            )

    def recovery_candidates(
        self,
        source: Path | None = None,
    ) -> tuple[ProjectBackupRecord, ...]:
        """Return verified recovery snapshots for the active or requested project path."""

        if self.file_safety is None:
            raise ProjectFileSafetyError(
                "Резервные копии доступны только для файлового репозитория проектов"
            )
        project_path = source or self.project_path
        if project_path is None:
            raise ValueError("Не указан исходный путь проекта")
        return self.file_safety.recovery_candidates(project_path)

    def restore_backup_as_copy(
        self,
        record: ProjectBackupRecord,
        target: Path,
    ) -> ProjectDiskState:
        """Restore one verified snapshot under a new name without switching the session."""

        if self.file_safety is None:
            raise ProjectFileSafetyError(
                "Восстановление доступно только для файлового репозитория проектов"
            )
        return self.file_safety.restore_as_copy(record, target)

    @staticmethod
    def _same_path(first: Path, second: Path) -> bool:
        return os.path.normcase(os.path.abspath(first)) == os.path.normcase(os.path.abspath(second))

    @staticmethod
    def _same_disk_state(expected: ProjectDiskState, current: ProjectDiskState) -> bool:
        return (
            expected.path_id == current.path_id
            and expected.storage_kind == current.storage_kind
            and expected.project_id == current.project_id
            and expected.save_revision == current.save_revision
            and expected.bundle_sha256 == current.bundle_sha256
        )

    @staticmethod
    def _select_first_dataset(session: ProjectSession) -> None:
        for well in session.project.wells.values():
            for dataset in well.datasets.values():
                session.current_well_id = well.well_id
                session.current_dataset_id = dataset.dataset_id
                return
