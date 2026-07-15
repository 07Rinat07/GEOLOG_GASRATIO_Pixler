from __future__ import annotations

from dataclasses import replace

from geoworkbench.calculations.custom_formula import calculate_custom_formula, validate_definition
from geoworkbench.domain.models import CustomFormulaDefinition, CurveData
from geoworkbench.project.session import ProjectSession


class CustomFormulaController:
    def __init__(self, session: ProjectSession) -> None:
        self.session = session

    def save(self, definition: CustomFormulaDefinition) -> CustomFormulaDefinition:
        validate_definition(definition)
        formulas = self.session.project.custom_formulas
        previous = formulas.get(definition.formula_id)
        stored = replace(definition, version=(previous.version + 1 if previous else 1))
        formulas[stored.formula_id] = stored
        self.session.dirty = True
        return stored

    def delete(self, formula_id: str) -> None:
        if formula_id not in self.session.project.custom_formulas:
            raise KeyError(f"Неизвестная формула: {formula_id}")
        del self.session.project.custom_formulas[formula_id]
        self.session.dirty = True

    def calculate(self, formula_id: str) -> CurveData:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите набор данных")
        try:
            definition = self.session.project.custom_formulas[formula_id]
        except KeyError as exc:
            raise KeyError(f"Неизвестная формула: {formula_id}") from exc
        destination = definition.output_mnemonic.strip().upper()
        existing = dataset.curve_by_mnemonic(destination)
        if existing is not None and not existing.metadata.provenance.startswith("custom-formula:"):
            raise ValueError(f"Нельзя перезаписать исходную кривую: {destination}")
        values = calculate_custom_formula(dataset, definition)
        curve = dataset.upsert_curve(
            destination,
            values,
            unit=definition.output_unit,
            description=definition.name,
            provenance=f"custom-formula:{definition.formula_id}:{definition.version}",
        )
        self.session.dirty = True
        return curve
