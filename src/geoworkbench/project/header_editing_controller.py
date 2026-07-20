from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from typing import Callable

import numpy as np

from geoworkbench.domain.models import Dataset, IndexRole, Well
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.depth_axis import DepthDirection, analyze_depth_axis


class HeaderSection(StrEnum):
    VERSION = "VERSION"
    WELL = "WELL"
    PARAMETER = "PARAMETER"


@dataclass(frozen=True, slots=True)
class HeaderEntry:
    mnemonic: str
    value: str
    protected: bool = False


@dataclass(frozen=True, slots=True)
class DepthHeaderSummary:
    calculated_start: float | None
    calculated_stop: float | None
    calculated_step: float | None
    declared_start: float | None
    declared_stop: float | None
    declared_step: float | None
    null_value: float | None
    direction: DepthDirection
    uniform: bool
    issues: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _HeaderSnapshot:
    well_id: str
    dataset_id: str
    version_headers: tuple[tuple[str, str], ...]
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
    _VERSION_PROTECTED = frozenset({"VERS", "WRAP"})
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
            HeaderEntry(
                key,
                value,
                (section is HeaderSection.WELL and key in self._PROTECTED)
                or (section is HeaderSection.VERSION and key in self._VERSION_PROTECTED),
            )
            for key, value in sorted(values.items(), key=lambda item: item[0].casefold())
        )

    def depth_summary(self) -> DepthHeaderSummary:
        dataset = self._dataset()
        report = analyze_depth_axis(dataset.depth)
        signed_step = report.nominal_step
        if signed_step is not None and report.direction is DepthDirection.DESCENDING:
            signed_step = -signed_step
        declared = {
            key: self._optional_float(dataset.headers.get(key))
            for key in ("STRT", "STOP", "STEP", "NULL")
        }
        issues: list[str] = []
        if dataset.active_index.role is not IndexRole.DEPTH:
            issues.append("Активный индекс не является глубинным; синхронизация отключена")
        for key, actual in (
            ("STRT", report.start),
            ("STOP", report.stop),
            ("STEP", signed_step),
        ):
            value = declared[key]
            if value is None:
                issues.append(f"{key} отсутствует или не является числом")
            elif actual is not None and not np.isclose(value, actual, rtol=1e-6, atol=1e-9):
                issues.append(f"{key}={value:g} не совпадает с данными ({actual:g})")
        if declared["NULL"] is None:
            issues.append("NULL отсутствует или не является конечным числом")
        if not report.is_uniform:
            issues.append("Шаг активного глубинного индекса неоднороден")
        if report.direction not in {DepthDirection.ASCENDING, DepthDirection.DESCENDING}:
            issues.append(f"Направление глубины: {report.direction.value}")
        return DepthHeaderSummary(
            report.start,
            report.stop,
            signed_step,
            declared["STRT"],
            declared["STOP"],
            declared["STEP"],
            declared["NULL"],
            report.direction,
            report.is_uniform,
            tuple(issues),
        )

    def synchronize_depth_fields(self) -> None:
        dataset = self._dataset()
        report = analyze_depth_axis(dataset.depth)
        if dataset.active_index.role is not IndexRole.DEPTH:
            raise ValueError("Для синхронизации выберите активный глубинный индекс")
        if (
            report.start is None
            or report.stop is None
            or report.nominal_step is None
            or not report.is_uniform
            or report.missing_count
            or report.duplicate_count
            or report.direction not in {DepthDirection.ASCENDING, DepthDirection.DESCENDING}
        ):
            raise ValueError(
                "Синхронизация доступна только для конечной равномерной монотонной глубины"
            )
        signed_step = (
            -report.nominal_step
            if report.direction is DepthDirection.DESCENDING
            else report.nominal_step
        )

        def apply() -> None:
            dataset.headers.update(
                STRT=f"{report.start:.15g}",
                STOP=f"{report.stop:.15g}",
                STEP=f"{signed_step:.15g}",
            )

        self._change("Синхронизация STRT/STOP/STEP", apply)

    def set_null_value(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)):
            raise ValueError("NULL должен быть числом")
        normalized = float(value)
        if not isfinite(normalized):
            raise ValueError("NULL должен быть конечным числом")
        dataset = self._dataset()
        arrays = [dataset.depth, *(curve.values for curve in dataset.curves.values())]
        if any(np.any(np.asarray(array) == normalized) for array in arrays):
            raise ValueError("NULL совпадает с реальным значением dataset")
        self._change(
            "Изменение NULL",
            lambda: dataset.headers.__setitem__("NULL", f"{normalized:.15g}"),
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
        dataset.version_headers = dict(replacement.version_headers)
        dataset.headers = dict(replacement.headers)
        dataset.parameters = dict(replacement.parameters)
        self._well().name = replacement.well_name

    def _snapshot(self) -> _HeaderSnapshot:
        dataset = self._dataset()
        return _HeaderSnapshot(
            self._well().well_id,
            dataset.dataset_id,
            tuple(dataset.version_headers.items()),
            tuple(dataset.headers.items()),
            tuple(dataset.parameters.items()),
            self._well().name,
        )

    def _values(self, section: HeaderSection) -> dict[str, str]:
        dataset = self._dataset()
        if section is HeaderSection.VERSION:
            return dataset.version_headers
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
        if section is HeaderSection.VERSION and mnemonic in self._VERSION_PROTECTED:
            raise ValueError(
                f"{mnemonic} управляется планом экспорта; измените версию или WRAP при сохранении"
            )
        if section is HeaderSection.WELL and mnemonic in self._PROTECTED:
            raise ValueError(
                f"{mnemonic} управляется данными глубины и планом экспорта; "
                "используйте глубинные операции"
            )

    @staticmethod
    def _optional_float(value: str | None) -> float | None:
        if value is None:
            return None
        try:
            number = float(value.strip().replace(",", "."))
        except ValueError:
            return None
        return number if isfinite(number) else None

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
