import numpy as np
import pytest

from geoworkbench.calculations.custom_formula import (
    CustomFormulaError,
    evaluate_formula,
    formula_inputs,
    validate_definition,
)
from geoworkbench.domain.models import CustomFormulaDefinition


def test_evaluates_gas_formula_and_infers_inputs() -> None:
    expression = "100 * (C2 + C3 + IC4 + NC4) / (C1 + C2 + C3 + IC4 + NC4)"
    inputs = {
        name: np.array([value])
        for name, value in {
            "C1": 80.0,
            "C2": 10.0,
            "C3": 5.0,
            "IC4": 2.0,
            "NC4": 3.0,
        }.items()
    }

    assert formula_inputs(expression) == ("C1", "C2", "C3", "IC4", "NC4")
    np.testing.assert_allclose(evaluate_formula(expression, inputs), [20.0])


def test_invalid_domain_becomes_nan() -> None:
    result = evaluate_formula("C1 / C2", {"C1": np.array([1.0]), "C2": np.array([0.0])})
    assert np.isnan(result[0])


@pytest.mark.parametrize(
    "expression",
    ["__import__('os')", "C1.__class__", "[x for x in C1]", "open('secret')"],
)
def test_rejects_executable_or_object_access(expression: str) -> None:
    with pytest.raises(CustomFormulaError):
        formula_inputs(expression)


def test_definition_cannot_depend_on_its_output() -> None:
    definition = CustomFormulaDefinition("wet", "Wetness", "WH + C1", "WH", "%")
    with pytest.raises(CustomFormulaError, match="собственной"):
        validate_definition(definition)
