from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset
from geoworkbench.project.session import ProjectSession


@dataclass(frozen=True, slots=True)
class CurveMetadataCommand:
    dataset_id: str
    curve: CurveData
    before: CurveMetadata
    after: CurveMetadata
    description: str


@dataclass(slots=True)
class CurveMetadataController:
    session: ProjectSession
    max_commands: int = 100
    _undo_stack: list[CurveMetadataCommand] = field(default_factory=list, init=False)
    _redo_stack: list[CurveMetadataCommand] = field(default_factory=list, init=False)

    _MNEMONIC = re.compile(r"^[A-Z][A-Z0-9_-]{0,31}$")

    def __post_init__(self) -> None:
        if self.max_commands < 1:
            raise ValueError("История должна хранить минимум одну команду")

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def update(
        self,
        curve_id: str,
        *,
        mnemonic: str,
        unit: str,
        description: str,
    ) -> None:
        dataset = self._dataset()
        curve = self._curve(dataset, curve_id)
        normalized_mnemonic = mnemonic.strip().upper()
        normalized_unit = unit.strip() or None
        normalized_description = description.strip() or None
        self._validate(dataset, curve, normalized_mnemonic, normalized_unit, normalized_description)
        before = curve.metadata
        after = replace(
            before,
            original_mnemonic=normalized_mnemonic,
            unit=normalized_unit,
            description=normalized_description,
        )
        if before == after:
            return
        curve.metadata = after
        self._undo_stack.append(
            CurveMetadataCommand(
                dataset.dataset_id,
                curve,
                before,
                after,
                f"Изменение метаданных {before.original_mnemonic}",
            )
        )
        if len(self._undo_stack) > self.max_commands:
            del self._undo_stack[0]
        self._redo_stack.clear()
        self.session.dirty = True

    def undo(self) -> str:
        if not self._undo_stack:
            raise RuntimeError("Нет изменений метаданных кривых для отмены")
        command = self._undo_stack[-1]
        self._require_current_command_dataset(command)
        self._restore(command.curve, command.after, command.before)
        self._undo_stack.pop()
        self._redo_stack.append(command)
        self.session.dirty = True
        return command.description

    def redo(self) -> str:
        if not self._redo_stack:
            raise RuntimeError("Нет изменений метаданных кривых для повтора")
        command = self._redo_stack[-1]
        self._require_current_command_dataset(command)
        self._restore(command.curve, command.before, command.after)
        self._redo_stack.pop()
        self._undo_stack.append(command)
        self.session.dirty = True
        return command.description

    def clear_history(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()

    def _validate(
        self,
        dataset: Dataset,
        curve: CurveData,
        mnemonic: str,
        unit: str | None,
        description: str | None,
    ) -> None:
        if not self._MNEMONIC.fullmatch(mnemonic):
            raise ValueError("Мнемоника: A–Z, затем A–Z, 0–9, '_' или '-', максимум 32 символа")
        reserved = {index.mnemonic.casefold() for index in dataset.indexes.values()}
        if mnemonic.casefold() in reserved:
            raise ValueError(f"Мнемоника зарезервирована индексом dataset: {mnemonic}")
        for existing in dataset.curves.values():
            if existing is not curve and existing.metadata.original_mnemonic.casefold() == mnemonic.casefold():
                raise ValueError(f"Кривая с мнемоникой {mnemonic} уже существует")
        if unit is not None:
            if len(unit) > 32:
                raise ValueError("Единица измерения не должна превышать 32 символа")
            if any(character.isspace() or ord(character) < 32 for character in unit):
                raise ValueError("Единица измерения не должна содержать пробелы или управляющие символы")
        if description is not None and len(description) > 500:
            raise ValueError("Описание не должно превышать 500 символов")

    def _require_current_command_dataset(self, command: CurveMetadataCommand) -> None:
        if self._dataset().dataset_id != command.dataset_id:
            raise RuntimeError("История относится к другому dataset")

    @staticmethod
    def _restore(curve: CurveData, expected: CurveMetadata, replacement: CurveMetadata) -> None:
        if curve.metadata != expected:
            raise RuntimeError("Метаданные кривой были изменены вне истории команд")
        curve.metadata = replacement

    @staticmethod
    def _curve(dataset: Dataset, curve_id: str) -> CurveData:
        try:
            return dataset.curves[curve_id]
        except KeyError as exc:
            raise KeyError(f"Кривая не найдена: {curve_id}") from exc

    def _dataset(self) -> Dataset:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите dataset")
        return dataset
