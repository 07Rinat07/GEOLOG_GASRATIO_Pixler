from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from geoworkbench.importers.witsml import read_witsml_channel_sets
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.witsml_import_coordinator import WitsmlImportCoordinator
from geoworkbench.services.witsml_import_review import WitsmlImportReviewController


SAMPLE = Path("resources/samples/witsml/log_channel_set_2_1.xml")


def _commit(*, dataset_id: str | None = None):
    channel_set = read_witsml_channel_sets(SAMPLE).channel_sets[0]
    review = WitsmlImportReviewController()
    plan = review.initial_plan(channel_set)
    if dataset_id is not None:
        plan = replace(plan, dataset_id=dataset_id)
    return review.commit(channel_set, plan)


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

    second = _commit(dataset_id="second-dataset")
    result = coordinator.register_reviewed_commit(second)

    assert result.commit is second
    assert session.current_well is not None
    assert set(session.current_well.datasets) == {
        first.dataset.dataset_id,
        second.dataset.dataset_id,
    }



def test_coordinator_uses_rebound_project_session() -> None:
    first_session = ProjectSession()
    second_session = ProjectSession()
    coordinator = WitsmlImportCoordinator(first_session)
    coordinator.session = second_session

    commit = _commit(dataset_id="rebound-dataset")
    coordinator.register_reviewed_commit(commit)

    assert first_session.project.wells == {}
    assert second_session.current_dataset is commit.dataset
    assert second_session.dirty

def test_main_window_does_not_construct_witsml_project_controller_directly() -> None:
    source = Path("src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")

    assert "WitsmlImportCoordinator" in source
    assert source.count(
        "self.witsml_import_coordinator.register_reviewed_commit(commit)"
    ) == 2
    assert "WitsmlProjectImportController(self.session)" not in source
    assert 'bindings.register(self.witsml_import_coordinator, name="witsml_import")' in source
