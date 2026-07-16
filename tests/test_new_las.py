import numpy as np
import pytest

from geoworkbench.data.las_adapter import export_las
from geoworkbench.data.las_export_plan import LasExportPlan, LasExportVersion
from geoworkbench.domain.models import DatasetKind, DepthDomain, IndexType
from geoworkbench.project.new_las_controller import NewLasController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.new_las import NewLasPlan, create_empty_las_dataset


def make_plan(**changes) -> NewLasPlan:
    values = {
        "name": "Clean LAS",
        "version": LasExportVersion.V2_0,
        "index_type": IndexType.MD,
        "start": 100.0,
        "stop": 101.0,
        "step": 0.2,
        "null_value": -9999.25,
    }
    values.update(changes)
    return NewLasPlan(**values)


def test_new_las_dataset_contains_typed_grid_and_export_headers(tmp_path) -> None:
    plan = make_plan(version=LasExportVersion.V1_2, index_type=IndexType.TVD)

    dataset = create_empty_las_dataset(plan)

    assert dataset.kind is DatasetKind.USER
    assert dataset.depth_domain is DepthDomain.TVD
    assert dataset.active_index.index_type is IndexType.TVD
    np.testing.assert_allclose(dataset.depth, [100.0, 100.2, 100.4, 100.6, 100.8, 101.0])
    assert dataset.curves == {}
    assert dataset.version_headers == {"VERS": "1.2", "WRAP": "NO"}
    assert dataset.headers == {
        "WELL": "Clean LAS",
        "STRT": "100",
        "STOP": "101",
        "STEP": "0.2",
        "NULL": "-9999.25",
    }

    target = tmp_path / "clean.las"
    export_las(dataset, target, plan=LasExportPlan(version=LasExportVersion.V1_2))
    text = target.read_text(encoding="utf-8")
    assert "VERS" in text
    assert "1.2" in text
    assert "DEPT" in text


def test_new_las_plan_rejects_null_collision() -> None:
    with pytest.raises(ValueError, match="NULL совпадает"):
        make_plan(null_value=100.4)


def test_new_las_plan_rejects_boolean_numeric_values() -> None:
    with pytest.raises(ValueError, match="должны быть числами"):
        make_plan(step=True)


def test_new_las_controller_adds_dataset_to_project() -> None:
    session = ProjectSession()

    dataset = NewLasController(session).create(make_plan())

    assert session.current_dataset is dataset
    assert session.current_well is not None
    assert session.current_well.name == "Clean LAS"
    assert session.dirty is True
