from __future__ import annotations

from dataclasses import dataclass
import re

from geoworkbench.catalogs.stratigraphy import (
    StratigraphyUnitDefinition,
    load_stratigraphy_catalog,
)
from geoworkbench.domain.models import ProjectStratigraphyUnit
from geoworkbench.project.session import ProjectSession

_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True, slots=True)
class CatalogStratigraphyUnit:
    unit_id: str
    rank: str
    code: str
    name_ru: str
    name_kk: str
    name_en: str
    color: str
    parent_code: str = ""
    description: str = ""
    system: bool = False
    overridden: bool = False
    source: str = ""

    def localized_name(self, language: str) -> str:
        if language == "kk":
            return self.name_kk or self.name_ru
        if language == "en":
            return self.name_en or self.name_ru
        return self.name_ru


@dataclass(slots=True)
class StratigraphyCatalogController:
    session: ProjectSession

    def available(self) -> tuple[CatalogStratigraphyUnit, ...]:
        defaults = {item.unit_id: item for item in load_stratigraphy_catalog()}
        merged: list[CatalogStratigraphyUnit] = []
        for unit_id, definition in defaults.items():
            override = self.session.project.stratigraphy_units.get(unit_id)
            if override is None:
                merged.append(self._from_definition(definition))
            else:
                merged.append(self._from_project(override, system=True, overridden=True))
        for unit_id, record in self.session.project.stratigraphy_units.items():
            if unit_id not in defaults:
                merged.append(self._from_project(record, system=False, overridden=False))
        return tuple(sorted(merged, key=self._sort_key))

    def get(self, unit_id: str) -> CatalogStratigraphyUnit:
        for item in self.available():
            if item.unit_id == unit_id:
                return item
        raise KeyError(f"Стратиграфическая единица не найдена: {unit_id}")

    def save(
        self,
        unit_id: str,
        *,
        rank: str,
        code: str,
        name_ru: str,
        name_kk: str,
        name_en: str,
        color: str,
        parent_code: str = "",
        description: str = "",
    ) -> CatalogStratigraphyUnit:
        record = self._validate(
            unit_id,
            rank,
            code,
            name_ru,
            name_kk,
            name_en,
            color,
            parent_code,
            description,
        )
        self._ensure_unique_code(record)
        self.session.project.stratigraphy_units[record.unit_id] = record
        self.session.dirty = True
        defaults = {item.unit_id for item in load_stratigraphy_catalog()}
        return self._from_project(
            record,
            system=record.unit_id in defaults,
            overridden=record.unit_id in defaults,
        )

    def reset(self, unit_id: str) -> CatalogStratigraphyUnit:
        defaults = {item.unit_id: item for item in load_stratigraphy_catalog()}
        if unit_id not in defaults:
            raise ValueError("Пользовательскую запись нельзя сбросить к заводскому значению")
        self.session.project.stratigraphy_units.pop(unit_id, None)
        self.session.dirty = True
        return self._from_definition(defaults[unit_id])

    def remove(self, unit_id: str) -> CatalogStratigraphyUnit:
        defaults = {item.unit_id for item in load_stratigraphy_catalog()}
        if unit_id in defaults:
            raise ValueError("Системную запись можно только изменить или сбросить")
        try:
            record = self.session.project.stratigraphy_units.pop(unit_id)
        except KeyError as exc:
            raise KeyError(f"Пользовательская запись не найдена: {unit_id}") from exc
        self.session.dirty = True
        return self._from_project(record, system=False, overridden=False)

    def new_id(self, code: str) -> str:
        stem = re.sub(r"[^a-z0-9]+", "_", code.strip().casefold()).strip("_") or "unit"
        candidate = f"custom_{stem}"
        existing = {item.unit_id for item in self.available()}
        counter = 2
        while candidate in existing:
            candidate = f"custom_{stem}_{counter}"
            counter += 1
        return candidate

    def _ensure_unique_code(self, record: ProjectStratigraphyUnit) -> None:
        rank_key = record.rank.strip().casefold()
        code_key = record.code.strip().casefold()
        for item in self.available():
            if item.unit_id == record.unit_id:
                continue
            if item.rank.strip().casefold() == rank_key and item.code.strip().casefold() == code_key:
                raise ValueError(
                    f"Код '{record.code}' уже существует в ранге '{record.rank}'"
                )

    @staticmethod
    def _validate(
        unit_id: str,
        rank: str,
        code: str,
        name_ru: str,
        name_kk: str,
        name_en: str,
        color: str,
        parent_code: str,
        description: str,
    ) -> ProjectStratigraphyUnit:
        normalized_id = unit_id.strip().casefold()
        normalized_rank = rank.strip()
        normalized_code = code.strip()
        normalized_ru = name_ru.strip()
        normalized_kk = name_kk.strip() or normalized_ru
        normalized_en = name_en.strip() or normalized_ru
        normalized_color = color.strip().lower()
        normalized_parent = parent_code.strip()
        normalized_description = description.strip()
        if not _ID_PATTERN.fullmatch(normalized_id):
            raise ValueError("ID должен начинаться с латинской буквы и содержать a-z, 0-9, _")
        if not normalized_rank or len(normalized_rank) > 100:
            raise ValueError("Ранг обязателен и не длиннее 100 символов")
        if not normalized_code or len(normalized_code) > 30:
            raise ValueError("Код обязателен и не длиннее 30 символов")
        if not normalized_ru or len(normalized_ru) > 160:
            raise ValueError("Русское название обязательно и не длиннее 160 символов")
        if len(normalized_kk) > 160 or len(normalized_en) > 160:
            raise ValueError("Локализованное название не должно превышать 160 символов")
        if not _COLOR_PATTERN.fullmatch(normalized_color):
            raise ValueError("Цвет должен быть записан как #RRGGBB")
        if len(normalized_parent) > 30 or len(normalized_description) > 1000:
            raise ValueError("Родительский код или описание слишком длинные")
        return ProjectStratigraphyUnit(
            normalized_id,
            normalized_rank,
            normalized_code,
            normalized_ru,
            normalized_kk,
            normalized_en,
            normalized_color,
            normalized_parent,
            normalized_description,
        )

    @staticmethod
    def _sort_key(item: CatalogStratigraphyUnit) -> tuple[int, str, str]:
        rank_order = {
            "Eonothem / Eon": 0,
            "Erathem / Era": 1,
            "System / Period": 2,
            "Series / Epoch": 3,
            "Stage / Age": 4,
            "Formation": 5,
            "Member": 6,
            "Bed": 7,
        }
        return rank_order.get(item.rank, 99), item.code.casefold(), item.unit_id

    @staticmethod
    def _from_definition(item: StratigraphyUnitDefinition) -> CatalogStratigraphyUnit:
        return CatalogStratigraphyUnit(
            item.unit_id,
            item.rank,
            item.code,
            item.name_ru,
            item.name_kk,
            item.name_en,
            item.color,
            item.parent_code,
            system=True,
            overridden=False,
            source=item.source,
        )

    @staticmethod
    def _from_project(
        item: ProjectStratigraphyUnit,
        *,
        system: bool,
        overridden: bool,
    ) -> CatalogStratigraphyUnit:
        return CatalogStratigraphyUnit(
            item.unit_id,
            item.rank,
            item.code,
            item.name_ru,
            item.name_kk,
            item.name_en,
            item.color,
            item.parent_code,
            item.description,
            system,
            overridden,
            "project",
        )
