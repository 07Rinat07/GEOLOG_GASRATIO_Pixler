import numpy as np
import pytest

from geoworkbench.calculations.custom_formula import CustomFormulaError
from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    CustomFormulaDefinition,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.project.custom_formula_controller import CustomFormulaController
from geoworkbench.project.session import ProjectSession


def make_controller() -> tuple[CustomFormulaController, Dataset]:
    dataset = Dataset(
        "dataset", "Dataset", DatasetKind.GTI, DepthDomain.MD, np.array([0.0, 1.0, 2.0])
    )
    dataset.curves["c1"] = CurveData(
        CurveMetadata("c1", "C1", "C1", "%", None, dataset.dataset_id),
        np.array([1.0, 2.0, 3.0]),
    )
    session = ProjectSession()
    session.add_dataset(dataset)
    return CustomFormulaController(session), dataset


def test_batch_formula_plan_uses_dependency_order_and_applies_atomically() -> None:
    controller, dataset = make_controller()
    controller.session.project.custom_formulas = {
        "second": CustomFormulaDefinition("second", "Second", "FIRST * 3", "SECOND", "%"),
        "first": CustomFormulaDefinition("first", "First", "C1 + 1", "FIRST", "%"),
    }

    plan = controller.analyze_batch()

    assert plan.ordered_formula_ids == ("first", "second")
    assert [item.output_mnemonic for item in plan.previews] == ["FIRST", "SECOND"]
    assert plan.previews[0].changed_count == 3
    assert dataset.curve_by_mnemonic("FIRST") is None

    curves = controller.apply_batch(plan)

    np.testing.assert_allclose(curves[0].values, [2.0, 3.0, 4.0])
    np.testing.assert_allclose(curves[1].values, [6.0, 9.0, 12.0])
    assert controller.session.dirty


def test_batch_formula_analysis_rejects_cycle_without_changing_dataset() -> None:
    controller, dataset = make_controller()
    controller.session.project.custom_formulas = {
        "first": CustomFormulaDefinition("first", "First", "SECOND + 1", "FIRST", "%"),
        "second": CustomFormulaDefinition("second", "Second", "FIRST + 1", "SECOND", "%"),
    }

    with pytest.raises(CustomFormulaError, match="циклическую"):
        controller.analyze_batch()

    assert set(dataset.curves) == {"c1"}


def test_batch_formula_plan_is_rejected_after_source_change() -> None:
    controller, dataset = make_controller()
    controller.session.project.custom_formulas["first"] = CustomFormulaDefinition(
        "first", "First", "C1 + 1", "FIRST", "%"
    )
    plan = controller.analyze_batch()
    dataset.curves["c1"].version += 1

    with pytest.raises(RuntimeError, match="изменились"):
        controller.apply_batch(plan)

    assert dataset.curve_by_mnemonic("FIRST") is None
