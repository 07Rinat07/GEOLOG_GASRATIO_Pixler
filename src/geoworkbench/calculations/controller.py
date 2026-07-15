from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from geoworkbench.calculations.pixler import FormulaProfileRegistry
from geoworkbench.domain.models import CurveData, Dataset
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
        self.session.dirty = True
        return FormulaExecutionResult(profile_id, destination, curve)

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
