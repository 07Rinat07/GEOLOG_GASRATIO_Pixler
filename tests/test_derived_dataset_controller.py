from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, Project, Well
from geoworkbench.project.derived_dataset_controller import DerivedDatasetController
from geoworkbench.project.session import ProjectSession
from geoworkbench.tablet.models import TabletLayout


def _dataset(dataset_id: str) -> Dataset:
    return Dataset(
        dataset_id,
        dataset_id,
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0]),
    )


def test_rollback_removes_temporary_dataset_and_restores_project_state() -> None:
    original = _dataset("original")
    well = Well("well", "Well", datasets={original.dataset_id: original})
    session = ProjectSession(
        project=Project("project", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=original.dataset_id,
        dirty=False,
    )
    controller = DerivedDatasetController(session)
    checkpoint = controller.checkpoint()

    derived = _dataset("derived")
    well.datasets[derived.dataset_id] = derived
    session.tablet_layouts[derived.dataset_id] = TabletLayout()
    session.source_documents[derived.dataset_id] = object()  # type: ignore[assignment]
    session.import_reports[derived.dataset_id] = object()  # type: ignore[assignment]
    session.current_dataset_id = derived.dataset_id
    session.dirty = True

    report = controller.rollback(checkpoint)

    assert report.removed_dataset_id == derived.dataset_id
    assert report.restored_dataset_id == original.dataset_id
    assert report.restored_dirty is False
    assert set(well.datasets) == {original.dataset_id}
    assert derived.dataset_id not in session.tablet_layouts
    assert derived.dataset_id not in session.source_documents
    assert derived.dataset_id not in session.import_reports
    assert session.current_well_id == well.well_id
    assert session.current_dataset_id == original.dataset_id
    assert session.dirty is False


def test_rollback_without_created_dataset_only_restores_selection_and_dirty_flag() -> None:
    first = _dataset("first")
    second = _dataset("second")
    well = Well(
        "well",
        "Well",
        datasets={first.dataset_id: first, second.dataset_id: second},
    )
    session = ProjectSession(
        project=Project("project", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=first.dataset_id,
        dirty=True,
    )
    controller = DerivedDatasetController(session)
    checkpoint = controller.checkpoint()
    session.current_dataset_id = second.dataset_id
    session.dirty = False

    report = controller.rollback(checkpoint)

    assert report.removed_dataset_id is None
    assert set(well.datasets) == {first.dataset_id, second.dataset_id}
    assert session.current_dataset_id == first.dataset_id
    assert session.dirty is True


def test_rollback_removes_created_dataset_even_after_selection_changed() -> None:
    original = _dataset("original")
    existing = _dataset("existing")
    well = Well(
        "well",
        "Well",
        datasets={original.dataset_id: original, existing.dataset_id: existing},
    )
    session = ProjectSession(
        project=Project("project", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=original.dataset_id,
        dirty=False,
    )
    controller = DerivedDatasetController(session)
    checkpoint = controller.checkpoint()

    derived = _dataset("derived")
    well.datasets[derived.dataset_id] = derived
    session.tablet_layouts[derived.dataset_id] = TabletLayout()
    session.current_dataset_id = existing.dataset_id
    session.dirty = True

    report = controller.rollback(checkpoint)

    assert report.removed_dataset_id == derived.dataset_id
    assert set(well.datasets) == {original.dataset_id, existing.dataset_id}
    assert session.current_dataset_id == original.dataset_id
    assert session.dirty is False
