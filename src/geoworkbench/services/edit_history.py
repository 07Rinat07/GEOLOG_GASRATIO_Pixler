from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol, cast

import numpy as np
from numpy.typing import NDArray

from geoworkbench.domain.models import CalculationState, CurveData


class UndoableCommand(Protocol):
    """A reversible application command stored by :class:`CommandHistory`."""

    @property
    def description(self) -> str: ...

    @property
    def history_domain(self) -> str: ...

    def execute(self) -> None: ...

    def undo(self) -> None: ...


HistoryListener = Callable[[], None]


@dataclass(slots=True)
class CommandHistory:
    """Bounded chronological history shared by reversible project edits.

    Stack mutations happen only after the command itself succeeds.  This keeps
    failed execute/undo/redo operations from corrupting history order.  A new
    edit always invalidates the complete redo branch, even when the new command
    belongs to another editing domain.
    """

    max_commands: int = 100
    _undo_stack: list[UndoableCommand] = field(default_factory=list, init=False)
    _redo_stack: list[UndoableCommand] = field(default_factory=list, init=False)
    _listeners: list[HistoryListener] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.max_commands < 1:
            raise ValueError("История должна хранить минимум одну команду")

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    @property
    def next_undo(self) -> UndoableCommand | None:
        return self._undo_stack[-1] if self._undo_stack else None

    @property
    def next_redo(self) -> UndoableCommand | None:
        return self._redo_stack[-1] if self._redo_stack else None

    def execute(self, command: UndoableCommand) -> None:
        command.execute()
        self._append_undo(command)
        self._redo_stack.clear()
        self._notify()

    def record_applied(self, command: UndoableCommand) -> None:
        """Record a command whose forward mutation was already committed.

        This supports snapshot-based editors that must validate and materialize
        their post-state before a reversible command can be constructed.
        """

        self._append_undo(command)
        self._redo_stack.clear()
        self._notify()

    def undo(self) -> UndoableCommand:
        if not self._undo_stack:
            raise RuntimeError("Нет команд для отмены")
        command = self._undo_stack[-1]
        command.undo()
        self._undo_stack.pop()
        self._redo_stack.append(command)
        self._notify()
        return command

    def redo(self) -> UndoableCommand:
        if not self._redo_stack:
            raise RuntimeError("Нет команд для повтора")
        command = self._redo_stack[-1]
        command.execute()
        self._redo_stack.pop()
        self._append_undo(command)
        self._notify()
        return command

    def clear(self) -> None:
        changed = bool(self._undo_stack or self._redo_stack)
        self._undo_stack.clear()
        self._redo_stack.clear()
        if changed:
            self._notify()

    def add_listener(self, listener: HistoryListener) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: HistoryListener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _append_undo(self, command: UndoableCommand) -> None:
        self._undo_stack.append(command)
        if len(self._undo_stack) > self.max_commands:
            del self._undo_stack[0]

    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()


class CurveEditConflictError(RuntimeError):
    """Raised when curve values changed outside the command history."""


@dataclass(slots=True)
class CurveEditCommand:
    curve: CurveData
    indices: NDArray[np.int64]
    before_values: NDArray[np.float64]
    after_values: NDArray[np.float64]
    description: str = "Редактирование кривой"
    history_domain: str = field(default="curve", init=False, repr=False)
    _applied: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        self.indices = np.asarray(self.indices, dtype=np.int64).copy()
        self.before_values = np.asarray(self.before_values, dtype=np.float64).copy()
        self.after_values = np.asarray(self.after_values, dtype=np.float64).copy()
        if self.indices.ndim != 1:
            raise ValueError("Индексы редактирования должны быть одномерными")
        if self.indices.size == 0:
            raise ValueError("Команда редактирования не может быть пустой")
        if (
            self.before_values.shape != self.indices.shape
            or self.after_values.shape != self.indices.shape
        ):
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


class CurveEditHistory(CommandHistory):
    """Compatibility facade for callers that still expect curve-only history."""

    def undo(self) -> CurveEditCommand:
        return cast(CurveEditCommand, super().undo())

    def redo(self) -> CurveEditCommand:
        return cast(CurveEditCommand, super().redo())
