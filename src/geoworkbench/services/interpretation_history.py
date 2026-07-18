from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from geoworkbench.domain.models import Well, WellInterpretation


class InterpretationHistoryConflictError(RuntimeError):
    """Raised when interpretations changed outside the recorded command history."""


@dataclass(frozen=True, slots=True)
class InterpretationSnapshotCommand:
    well: Well
    before: dict[str, WellInterpretation]
    after: dict[str, WellInterpretation]
    description: str

    def undo(self) -> None:
        self._restore(expected=self.after, replacement=self.before)

    def redo(self) -> None:
        self._restore(expected=self.before, replacement=self.after)

    def _restore(
        self,
        *,
        expected: dict[str, WellInterpretation],
        replacement: dict[str, WellInterpretation],
    ) -> None:
        if self.well.interpretations != expected:
            raise InterpretationHistoryConflictError(
                "Интерпретации были изменены вне истории команд"
            )
        self.well.interpretations = deepcopy(replacement)


@dataclass(slots=True)
class InterpretationHistory:
    max_commands: int = 100
    _undo_stack: list[InterpretationSnapshotCommand] = field(default_factory=list, init=False)
    _redo_stack: list[InterpretationSnapshotCommand] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        if self.max_commands < 1:
            raise ValueError("История должна хранить минимум одну команду")

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def record(
        self,
        well: Well,
        before: dict[str, WellInterpretation],
        *,
        description: str,
    ) -> None:
        if not description.strip():
            raise ValueError("Описание команды не может быть пустым")
        after = deepcopy(well.interpretations)
        if before == after:
            return
        self._undo_stack.append(
            InterpretationSnapshotCommand(
                well=well,
                before=deepcopy(before),
                after=after,
                description=description,
            )
        )
        if len(self._undo_stack) > self.max_commands:
            del self._undo_stack[0]
        self._redo_stack.clear()

    def undo(self) -> InterpretationSnapshotCommand:
        if not self._undo_stack:
            raise RuntimeError("Нет операций интерпретации для отмены")
        command = self._undo_stack[-1]
        command.undo()
        self._undo_stack.pop()
        self._redo_stack.append(command)
        return command

    def redo(self) -> InterpretationSnapshotCommand:
        if not self._redo_stack:
            raise RuntimeError("Нет операций интерпретации для повтора")
        command = self._redo_stack[-1]
        command.redo()
        self._redo_stack.pop()
        self._undo_stack.append(command)
        return command

    def clear(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()
