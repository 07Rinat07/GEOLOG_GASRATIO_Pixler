from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Callable

from geoworkbench.domain.models import Dataset, Well
from geoworkbench.project.session import ProjectSession


class HeaderSection(StrEnum):
    WELL = "WELL"
    PARAMETER = "PARAMETER"


@dataclass(frozen=True, slots=True)
class HeaderEntry:
    mnemonic: str
    value: str
    protected: bool = False


@dataclass(frozen=True, slots=True)
class _HeaderSnapshot:
    well_id: str
    dataset_id: str
    headers: tuple[tuple[str, str], ...]
    parameters: tuple[tuple[str, str], ...]
    well_name: str


@dataclass(frozen=True, slots=True)
class _HeaderCommand:
    before: _HeaderSnapshot
    after: _HeaderSnapshot
    description: str


@dataclass(slots=True)
class HeaderEditingController:
    session: ProjectSession
    max_commands: int = 100
    _undo_stack: list[_HeaderCommand] = field(default_factory=list, init=False)
    _redo_stack: list[_HeaderCommand] = field(default_factory=list, init=False)

    _MNEMONIC = re.compile(r"^[A-Z][A-Z0-9_-]{0,31}$")
    _PROTECTED = frozenset({"STRT", "STOP", "STEP", "NULL"})
    _LATITUDE = frozenset({"LAT", "LATI", "LATITUDE"})
    _LONGITUDE = frozenset({"LON", "LONG", "LONGITUDE"})

    def __post_init__(self) -> None:
        if self.max_commands < 1:
            raise ValueError("История должна хранить минимум одну команду")

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def entries(self, section: HeaderSection) -> tuple[HeaderEntry, ...]:
        values = self._values(section)
        return tuple(
            HeaderEntry(key, value, section is HeaderSection.WELL and key in self._PROTECTED)
            for key, value in sorted(values.items(), key=lambda item: item[0].casefold())
        )

    def add(self, section: HeaderSection, mnemonic: str, value: str) -> None:
        key, normalized_value = self._validate(section, mnemonic, value)
        values = self._values(section)
        if key in values:
            raise ValueError(f"Мнемоника уже существует: {key}")
        def apply() -> None:
            values[key] = normalized_value
            if section is HeaderSection.WELL and key == "WELL":
                self._well().name = normalized_value

        self._change(f"Добавление {section.value}.{key}", apply)

    def update(
        self,
        section: HeaderSection,
        original_mnemonic: str,
        mnemonic: str,
        value: str,
    ) -> None:
        original = original_mnemonic.strip().upper()
        values = self._values(section)
        if original not in values:
            raise KeyError(f"Мнемоника не найдена: {original}")
        self._ensure_mutable(section, original)
        key, normalized_value = self._validate(section, mnemonic, value)
        if key != original and key in values:
            raise ValueError(f"Мнемоника уже существует: {key}")

        def apply() -> None:
            if key != original:
                del values[original]
            values[key] = normalized_value
            if section is HeaderSection.WELL and key == "WELL":
                self._well().name = normalized_value

        self._change(f"Изменение {section.value}.{original}", apply)

    def remove(self, section: HeaderSection, mnemonic: str) -> None:
        key = mnemonic.strip().upper()
        values = self._values(section)
        if key not in values:
            raise KeyError(f"Мнемоника не найдена: {key}")
        self._ensure_mutable(section, key)
        self._change(f"Удаление {section.value}.{key}", lambda: values.__delitem__(key))

    def undo(self) -> str:
        if not self._undo_stack:
            raise RuntimeError("Нет изменений заголовка для отмены")
        command = self._undo_stack[-1]
        self._restore(command.after, command.before)
        self._undo_stack.pop()
        self._redo_stack.append(command)
        self.session.dirty = True
        return command.description

    def redo(self) -> str:
        if not self._redo_stack:
            raise RuntimeError("Нет изменений заголовка для повтора")
        command = self._redo_stack[-1]
        self._restore(command.before, command.after)
        self._redo_stack.pop()
        self._undo_stack.append(command)
        self.session.dirty = True
        return command.description

    def clear_history(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()

    def _change(self, description: str, operation: Callable[[], None]) -> None:
        before = self._snapshot()
        operation()
        after = self._snapshot()
        if before == after:
            return
        self._undo_stack.append(_HeaderCommand(before, after, description))
        if len(self._undo_stack) > self.max_commands:
            del self._undo_stack[0]
        self._redo_stack.clear()
        self.session.dirty = True

    def _restore(self, expected: _HeaderSnapshot, replacement: _HeaderSnapshot) -> None:
        if self._snapshot() != expected:
            raise RuntimeError("LAS-заголовок был изменён вне истории команд")
        dataset = self._dataset()
        dataset.headers = dict(replacement.headers)
        dataset.parameters = dict(replacement.parameters)
        self._well().name = replacement.well_name

    def _snapshot(self) -> _HeaderSnapshot:
        dataset = self._dataset()
        return _HeaderSnapshot(
            self._well().well_id,
            dataset.dataset_id,
            tuple(dataset.headers.items()),
            tuple(dataset.parameters.items()),
            self._well().name,
        )

    def _values(self, section: HeaderSection) -> dict[str, str]:
        dataset = self._dataset()
        return dataset.headers if section is HeaderSection.WELL else dataset.parameters

    def _validate(self, section: HeaderSection, mnemonic: str, value: str) -> tuple[str, str]:
        key = mnemonic.strip().upper()
        normalized_value = value.strip()
        if not self._MNEMONIC.fullmatch(key):
            raise ValueError("Мнемоника: A–Z, затем A–Z, 0–9, '_' или '-', максимум 32 символа")
        self._ensure_mutable(section, key)
        if not normalized_value:
            raise ValueError("Значение LAS-заголовка не может быть пустым")
        if section is HeaderSection.WELL and key in self._LATITUDE:
            self._validate_coordinate(normalized_value, -90.0, 90.0, "Широта")
        if section is HeaderSection.WELL and key in self._LONGITUDE:
            self._validate_coordinate(normalized_value, -180.0, 180.0, "Долгота")
        return key, normalized_value

    def _ensure_mutable(self, section: HeaderSection, mnemonic: str) -> None:
        if section is HeaderSection.WELL and mnemonic in self._PROTECTED:
            raise ValueError(
                f"{mnemonic} управляется данными глубины и планом экспорта; "
                "используйте глубинные операции"
            )

    @staticmethod
    def _validate_coordinate(value: str, minimum: float, maximum: float, label: str) -> None:
        try:
            number = float(value.replace(",", "."))
        except ValueError as exc:
            raise ValueError(f"{label} должна быть числом в десятичных градусах") from exc
        if not minimum <= number <= maximum:
            raise ValueError(f"{label} должна быть в диапазоне {minimum:g}…{maximum:g}")

    def _dataset(self) -> Dataset:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите dataset")
        return dataset

    def _well(self) -> Well:
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Сначала выберите скважину")
        return well
