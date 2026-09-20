from __future__ import annotations

from pathlib import Path

from geoworkbench.importers.witsml import read_witsml_channel_sets
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.witsml_import_coordinator import WitsmlImportCoordinator
from geoworkbench.services.witsml_import_review import WitsmlImportReviewController


SAMPLE = Path("resources/samples/witsml/log_channel_set_2_1.xml")


def _commit():
    channel_set = read_witsml_channel_sets(SAMPLE).channel_sets[0]
    review = WitsmlImportReviewController()
    return review.commit(channel_set, review.initial_plan(channel_set))


def test_coordinator_registers_first_commit_into_new_well() -> None:
    session = ProjectSession()
    commit = _commit()

    result = WitsmlImportCoordinator(session).register_reviewed_commit(commit)

    assert result.commit is commit
    assert session.current_well is not None
    assert session.current_dataset is commit.dataset
    assert session.current_well.datasets == {commit.dataset.dataset_id: commit.dataset}
    assert session.dirty


def test_coordinator_registers_next_commit_into_current_well() -> None:
    session = ProjectSession()
    coordinator = WitsmlImportCoordinator(session)
    first = _commit()
    coordinator.register_reviewed_commit(first)

    second = _commit()
    second.dataset.dataset_id = "second-dataset"
    result = coordinator.register_reviewed_commit(second)

    assert result.commit is second
    assert session.current_well is not None
    assert set(session.current_well.datasets) == {
        first.dataset.dataset_id,
        second.dataset.dataset_id,
    }


def test_main_window_does_not_construct_witsml_project_controller_directly() -> None:
    source = Path("src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")

    assert "WitsmlImportCoordinator" in source
    assert "self.witsml_import_coordinator.register_reviewed_commit(" in source
    assert "WitsmlProjectImportController(self.session)" not in source
