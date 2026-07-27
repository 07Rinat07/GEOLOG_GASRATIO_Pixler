from __future__ import annotations

from pathlib import Path

import pytest

from geoworkbench.importers.witsml import read_witsml_channel_sets
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.witsml_import_controller import WitsmlProjectImportController
from geoworkbench.services.witsml_import_review import WitsmlImportReviewController


SAMPLE = Path("resources/samples/witsml/log_channel_set_2_1.xml")


def _commit():
    channel_set = read_witsml_channel_sets(SAMPLE).channel_sets[0]
    controller = WitsmlImportReviewController()
    return controller.commit(channel_set, controller.initial_plan(channel_set))


def test_registers_exact_reviewed_commit_once() -> None:
    session = ProjectSession()
    commit = _commit()

    result = WitsmlProjectImportController(session).register(commit, create_new_well=True)

    assert result.commit is commit
    assert session.current_dataset is commit.dataset
    assert session.current_well is not None
    assert session.current_well.datasets == {commit.dataset.dataset_id: commit.dataset}
    assert session.dirty


def test_duplicate_dataset_registration_is_rejected_without_mutation() -> None:
    session = ProjectSession()
    commit = _commit()
    controller = WitsmlProjectImportController(session)
    controller.register(commit, create_new_well=True)
    state = (session.current_well_id, session.current_dataset_id, session.dirty, tuple(session.project.wells))

    with pytest.raises(ValueError, match="already exists"):
        controller.register(commit)

    assert (session.current_well_id, session.current_dataset_id, session.dirty, tuple(session.project.wells)) == state


def test_registration_rolls_back_partial_project_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    session = ProjectSession()
    commit = _commit()
    original = ProjectSession.add_dataset

    def broken_add(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise RuntimeError("simulated project registration failure")

    monkeypatch.setattr(ProjectSession, "add_dataset", broken_add)

    with pytest.raises(RuntimeError, match="simulated"):
        WitsmlProjectImportController(session).register(commit, create_new_well=True)

    assert session.project.wells == {}
    assert session.current_well_id is None
    assert session.current_dataset_id is None
    assert not session.dirty
