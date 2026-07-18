import numpy as np
import pytest

from geoworkbench.calculations.custom_formula import CustomFormulaError
from geoworkbench.domain.models import (
    CalculationState,
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


def test_formula_update_marks_transitive_outputs_stale_and_refreshes_passport() -> None:
    controller, dataset = make_controller()
    controller.save(CustomFormulaDefinition("first", "First", "C1 + 1", "FIRST", "%"))
    controller.save(
        CustomFormulaDefinition("second", "Second", "FIRST * 2", "SECOND", "%")
    )
    controller.apply_batch(controller.analyze_batch())
    first = dataset.curve_by_mnemonic("FIRST")
    second = dataset.curve_by_mnemonic("SECOND")
    assert first is not None and second is not None

    stored = controller.save(
        CustomFormulaDefinition("first", "First v2", "C1 + 2", "FIRST", "ppm")
    )

    assert stored.version == 2
    assert first.state is CalculationState.STALE
    assert second.state is CalculationState.STALE
    assert not controller.can_undo_batch

    recalculated = controller.calculate("first")

    assert recalculated.state is CalculationState.CURRENT
    assert second.state is CalculationState.STALE
    assert recalculated.metadata.description == "First v2"
    assert recalculated.metadata.unit == "ppm"
    assert recalculated.metadata.provenance == "custom-formula:first:2"
    np.testing.assert_allclose(recalculated.values, [3.0, 4.0, 5.0])


def test_formula_delete_marks_removed_output_and_consumers_stale() -> None:
    controller, dataset = make_controller()
    controller.save(CustomFormulaDefinition("first", "First", "C1 + 1", "FIRST", "%"))
    controller.save(
        CustomFormulaDefinition("second", "Second", "FIRST * 2", "SECOND", "%")
    )
    controller.apply_batch(controller.analyze_batch())

    controller.delete("first")

    first = dataset.curve_by_mnemonic("FIRST")
    second = dataset.curve_by_mnemonic("SECOND")
    assert first is not None and first.state is CalculationState.STALE
    assert second is not None and second.state is CalculationState.STALE


def test_formula_update_invalidates_matching_outputs_in_other_dataset() -> None:
    controller, _ = make_controller()
    controller.save(CustomFormulaDefinition("first", "First", "C1 + 1", "FIRST", "%"))
    other = Dataset(
        "other", "Other", DatasetKind.GTI, DepthDomain.MD, np.array([0.0, 1.0, 2.0])
    )
    other.curves["first-other"] = CurveData(
        CurveMetadata(
            "first-other",
            "FIRST",
            "FIRST",
            "%",
            "First",
            other.dataset_id,
            "custom-formula:first:1",
        ),
        np.array([2.0, 3.0, 4.0]),
    )
    well = controller.session.current_well
    assert well is not None
    well.datasets[other.dataset_id] = other

    controller.save(CustomFormulaDefinition("first", "First", "C1 + 2", "FIRST", "%"))

    assert other.curves["first-other"].state is CalculationState.STALE


def test_calculation_passport_exposes_inputs_output_and_versioned_provenance() -> None:
    controller, _ = make_controller()
    controller.save(CustomFormulaDefinition("first", "First", "C1 + C2", "FIRST", "%"))

    missing = controller.calculation_passport("first")

    assert [item.requested_mnemonic for item in missing.inputs] == ["C1", "C2"]
    assert missing.inputs[0].curve_id == "c1"
    assert missing.inputs[0].provenance == "source"
    assert missing.inputs[1].curve_id is None
    assert missing.output.curve_id is None

    dataset = controller.session.current_dataset
    assert dataset is not None
    dataset.curves["c2"] = CurveData(
        CurveMetadata("c2", "C2", "C2", "%", None, dataset.dataset_id),
        np.array([10.0, 20.0, 30.0]),
    )
    controller.calculate("first")
    passport = controller.calculation_passport("first")

    assert passport.version == 1
    assert passport.expression == "C1 + C2"
    assert passport.output.state is CalculationState.CURRENT
    assert passport.output.provenance == "custom-formula:first:1"
