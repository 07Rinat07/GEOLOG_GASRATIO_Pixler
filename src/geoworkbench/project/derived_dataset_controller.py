from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.project.session import ProjectSession


@dataclass(frozen=True, slots=True)
class DerivedDatasetCheckpoint:
    """Project context captured before creating a temporary derived dataset."""

    well_id: str | None
    dataset_id: str | None
    dirty: bool
    existing_dataset_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class DerivedDatasetRollback:
    removed_dataset_id: str | None
    restored_dataset_id: str | None
    restored_dirty: bool


@dataclass(slots=True)
class DerivedDatasetController:
    """Own rollback of temporary merge/insert datasets outside the Qt layer."""

    session: ProjectSession

    def checkpoint(self) -> DerivedDatasetCheckpoint:
        return DerivedDatasetCheckpoint(
            well_id=self.session.current_well_id,
            dataset_id=self.session.current_dataset_id,
            dirty=self.session.dirty,
            existing_dataset_ids=frozenset(
                dataset.dataset_id
                for well in self.session.project.wells.values()
                for dataset in well.datasets.values()
            ),
        )

    def rollback(self, checkpoint: DerivedDatasetCheckpoint) -> DerivedDatasetRollback:
        if not isinstance(checkpoint, DerivedDatasetCheckpoint):
            raise TypeError("Ожидалась контрольная точка производного dataset")

        created_dataset_ids = tuple(
            dataset_id
            for well in self.session.project.wells.values()
            for dataset_id in well.datasets
            if dataset_id not in checkpoint.existing_dataset_ids
        )
        for dataset_id in created_dataset_ids:
            for well in self.session.project.wells.values():
                if dataset_id in well.datasets:
                    well.datasets.pop(dataset_id, None)
                    break
            self.session.tablet_layouts.pop(dataset_id, None)
            self.session.source_documents.pop(dataset_id, None)
            self.session.import_reports.pop(dataset_id, None)

        removed_dataset_id = created_dataset_ids[0] if created_dataset_ids else None
        self.session.current_well_id = checkpoint.well_id
        self.session.current_dataset_id = checkpoint.dataset_id
        self.session.dirty = checkpoint.dirty
        return DerivedDatasetRollback(
            removed_dataset_id=removed_dataset_id,
            restored_dataset_id=checkpoint.dataset_id,
            restored_dirty=checkpoint.dirty,
        )
