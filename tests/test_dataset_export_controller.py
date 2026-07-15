from pathlib import Path

import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, Project, Well
from geoworkbench.data.lossless_las import parse_lossless_las
from geoworkbench.project.dataset_export_controller import DatasetExportController
from geoworkbench.project.session import ProjectSession


def test_export_controller_uses_current_dataset(tmp_path, monkeypatch) -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([1.0]),
    )
    well = Well("well-1", "Well", datasets={dataset.dataset_id: dataset})
    session = ProjectSession(
        project=Project("project-1", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=dataset.dataset_id,
        source_documents={dataset.dataset_id: parse_lossless_las(b"~A\n1\n")},
    )
    captured: list[tuple[Dataset, Path, bool, object]] = []

    def fake_export(selected, target, *, overwrite=False, source_document=None, plan=None):
        assert plan is None
        captured.append((selected, target, overwrite, source_document))
        return target

    monkeypatch.setattr(
        "geoworkbench.project.dataset_export_controller.export_las",
        fake_export,
    )
    target = tmp_path / "result.las"

    result = DatasetExportController(session).export_current_las(target, overwrite=True)

    assert result == target
    assert captured == [(dataset, target, True, session.source_documents[dataset.dataset_id])]


def test_export_controller_requires_current_dataset(tmp_path) -> None:
    with pytest.raises(RuntimeError, match="набор данных"):
        DatasetExportController(ProjectSession()).export_current_las(tmp_path / "result.las")


def test_default_export_plan_uses_typed_header_null() -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([1.0]),
        headers={"NULL": "-999.25"},
    )
    well = Well("well-1", "Well", datasets={dataset.dataset_id: dataset})
    session = ProjectSession(
        project=Project("project-1", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=dataset.dataset_id,
    )

    plan = DatasetExportController(session).default_las_plan()

    assert plan.null_value == pytest.approx(-999.25)
