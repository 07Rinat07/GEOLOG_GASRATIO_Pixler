from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

import numpy as np

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, new_id
from geoworkbench.project.session import ProjectSession


@dataclass(frozen=True, slots=True)
class CurveMetadataCommand:
    dataset_id: str
    curve: CurveData
    before: CurveMetadata
    after: CurveMetadata
    description: str


@dataclass(frozen=True, slots=True)
class CurveCreationCommand:
    dataset_id: str
    curve: CurveData
    description: str


@dataclass(frozen=True, slots=True)
class CurveRemovalCommand:
    dataset_id: str
    curve: CurveData
    position: int
    description: str


CurveCatalogCommand = CurveMetadataCommand | CurveCreationCommand | CurveRemovalCommand


@dataclass(slots=True)
class CurveMetadataController:
    session: ProjectSession
    max_commands: int = 100
    _undo_stack: list[CurveCatalogCommand] = field(default_factory=list, init=False)
    _redo_stack: list[CurveCatalogCommand] = field(default_factory=list, init=False)

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

    def create(self, *, mnemonic: str, unit: str, description: str) -> CurveData:
        dataset = self._dataset()
        normalized_mnemonic = mnemonic.strip().upper()
        normalized_unit = unit.strip() or None
        normalized_description = description.strip() or None
        self._validate(
            dataset,
            None,
            normalized_mnemonic,
            normalized_unit,
            normalized_description,
        )
        curve_id = new_id()
        curve = CurveData(
            CurveMetadata(
                curve_id=curve_id,
                original_mnemonic=normalized_mnemonic,
                canonical_mnemonic=None,
                unit=normalized_unit,
                description=normalized_description,
                source_dataset_id=dataset.dataset_id,
                provenance="user",
            ),
            np.full(dataset.depth.shape, np.nan, dtype=np.float64),
        )
        dataset.curves[curve_id] = curve
        self._undo_stack.append(
            CurveCreationCommand(
                dataset.dataset_id,
                curve,
                f"Создание кривой {normalized_mnemonic}",
            )
        )
        if len(self._undo_stack) > self.max_commands:
            del self._undo_stack[0]
        self._redo_stack.clear()
        self.session.dirty = True
        return curve

    def remove(self, curve_id: str) -> CurveData:
        dataset = self._dataset()
        curve = self._curve(dataset, curve_id)
        if curve.metadata.provenance != "user":
            raise ValueError(
                "Удалять можно только кривые, созданные пользователем в текущем проекте"
            )
        position = list(dataset.curves).index(curve_id)
        del dataset.curves[curve_id]
        self._undo_stack.append(
            CurveRemovalCommand(
                dataset.dataset_id,
                curve,
                position,
                f"Удаление кривой {curve.metadata.original_mnemonic}",
            )
        )
        if len(self._undo_stack) > self.max_commands:
            del self._undo_stack[0]
        self._redo_stack.clear()
        self.session.dirty = True
        return curve

    def undo(self) -> str:
        if not self._undo_stack:
            raise RuntimeError("Нет изменений метаданных кривых для отмены")
        command = self._undo_stack[-1]
        self._require_current_command_dataset(command)
        if isinstance(command, CurveMetadataCommand):
            self._restore(command.curve, command.after, command.before)
        elif isinstance(command, CurveCreationCommand):
            self._remove_created_curve(command)
        else:
            self._restore_removed_curve(command)
        self._undo_stack.pop()
        self._redo_stack.append(command)
        self.session.dirty = True
        return command.description

    def redo(self) -> str:
        if not self._redo_stack:
            raise RuntimeError("Нет изменений метаданных кривых для повтора")
        command = self._redo_stack[-1]
        self._require_current_command_dataset(command)
        if isinstance(command, CurveMetadataCommand):
            self._restore(command.curve, command.before, command.after)
        elif isinstance(command, CurveCreationCommand):
            self._restore_created_curve(command)
        else:
            self._remove_again(command)
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
        curve: CurveData | None,
        mnemonic: str,
        unit: str | None,
        description: str | None,
    ) -> None:
        if not self._MNEMONIC.fullmatch(mnemonic):
            raise ValueError("Мнемоника: A–Z, затем A–Z, 0–9, '_' или '-', максимум 32 символа")
        reserved = {"dept"} | {
            index.mnemonic.casefold() for index in dataset.indexes.values()
        }
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

    def _require_current_command_dataset(self, command: CurveCatalogCommand) -> None:
        if self._dataset().dataset_id != command.dataset_id:
            raise RuntimeError("История относится к другому dataset")

    @staticmethod
    def _restore(curve: CurveData, expected: CurveMetadata, replacement: CurveMetadata) -> None:
        if curve.metadata != expected:
            raise RuntimeError("Метаданные кривой были изменены вне истории команд")
        curve.metadata = replacement

    def _remove_created_curve(self, command: CurveCreationCommand) -> None:
        dataset = self._dataset()
        if dataset.curves.get(command.curve.metadata.curve_id) is not command.curve:
            raise RuntimeError("Созданная кривая была изменена вне истории команд")
        if command.curve.version != 1 or not np.all(np.isnan(command.curve.values)):
            raise RuntimeError(
                "Кривая уже содержит пользовательские правки и не может быть удалена через Undo"
            )
        del dataset.curves[command.curve.metadata.curve_id]

    def _restore_created_curve(self, command: CurveCreationCommand) -> None:
        dataset = self._dataset()
        curve_id = command.curve.metadata.curve_id
        if curve_id in dataset.curves:
            raise RuntimeError("Идентификатор созданной кривой уже занят")
        self._validate(
            dataset,
            None,
            command.curve.metadata.original_mnemonic,
            command.curve.metadata.unit,
            command.curve.metadata.description,
        )
        dataset.curves[curve_id] = command.curve

    def _restore_removed_curve(self, command: CurveRemovalCommand) -> None:
        dataset = self._dataset()
        curve_id = command.curve.metadata.curve_id
        if curve_id in dataset.curves:
            raise RuntimeError("Идентификатор удалённой кривой уже занят")
        items = list(dataset.curves.items())
        items.insert(command.position, (curve_id, command.curve))
        dataset.curves = dict(items)

    def _remove_again(self, command: CurveRemovalCommand) -> None:
        dataset = self._dataset()
        curve_id = command.curve.metadata.curve_id
        if dataset.curves.get(curve_id) is not command.curve:
            raise RuntimeError("Удалённая кривая была изменена вне истории команд")
        del dataset.curves[curve_id]

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
