from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from geoworkbench.domain.models import CalculationState, CurveData


class CurveEditConflictError(RuntimeError):
    """Raised when curve values changed outside the command history."""


@dataclass(slots=True)
class CurveEditCommand:
    curve: CurveData
    indices: NDArray[np.int64]
    before_values: NDArray[np.float64]
    after_values: NDArray[np.float64]
    description: str = "Редактирование кривой"
    _applied: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        self.indices = np.asarray(self.indices, dtype=np.int64).copy()
        self.before_values = np.asarray(self.before_values, dtype=np.float64).copy()
        self.after_values = np.asarray(self.after_values, dtype=np.float64).copy()
        if self.indices.ndim != 1:
            raise ValueError("Индексы редактирования должны быть одномерными")
        if self.indices.size == 0:
            raise ValueError("Команда редактирования не может быть пустой")
        if self.before_values.shape != self.indices.shape or self.after_values.shape != self.indices.shape:
            raise ValueError("Количество индексов и значений должно совпадать")
        if np.unique(self.indices).size != self.indices.size:
            raise ValueError("Индексы редактирования не должны повторяться")
        if np.any(self.indices < 0) or np.any(self.indices >= self.curve.values.size):
            raise IndexError("Индекс редактирования выходит за границы кривой")
        if not self.description.strip():
            raise ValueError("Описание команды не может быть пустым")

    @classmethod
    def create(
        cls,
        curve: CurveData,
        indices: NDArray[np.int64],
        new_values: NDArray[np.float64],
        *,
        description: str = "Редактирование кривой",
    ) -> CurveEditCommand:
        normalized_indices = np.asarray(indices, dtype=np.int64)
        if normalized_indices.ndim != 1:
            raise ValueError("Индексы редактирования должны быть одномерными")
        if np.any(normalized_indices < 0) or np.any(normalized_indices >= curve.values.size):
            raise IndexError("Индекс редактирования выходит за границы кривой")
        return cls(
            curve=curve,
            indices=normalized_indices,
            before_values=np.asarray(curve.values[normalized_indices], dtype=np.float64),
            after_values=np.asarray(new_values, dtype=np.float64),
            description=description,
        )

    def execute(self) -> None:
        if self._applied:
            raise RuntimeError("Команда уже выполнена")
        self._assert_values(self.before_values)
        self._write(self.after_values)
        self._applied = True

    def undo(self) -> None:
        if not self._applied:
            raise RuntimeError("Команда ещё не выполнена")
        self._assert_values(self.after_values)
        self._write(self.before_values)
        self._applied = False

    def _assert_values(self, expected: NDArray[np.float64]) -> None:
        current = self.curve.values[self.indices]
        if not np.array_equal(current, expected, equal_nan=True):
            raise CurveEditConflictError("Кривая была изменена вне истории команд")

    def _write(self, values: NDArray[np.float64]) -> None:
        self.curve.values[self.indices] = values
        self.curve.version += 1
        self.curve.state = CalculationState.CURRENT


@dataclass(slots=True)
class CurveEditHistory:
    max_commands: int = 100
    _undo_stack: list[CurveEditCommand] = field(default_factory=list, init=False)
    _redo_stack: list[CurveEditCommand] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        if self.max_commands < 1:
            raise ValueError("История должна хранить минимум одну команду")

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def execute(self, command: CurveEditCommand) -> None:
        command.execute()
        self._undo_stack.append(command)
        if len(self._undo_stack) > self.max_commands:
            del self._undo_stack[0]
        self._redo_stack.clear()

    def undo(self) -> CurveEditCommand:
        if not self._undo_stack:
            raise RuntimeError("Нет команд для отмены")
        command = self._undo_stack[-1]
        command.undo()
        self._undo_stack.pop()
        self._redo_stack.append(command)
        return command

    def redo(self) -> CurveEditCommand:
        if not self._redo_stack:
            raise RuntimeError("Нет команд для повтора")
        command = self._redo_stack[-1]
        command.execute()
        self._redo_stack.pop()
        self._undo_stack.append(command)
        return command

    def clear(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()
