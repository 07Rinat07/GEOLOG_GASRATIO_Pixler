from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from geoworkbench.domain.models import CanvasObject, Well


class CanvasHistoryConflictError(RuntimeError):
    """Raised when canvas objects changed outside the recorded history."""


@dataclass(frozen=True, slots=True)
class CanvasSnapshotCommand:
    well: Well
    before: tuple[CanvasObject, ...]
    after: tuple[CanvasObject, ...]
    description: str

    def undo(self) -> None:
        self._restore(expected=self.after, replacement=self.before)

    def redo(self) -> None:
        self._restore(expected=self.before, replacement=self.after)

    def _restore(
        self,
        *,
        expected: tuple[CanvasObject, ...],
        replacement: tuple[CanvasObject, ...],
    ) -> None:
        if self.well.canvas_objects != list(expected):
            raise CanvasHistoryConflictError("Canvas-объекты были изменены вне истории команд")
        self.well.canvas_objects = deepcopy(list(replacement))


@dataclass(slots=True)
class CanvasObjectHistory:
    max_commands: int = 100
    _undo_stack: list[CanvasSnapshotCommand] = field(default_factory=list, init=False)
    _redo_stack: list[CanvasSnapshotCommand] = field(default_factory=list, init=False)

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
        before: list[CanvasObject],
        *,
        description: str,
    ) -> None:
        if not description.strip():
            raise ValueError("Описание команды не может быть пустым")
        after = deepcopy(well.canvas_objects)
        if before == after:
            return
        self._undo_stack.append(
            CanvasSnapshotCommand(
                well=well,
                before=tuple(deepcopy(before)),
                after=tuple(after),
                description=description,
            )
        )
        if len(self._undo_stack) > self.max_commands:
            del self._undo_stack[0]
        self._redo_stack.clear()

    def undo(self) -> CanvasSnapshotCommand:
        if not self._undo_stack:
            raise RuntimeError("Нет операций canvas для отмены")
        command = self._undo_stack[-1]
        command.undo()
        self._undo_stack.pop()
        self._redo_stack.append(command)
        return command

    def redo(self) -> CanvasSnapshotCommand:
        if not self._redo_stack:
            raise RuntimeError("Нет операций canvas для повтора")
        command = self._redo_stack[-1]
        command.redo()
        self._redo_stack.pop()
        self._undo_stack.append(command)
        return command

    def clear(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()
