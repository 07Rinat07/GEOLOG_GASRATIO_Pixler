import numpy as np
import pytest

from geoworkbench.domain.models import (
    CalculationState,
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
    Project,
    Well,
)
from geoworkbench.project.curve_editing_controller import CurveEditingController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.dependency_graph import DependencyGraph


def add_curve(dataset: Dataset, curve_id: str, mnemonic: str) -> CurveData:
    curve = CurveData(
        CurveMetadata(curve_id, mnemonic, mnemonic, None, None, dataset.dataset_id),
        np.array([1.0, 2.0, 3.0]),
    )
    dataset.curves[curve_id] = curve
    return curve


def make_controller() -> tuple[CurveEditingController, dict[str, CurveData]]:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0, 102.0]),
    )
    curves = {
        "source": add_curve(dataset, "source", "C1"),
        "ratio": add_curve(dataset, "ratio", "C1_C2"),
        "anomaly": add_curve(dataset, "anomaly", "ANOMALY"),
    }
    well = Well("well-1", "Well", datasets={dataset.dataset_id: dataset})
    session = ProjectSession(
        project=Project("project-1", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=dataset.dataset_id,
    )
    graph = DependencyGraph()
    graph.add_dependency("C1", "C1_C2")
    graph.add_dependency("C1_C2", "ANOMALY")
    return CurveEditingController(session, graph), curves


def test_controller_edits_curve_and_marks_dependents_stale() -> None:
    controller, curves = make_controller()

    outcome = controller.edit_curve("source", np.array([1]), np.array([20.0]))

    np.testing.assert_allclose(curves["source"].values, [1.0, 20.0, 3.0])
    assert curves["source"].state is CalculationState.CURRENT
    assert curves["ratio"].state is CalculationState.STALE
    assert curves["anomaly"].state is CalculationState.STALE
    assert outcome.operation == "edit"
    assert outcome.affected_mnemonics == ("ANOMALY", "C1_C2")
    assert controller.session.dirty is True


def test_controller_undo_and_redo_preserve_dependency_invalidation() -> None:
    controller, curves = make_controller()
    controller.edit_curve("source", np.array([0]), np.array([10.0]))
    curves["ratio"].state = CalculationState.CURRENT
    curves["anomaly"].state = CalculationState.CURRENT

    undo_outcome = controller.undo()
    assert undo_outcome.operation == "undo"
    np.testing.assert_allclose(curves["source"].values, [1.0, 2.0, 3.0])
    assert curves["ratio"].state is CalculationState.STALE
    assert curves["anomaly"].state is CalculationState.STALE

    curves["ratio"].state = CalculationState.CURRENT
    redo_outcome = controller.redo()
    assert redo_outcome.operation == "redo"
    np.testing.assert_allclose(curves["source"].values, [10.0, 2.0, 3.0])
    assert curves["ratio"].state is CalculationState.STALE


def test_controller_rejects_missing_dataset_or_curve() -> None:
    with pytest.raises(RuntimeError, match="набор данных"):
        CurveEditingController(ProjectSession()).edit_curve(
            "missing",
            np.array([0]),
            np.array([1.0]),
        )

    controller, _ = make_controller()
    with pytest.raises(KeyError, match="missing"):
        controller.edit_curve("missing", np.array([0]), np.array([1.0]))
