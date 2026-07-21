from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from geoworkbench.calculations.custom_formula import calculate_custom_formula
from geoworkbench.calculations.pixler import FormulaProfileRegistry
from geoworkbench.domain.models import CalculationState, Dataset
from geoworkbench.project.session import ProjectSession


@dataclass(frozen=True, slots=True)
class DependentRecalculationReport:
    recalculated_mnemonics: tuple[str, ...]
    failed_mnemonics: tuple[str, ...]


def recalculate_existing_dependents(
    session: ProjectSession,
    dataset: Dataset,
    *,
    formula_registry: FormulaProfileRegistry | None = None,
) -> DependentRecalculationReport:
    """Recalculate derived curves that are already present in the dataset.

    Basic gas-ratio outputs retain the application's historical behaviour: when
    resolvable C1/C2/C3 inputs exist, the complete auditable basic set is kept in
    sync. Profile and custom-formula outputs are recalculated only when the output
    curve already exists, so editing a source curve does not unexpectedly add new
    engineering calculations.
    """

    recalculated: set[str] = set()
    failed: set[str] = set()

    try:
        recalculated.update(session.calculate_basic_gas_ratios())
    except Exception:
        # Gas inputs may not be present in non-gas LAS files. This is not an edit
        # failure and must not block changing drilling or geological parameters.
        pass

    # Re-run profile and custom outputs until no further values change. This
    # supports chains where one calculated output is an input to another.
    calculation_count = sum(
        curve.metadata.provenance.startswith(("calculation:", "custom-formula:"))
        for curve in dataset.curves.values()
    )
    max_passes = max(1, calculation_count + 1)
    for _ in range(max_passes):
        changed = False
        for curve in tuple(dataset.curves.values()):
            provenance = curve.metadata.provenance
            mnemonic = curve.metadata.original_mnemonic
            try:
                values = None
                if provenance.startswith("custom-formula:"):
                    formula_id = provenance.split(":", 2)[1]
                    definition = session.project.custom_formulas.get(formula_id)
                    if definition is None:
                        continue
                    values = calculate_custom_formula(dataset, definition)
                elif provenance.startswith("calculation:") and not provenance.startswith(
                    "calculation:basic-gas-ratio:"
                ):
                    if formula_registry is None:
                        continue
                    profile_id = provenance.split(":", 2)[1]
                    try:
                        passport = formula_registry.passport(profile_id)
                    except KeyError:
                        continue
                    inputs = {}
                    for input_name in passport.required_inputs:
                        input_curve = dataset.curve_by_mnemonic(input_name)
                        if input_curve is None:
                            raise KeyError(input_name)
                        inputs[input_name] = input_curve.values
                    values = formula_registry.calculate(profile_id, inputs)
                if values is None:
                    continue
                normalized = np.asarray(values, dtype=np.float64)
                if normalized.shape != curve.values.shape:
                    raise ValueError("Размер результата не совпадает с кривой")
                if not np.allclose(
                    curve.values,
                    normalized,
                    equal_nan=True,
                    rtol=1e-12,
                    atol=1e-12,
                ):
                    curve.values = normalized.copy()
                    curve.version += 1
                    changed = True
                curve.state = CalculationState.CURRENT
                recalculated.add(mnemonic)
                failed.discard(mnemonic)
            except Exception:
                curve.state = CalculationState.ERROR
                failed.add(mnemonic)
        if not changed:
            break

    session.dirty = True
    return DependentRecalculationReport(
        tuple(sorted(recalculated, key=str.casefold)),
        tuple(sorted(failed, key=str.casefold)),
    )
