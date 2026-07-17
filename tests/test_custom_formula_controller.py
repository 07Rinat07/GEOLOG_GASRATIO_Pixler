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

    controller.undo_batch()
    assert dataset.curve_by_mnemonic("FIRST") is None
    assert dataset.curve_by_mnemonic("SECOND") is None
    assert controller.can_redo_batch

    restored = controller.redo_batch()
    np.testing.assert_allclose(restored[0].values, [2.0, 3.0, 4.0])
    np.testing.assert_allclose(restored[1].values, [6.0, 9.0, 12.0])
    assert controller.can_undo_batch


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


def test_batch_undo_restores_previous_output_and_blocks_conflicting_change() -> None:
    controller, dataset = make_controller()
    controller.session.project.custom_formulas["first"] = CustomFormulaDefinition(
        "first", "First", "C1 + 1", "FIRST", "%"
    )
    previous = dataset.upsert_curve(
        "FIRST",
        np.array([10.0, 20.0, 30.0]),
        provenance="custom-formula:first:1",
    )
    previous_values = previous.values.copy()
    controller.apply_batch(controller.analyze_batch())

    controller.undo_batch()

    restored = dataset.curve_by_mnemonic("FIRST")
    assert restored is not None
    np.testing.assert_allclose(restored.values, previous_values)

    dataset.curves["c1"].version += 1
    with pytest.raises(RuntimeError, match="Redo заблокирован"):
        controller.redo_batch()


def test_batch_undo_blocks_output_changed_after_apply() -> None:
    controller, dataset = make_controller()
    controller.session.project.custom_formulas["first"] = CustomFormulaDefinition(
        "first", "First", "C1 + 1", "FIRST", "%"
    )
    controller.apply_batch(controller.analyze_batch())
    output = dataset.curve_by_mnemonic("FIRST")
    assert output is not None
    output.values[0] = 999.0

    with pytest.raises(RuntimeError, match="Undo заблокирован"):
        controller.undo_batch()
