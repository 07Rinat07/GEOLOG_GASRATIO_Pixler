from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.importers.witsml import WitsmlChannelSetData
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.witsml_import_review import (
    WitsmlImportCommit,
    WitsmlImportReviewController,
    WitsmlImportReviewPlan,
)


@dataclass(frozen=True, slots=True)
class WitsmlProjectImportResult:
    commit: WitsmlImportCommit
    well_id: str
    well_name: str


class WitsmlProjectImportController:
    """Atomic project registration boundary for a validated WITSML import."""

    def __init__(
        self,
        session: ProjectSession,
        review_controller: WitsmlImportReviewController | None = None,
    ) -> None:
        self.session = session
        self.review_controller = review_controller or WitsmlImportReviewController()

    def commit(
        self,
        channel_set: WitsmlChannelSetData,
        plan: WitsmlImportReviewPlan,
        *,
        create_new_well: bool = False,
    ) -> WitsmlProjectImportResult:
        # Build and validate the complete Dataset before touching project state.
        commit = self.review_controller.commit(channel_set, plan)
        return self.register(commit, create_new_well=create_new_well)

    def register(
        self,
        commit: WitsmlImportCommit,
        *,
        create_new_well: bool = False,
    ) -> WitsmlProjectImportResult:
        """Register an already validated immutable commit atomically.

        The review dialog creates the complete import commit before any project
        mutation.  This method deliberately does not re-run parsing or mapping:
        the exact Dataset that the operator reviewed is the one registered.
        """

        dataset_id = commit.dataset.dataset_id
        if any(dataset_id in well.datasets for well in self.session.project.wells.values()):
            raise ValueError(f"Dataset ID already exists in project: {dataset_id}")

        previous_well_id = self.session.current_well_id
        previous_dataset_id = self.session.current_dataset_id
        previous_dirty = self.session.dirty
        existing_well_ids = set(self.session.project.wells)
        target_well = self.session.current_well
        try:
            well = self.session.add_dataset(
                commit.dataset,
                well_name=commit.dataset.headers.get("WELL") or commit.dataset.name,
                create_new_well=create_new_well,
            )
        except Exception:
            # Roll back all observable session mutations if registration fails.
            for well_id in set(self.session.project.wells).difference(existing_well_ids):
                self.session.project.wells.pop(well_id, None)
            if target_well is not None:
                target_well.datasets.pop(dataset_id, None)
            self.session.current_well_id = previous_well_id
            self.session.current_dataset_id = previous_dataset_id
            self.session.dirty = previous_dirty
            raise
        return WitsmlProjectImportResult(commit, well.well_id, well.name)
