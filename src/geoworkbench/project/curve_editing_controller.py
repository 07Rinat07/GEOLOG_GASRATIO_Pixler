from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import numpy as np
from numpy.typing import NDArray

from geoworkbench.domain.models import CalculationState, CurveData, Dataset
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.dependency_graph import DependencyGraph
from geoworkbench.services.edit_history import CurveEditCommand, CurveEditHistory
from geoworkbench.services.dependent_recalculation import recalculate_existing_dependents

if TYPE_CHECKING:
    from geoworkbench.calculations.pixler import FormulaProfileRegistry


@dataclass(frozen=True, slots=True)
class CurveEditOutcome:
    operation: Literal["edit", "undo", "redo"]
    dataset_id: str
    curve_id: str
    mnemonic: str
    affected_mnemonics: tuple[str, ...]
    recalculated_mnemonics: tuple[str, ...] = ()
    failed_mnemonics: tuple[str, ...] = ()


@dataclass(slots=True)
class CurveEditingController:
    """Application workflows for curve edits and dependent calculation states."""

    session: ProjectSession
    dependency_graph: DependencyGraph = field(default_factory=DependencyGraph)
    history: CurveEditHistory = field(default_factory=CurveEditHistory)
    formula_registry: "FormulaProfileRegistry | None" = None

    def edit_curve(
        self,
        curve_id: str,
        indices: NDArray[np.int64],
        new_values: NDArray[np.float64],
        *,
        description: str = "Редактирование кривой",
    ) -> CurveEditOutcome:
        dataset = self._require_current_dataset()
        curve = dataset.curves.get(curve_id)
        if curve is None:
            raise KeyError(f"Кривая не найдена: {curve_id}")
        command = CurveEditCommand.create(
            curve,
            indices,
            new_values,
            description=description,
        )
        self.history.execute(command)
        return self._after_change("edit", dataset, curve)

    def undo(self) -> CurveEditOutcome:
        command = self.history.undo()
        dataset = self._dataset_for_curve(command.curve)
        return self._after_change("undo", dataset, command.curve)

    def redo(self) -> CurveEditOutcome:
        command = self.history.redo()
        dataset = self._dataset_for_curve(command.curve)
        return self._after_change("redo", dataset, command.curve)

    def clear_history(self) -> None:
        self.history.clear()

    def _after_change(
        self,
        operation: Literal["edit", "undo", "redo"],
        dataset: Dataset,
        curve: CurveData,
    ) -> CurveEditOutcome:
        source_names = {curve.metadata.original_mnemonic}
        if curve.metadata.canonical_mnemonic:
            source_names.add(curve.metadata.canonical_mnemonic)
        affected = tuple(sorted(set(self.dependency_graph.affected_outputs(source_names))))
        for mnemonic in affected:
            dependent = dataset.curve_by_mnemonic(mnemonic)
            if dependent is not None and dependent is not curve:
                dependent.state = CalculationState.STALE
        report = recalculate_existing_dependents(
            self.session,
            dataset,
            formula_registry=self.formula_registry,
        )
        # Pencil/table edits modify only the in-memory project model.  Mark the
        # session dirty so the title shows ``*`` and the data are written only
        # after the user explicitly presses Save.
        self.session.dirty = True
        return CurveEditOutcome(
            operation=operation,
            dataset_id=dataset.dataset_id,
            curve_id=curve.metadata.curve_id,
            mnemonic=curve.metadata.original_mnemonic,
            affected_mnemonics=affected,
            recalculated_mnemonics=report.recalculated_mnemonics,
            failed_mnemonics=report.failed_mnemonics,
        )

    def _require_current_dataset(self) -> Dataset:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите набор данных")
        return dataset

    def _dataset_for_curve(self, curve: CurveData) -> Dataset:
        for well in self.session.project.wells.values():
            dataset = well.datasets.get(curve.metadata.source_dataset_id)
            if dataset is not None and dataset.curves.get(curve.metadata.curve_id) is curve:
                return dataset
        raise RuntimeError("Набор отредактированной кривой больше не существует")
