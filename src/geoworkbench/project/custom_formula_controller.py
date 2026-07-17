from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace

import numpy as np
from numpy.typing import NDArray

from geoworkbench.calculations.custom_formula import (
    CustomFormulaError,
    calculate_custom_formula,
    evaluate_formula,
    validate_definition,
)
from geoworkbench.domain.models import CustomFormulaDefinition, CurveData, Dataset
from geoworkbench.project.session import ProjectSession


@dataclass(frozen=True, slots=True)
class FormulaBatchPreview:
    formula_id: str
    name: str
    output_mnemonic: str
    finite_count: int
    minimum: float | None
    maximum: float | None
    changed_count: int


@dataclass(frozen=True, slots=True)
class FormulaBatchPlan:
    dataset_id: str
    curve_versions: tuple[tuple[str, int], ...]
    formula_versions: tuple[tuple[str, int], ...]
    ordered_formula_ids: tuple[str, ...]
    previews: tuple[FormulaBatchPreview, ...]
    values: tuple[NDArray[np.float64], ...]


@dataclass(slots=True)
class _FormulaBatchCommand:
    dataset_id: str
    before: dict[str, CurveData | None]
    after: dict[str, CurveData]
    formula_versions: tuple[tuple[str, int], ...]
    applied: bool = True
    redo_curve_versions: tuple[tuple[str, int], ...] = ()


class CustomFormulaController:
    def __init__(self, session: ProjectSession) -> None:
        self.session = session
        self._batch_command: _FormulaBatchCommand | None = None

    @property
    def can_undo_batch(self) -> bool:
        command = self._batch_command
        dataset = self.session.current_dataset
        return bool(
            command is not None
            and command.applied
            and dataset is not None
            and dataset.dataset_id == command.dataset_id
        )

    @property
    def can_redo_batch(self) -> bool:
        command = self._batch_command
        dataset = self.session.current_dataset
        return bool(
            command is not None
            and not command.applied
            and dataset is not None
            and dataset.dataset_id == command.dataset_id
        )

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

    def analyze_batch(self) -> FormulaBatchPlan:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите набор данных")
        formulas = self.session.project.custom_formulas
        if not formulas:
            raise CustomFormulaError("В проекте нет сохранённых пользовательских формул")
        by_output: dict[str, CustomFormulaDefinition] = {}
        inputs_by_id: dict[str, tuple[str, ...]] = {}
        for definition in formulas.values():
            inputs = validate_definition(definition)
            output = definition.output_mnemonic.strip().upper()
            if output in by_output:
                raise CustomFormulaError(f"Несколько формул создают кривую {output}")
            existing = dataset.curve_by_mnemonic(output)
            if existing is not None and not existing.metadata.provenance.startswith(
                "custom-formula:"
            ):
                raise CustomFormulaError(f"Нельзя перезаписать исходную кривую: {output}")
            by_output[output] = definition
            inputs_by_id[definition.formula_id] = inputs

        ordered = _formula_order(by_output, inputs_by_id)
        available = {
            curve.metadata.original_mnemonic.strip().upper(): np.asarray(
                curve.values, dtype=np.float64
            )
            for curve in dataset.curves.values()
        }
        previews: list[FormulaBatchPreview] = []
        results: list[NDArray[np.float64]] = []
        for definition in ordered:
            inputs = inputs_by_id[definition.formula_id]
            missing = [mnemonic for mnemonic in inputs if mnemonic not in available]
            if missing:
                raise CustomFormulaError(
                    f"Формула {definition.name}: отсутствуют входные кривые "
                    f"{', '.join(missing)}"
                )
            values = evaluate_formula(
                definition.expression, {name: available[name] for name in inputs}
            )
            output = definition.output_mnemonic.strip().upper()
            previous = available.get(output)
            changed = (
                values.size
                if previous is None
                else int(
                    np.count_nonzero(
                        ~np.isclose(values, previous, equal_nan=True, rtol=1e-12, atol=1e-12)
                    )
                )
            )
            finite = values[np.isfinite(values)]
            previews.append(
                FormulaBatchPreview(
                    definition.formula_id,
                    definition.name,
                    output,
                    int(finite.size),
                    float(np.min(finite)) if finite.size else None,
                    float(np.max(finite)) if finite.size else None,
                    changed,
                )
            )
            stored_values = np.asarray(values, dtype=np.float64).copy()
            stored_values.setflags(write=False)
            results.append(stored_values)
            available[output] = stored_values
        return FormulaBatchPlan(
            dataset.dataset_id,
            tuple(sorted((curve_id, curve.version) for curve_id, curve in dataset.curves.items())),
            tuple(sorted((item.formula_id, item.version) for item in formulas.values())),
            tuple(item.formula_id for item in ordered),
            tuple(previews),
            tuple(results),
        )

    def apply_batch(self, plan: FormulaBatchPlan) -> tuple[CurveData, ...]:
        dataset = self.session.current_dataset
        if dataset is None or dataset.dataset_id != plan.dataset_id:
            raise RuntimeError("Dataset изменился после предварительного анализа формул")
        curve_versions = tuple(
            sorted((curve_id, curve.version) for curve_id, curve in dataset.curves.items())
        )
        formula_versions = tuple(
            sorted(
                (item.formula_id, item.version)
                for item in self.session.project.custom_formulas.values()
            )
        )
        if curve_versions != plan.curve_versions or formula_versions != plan.formula_versions:
            raise RuntimeError("Данные или формулы изменились после предварительного анализа")
        before = {
            preview.output_mnemonic: deepcopy(
                dataset.curve_by_mnemonic(preview.output_mnemonic)
            )
            for preview in plan.previews
        }
        results: list[CurveData] = []
        for formula_id, values in zip(plan.ordered_formula_ids, plan.values, strict=True):
            definition = self.session.project.custom_formulas[formula_id]
            results.append(
                dataset.upsert_curve(
                    definition.output_mnemonic.strip().upper(),
                    np.asarray(values, dtype=np.float64).copy(),
                    unit=definition.output_unit,
                    description=definition.name,
                    provenance=f"custom-formula:{definition.formula_id}:{definition.version}",
                )
            )
        self._batch_command = _FormulaBatchCommand(
            dataset.dataset_id,
            before,
            {
                curve.metadata.original_mnemonic.strip().upper(): deepcopy(curve)
                for curve in results
            },
            formula_versions,
        )
        self.session.dirty = True
        return tuple(results)

    def undo_batch(self) -> None:
        command, dataset = self._batch_history(applied=True)
        for mnemonic, expected in command.after.items():
            current = dataset.curve_by_mnemonic(mnemonic)
            if current is None or not _same_curve(current, expected):
                raise RuntimeError(
                    f"Кривая {mnemonic} изменилась после массового пересчёта; Undo заблокирован"
                )
        for mnemonic, snapshot in command.before.items():
            current = dataset.curve_by_mnemonic(mnemonic)
            if current is not None:
                del dataset.curves[current.metadata.curve_id]
            if snapshot is not None:
                dataset.curves[snapshot.metadata.curve_id] = deepcopy(snapshot)
        command.applied = False
        command.redo_curve_versions = _curve_versions(dataset)
        self.session.dirty = True

    def redo_batch(self) -> tuple[CurveData, ...]:
        command, dataset = self._batch_history(applied=False)
        if (
            _curve_versions(dataset) != command.redo_curve_versions
            or _formula_versions(self.session) != command.formula_versions
        ):
            raise RuntimeError("Данные или формулы изменились после Undo; Redo заблокирован")
        restored: list[CurveData] = []
        for mnemonic, snapshot in command.after.items():
            current = dataset.curve_by_mnemonic(mnemonic)
            if current is not None:
                del dataset.curves[current.metadata.curve_id]
            curve = deepcopy(snapshot)
            dataset.curves[curve.metadata.curve_id] = curve
            restored.append(curve)
        command.applied = True
        self.session.dirty = True
        return tuple(restored)

    def clear_history(self) -> None:
        self._batch_command = None

    def _batch_history(self, *, applied: bool) -> tuple[_FormulaBatchCommand, Dataset]:
        command = self._batch_command
        dataset = self.session.current_dataset
        if (
            command is None
            or command.applied is not applied
            or dataset is None
            or dataset.dataset_id != command.dataset_id
        ):
            action = "отмены" if applied else "повтора"
            raise RuntimeError(f"Нет массового пересчёта формул для {action}")
        return command, dataset


def _formula_order(
    by_output: dict[str, CustomFormulaDefinition],
    inputs_by_id: dict[str, tuple[str, ...]],
) -> tuple[CustomFormulaDefinition, ...]:
    dependencies = {
        definition.formula_id: {
            by_output[mnemonic].formula_id
            for mnemonic in inputs_by_id[definition.formula_id]
            if mnemonic in by_output
        }
        for definition in by_output.values()
    }
    ordered: list[CustomFormulaDefinition] = []
    remaining = dict(dependencies)
    while remaining:
        ready = sorted(formula_id for formula_id, required in remaining.items() if not required)
        if not ready:
            raise CustomFormulaError("Пользовательские формулы содержат циклическую зависимость")
        for formula_id in ready:
            ordered.append(
                next(item for item in by_output.values() if item.formula_id == formula_id)
            )
            del remaining[formula_id]
        for required in remaining.values():
            required.difference_update(ready)
    return tuple(ordered)


def _curve_versions(dataset: Dataset) -> tuple[tuple[str, int], ...]:
    return tuple(sorted((curve_id, curve.version) for curve_id, curve in dataset.curves.items()))


def _formula_versions(session: ProjectSession) -> tuple[tuple[str, int], ...]:
    return tuple(
        sorted(
            (item.formula_id, item.version)
            for item in session.project.custom_formulas.values()
        )
    )


def _same_curve(current: CurveData, expected: CurveData) -> bool:
    return (
        current.metadata == expected.metadata
        and current.version == expected.version
        and current.state == expected.state
        and np.array_equal(current.values, expected.values, equal_nan=True)
    )
