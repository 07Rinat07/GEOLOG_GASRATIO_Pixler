from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

from geoworkbench.calculations.pixler import FormulaProfileRegistry
from geoworkbench.domain.models import CalculationState, CurveData, Dataset
from geoworkbench.project.session import ProjectSession


_UNIT_ALIASES = {
    "ft/h": {"ft/h", "ft/hr", "fph"},
    "rev/min": {"rev/min", "rpm"},
    "lbf": {"lbf", "lb", "lbs"},
    "in": {"in", "inch", "inches"},
    "ppg": {"ppg", "lb/gal", "lbs/gal"},
    "gpm": {"gpm", "gal/min", "us gal/min"},
    "dimensionless": {"dimensionless", "ratio", "-", "1"},
}


@dataclass(frozen=True, slots=True)
class FormulaExecutionResult:
    profile_id: str
    output_mnemonic: str
    curve: CurveData
    passport: FormulaExecutionPassport


@dataclass(frozen=True, slots=True)
class FormulaInputBinding:
    input_name: str
    expected_unit: str
    mapped_mnemonic: str
    curve_id: str
    actual_unit: str | None
    provenance: str
    state: CalculationState


@dataclass(frozen=True, slots=True)
class FormulaExecutionPassport:
    profile_id: str
    display_name: str
    version: str
    source: str
    expression: str
    inputs: tuple[FormulaInputBinding, ...]
    parameters: tuple[tuple[str, float], ...]
    output_mnemonic: str
    output_curve_id: str
    output_unit: str | None
    output_provenance: str
    output_state: CalculationState


@dataclass(slots=True)
class FormulaExecutionController:
    session: ProjectSession
    registry: FormulaProfileRegistry

    def execute(
        self,
        profile_id: str,
        input_mapping: Mapping[str, str],
        *,
        output_mnemonic: str | None = None,
        parameters: Mapping[str, float] | None = None,
    ) -> FormulaExecutionResult:
        dataset = self._require_dataset()
        passport = self.registry.passport(profile_id)
        normalized_mapping = {name.upper(): mnemonic for name, mnemonic in input_mapping.items()}
        curves: dict[str, CurveData] = {}
        for input_name in passport.required_inputs:
            mnemonic = normalized_mapping.get(input_name.upper())
            if not mnemonic:
                raise KeyError(f"Не задан mapping для входа {input_name}")
            curve = dataset.curve_by_mnemonic(mnemonic)
            if curve is None:
                raise KeyError(f"Кривая mapping отсутствует: {mnemonic}")
            curves[input_name.upper()] = curve

        self._validate_units(passport.input_units, curves)
        destination = (output_mnemonic or passport.output_mnemonic).strip().upper()
        if not destination:
            raise ValueError("Выходная мнемоника не может быть пустой")
        existing = dataset.curve_by_mnemonic(destination)
        if existing is not None and not existing.metadata.provenance.startswith("calculation:"):
            raise ValueError(f"Нельзя перезаписать исходную кривую: {destination}")

        values = self.registry.calculate(
            profile_id,
            {name: curve.values for name, curve in curves.items()},
            parameters,
        )
        curve = dataset.upsert_curve(
            destination,
            values,
            unit=passport.output_unit,
            description=passport.display_name,
            provenance=f"calculation:{profile_id}:{passport.version}",
        )
        curve.metadata = replace(
            curve.metadata,
            canonical_mnemonic=destination,
            unit=passport.output_unit,
            description=passport.display_name,
            provenance=f"calculation:{profile_id}:{passport.version}",
        )
        curve.state = CalculationState.CURRENT
        self.session.dirty = True
        execution_passport = FormulaExecutionPassport(
            profile_id,
            passport.display_name,
            passport.version,
            passport.source,
            passport.expression,
            tuple(
                FormulaInputBinding(
                    input_name,
                    passport.input_units[input_name],
                    curves[input_name].metadata.original_mnemonic,
                    curves[input_name].metadata.curve_id,
                    curves[input_name].metadata.unit,
                    curves[input_name].metadata.provenance,
                    curves[input_name].state,
                )
                for input_name in passport.required_inputs
            ),
            tuple(sorted((name, float(value)) for name, value in (parameters or {}).items())),
            destination,
            curve.metadata.curve_id,
            curve.metadata.unit,
            curve.metadata.provenance,
            curve.state,
        )
        return FormulaExecutionResult(profile_id, destination, curve, execution_passport)

    def _require_dataset(self) -> Dataset:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите набор данных")
        return dataset

    @staticmethod
    def _validate_units(expected_units: Mapping[str, str], curves: Mapping[str, CurveData]) -> None:
        concentration_units: set[str] = set()
        for input_name, curve in curves.items():
            actual = (curve.metadata.unit or "").strip().casefold()
            expected = expected_units[input_name].strip().casefold()
            if expected == "same concentration unit":
                if not actual:
                    raise ValueError(f"Для {input_name} не указана единица концентрации")
                concentration_units.add(actual)
                continue
            accepted = _UNIT_ALIASES.get(expected, {expected})
            if actual not in accepted:
                raise ValueError(
                    f"Некорректная единица {input_name}: ожидалась {expected_units[input_name]}, "
                    f"получена {curve.metadata.unit or 'не указана'}"
                )
        if len(concentration_units) > 1:
            raise ValueError("Газовые компоненты должны иметь одинаковые единицы концентрации")
