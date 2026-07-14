import numpy as np
import pytest

from geoworkbench.calculations.gas_ratio import calculate_basic_ratios, safe_ratio
from geoworkbench.calculations.pixler import FormulaProfile, FormulaProfileRegistry
from geoworkbench.services.curve_editing import DrawPoint, interpolate_drawn_curve
from geoworkbench.services.cuttings import next_sample_interval
from geoworkbench.services.dependency_graph import DependencyGraph


def test_next_interval() -> None:
    assert next_sample_interval(1005.0, 5.0) == (1005.0, 1010.0)


def test_draw_interpolation() -> None:
    depth = np.array([0.0, 1.0, 2.0])
    result = interpolate_drawn_curve(depth, [DrawPoint(0, 10), DrawPoint(2, 20)])
    np.testing.assert_allclose(result, [10, 15, 20])


def test_dependency_graph() -> None:
    graph = DependencyGraph()
    graph.add_dependency("C1", "TG")
    graph.add_dependency("TG", "ANOMALY")
    assert graph.affected_outputs({"C1"}) == ["TG", "ANOMALY"]


def test_safe_ratio_handles_zero() -> None:
    result = safe_ratio(np.array([4.0, 2.0]), np.array([2.0, 0.0]))
    assert result[0] == 2.0
    assert np.isnan(result[1])


def test_basic_gas_ratios() -> None:
    results = calculate_basic_ratios(
        {
            "C1": np.array([10.0, 20.0]),
            "C2": np.array([2.0, 4.0]),
            "C3": np.array([1.0, 2.0]),
        }
    )
    np.testing.assert_allclose(results["C1_C2"].values, [5.0, 5.0])
    np.testing.assert_allclose(results["TG_CALC"].values, [13.0, 26.0])


def test_formula_profile_requires_source() -> None:
    registry = FormulaProfileRegistry()
    with pytest.raises(ValueError):
        registry.register(
            FormulaProfile("x", "X", "1", "", ("C1",), lambda inputs, params: inputs["C1"])
        )

from pathlib import Path

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain, Project, Well
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.project_codec import load_project


def test_project_round_trip(tmp_path: Path) -> None:
    dataset = Dataset(
        dataset_id="dataset-1",
        name="sample",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.array([1000.0, 1001.0]),
    )
    dataset.curves["curve-1"] = CurveData(
        metadata=CurveMetadata(
            curve_id="curve-1",
            original_mnemonic="C1",
            canonical_mnemonic="C1",
            unit="%abs",
            description="Methane",
            source_dataset_id="dataset-1",
        ),
        values=np.array([1.0, 2.0]),
    )
    well = Well("well-1", "KR-1", datasets={"dataset-1": dataset})
    project = Project("project-1", "Test", wells={"well-1": well})
    path = tmp_path / "project.geolog.json"

    save_project(project, path)
    restored = load_project(path)

    restored_dataset = restored.wells["well-1"].datasets["dataset-1"]
    assert restored.name == "Test"
    np.testing.assert_allclose(restored_dataset.depth, [1000.0, 1001.0])
    np.testing.assert_allclose(restored_dataset.curves["curve-1"].values, [1.0, 2.0])
