from __future__ import annotations

import re
from dataclasses import dataclass

from geoworkbench.catalogs.lithotypes import LithotypeDefinition, load_lithotype_catalog
from geoworkbench.domain.models import ProjectLithotype
from geoworkbench.project.session import ProjectSession


_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_CODE_PATTERN = re.compile(r"^[A-ZА-Я0-9][A-ZА-Я0-9_-]{0,19}$")
_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True, slots=True)
class CatalogLithotype:
    lithotype_id: str
    code: str
    name_ru: str
    name_en: str
    category: str
    color: str
    pattern_key: str
    system: bool
    name_kk: str = ""

    def localized_name(self, language: str) -> str:
        if language == "kk":
            return self.name_kk or self.name_ru
        if language == "en":
            return self.name_en
        return self.name_ru


@dataclass(slots=True)
class LithotypeCatalogController:
    session: ProjectSession

    def available(self) -> tuple[CatalogLithotype, ...]:
        system = [self._from_definition(item) for item in load_lithotype_catalog()]
        custom = [self._from_project(item) for item in self.session.project.lithotypes.values()]
        return tuple(system + sorted(custom, key=lambda item: (item.name_ru.casefold(), item.code)))

    def add(
        self,
        lithotype_id: str,
        code: str,
        name_ru: str,
        name_en: str,
        category: str,
        color: str,
        pattern_key: str,
        name_kk: str = "",
    ) -> CatalogLithotype:
        record = self._validate(
            lithotype_id, code, name_ru, name_en, category, color, pattern_key, name_kk
        )
        self._ensure_unique(record)
        self.session.project.lithotypes[record.lithotype_id] = record
        self.session.dirty = True
        return self._from_project(record)

    def update(
        self,
        lithotype_id: str,
        *,
        code: str,
        name_ru: str,
        name_en: str,
        category: str,
        color: str,
        pattern_key: str,
        name_kk: str = "",
    ) -> CatalogLithotype:
        if lithotype_id not in self.session.project.lithotypes:
            raise KeyError(f"Пользовательский литотип не найден: {lithotype_id}")
        record = self._validate(
            lithotype_id, code, name_ru, name_en, category, color, pattern_key, name_kk
        )
        self._ensure_unique(record, excluded_id=lithotype_id)
        self.session.project.lithotypes[lithotype_id] = record
        self.session.dirty = True
        return self._from_project(record)

    def remove(self, lithotype_id: str) -> CatalogLithotype:
        try:
            record = self.session.project.lithotypes[lithotype_id]
        except KeyError as exc:
            raise KeyError(
                f"Системный или неизвестный литотип нельзя удалить: {lithotype_id}"
            ) from exc
        used = [
            interval
            for well in self.session.project.wells.values()
            for interval in well.lithology
            if interval.lithotype_id == lithotype_id
        ]
        if used:
            raise ValueError("Литотип используется в литологических интервалах")
        del self.session.project.lithotypes[lithotype_id]
        self.session.dirty = True
        return self._from_project(record)

    def _ensure_unique(self, record: ProjectLithotype, *, excluded_id: str | None = None) -> None:
        for item in self.available():
            if item.lithotype_id == excluded_id:
                continue
            if item.lithotype_id == record.lithotype_id:
                raise ValueError(f"ID литотипа уже существует: {record.lithotype_id}")
            if item.code.casefold() == record.code.casefold():
                raise ValueError(f"Код литотипа уже существует: {record.code}")

    @staticmethod
    def _validate(
        lithotype_id: str,
        code: str,
        name_ru: str,
        name_en: str,
        category: str,
        color: str,
        pattern_key: str,
        name_kk: str = "",
    ) -> ProjectLithotype:
        values = {
            "ID": lithotype_id.strip(),
            "код": code.strip().upper(),
            "русское название": name_ru.strip(),
            "английское название": name_en.strip(),
            "казахское название": name_kk.strip() or name_ru.strip(),
            "категория": category.strip(),
            "цвет": color.strip(),
            "ключ узора": pattern_key.strip(),
        }
        for label, value in values.items():
            if not value:
                raise ValueError(f"Поле '{label}' не может быть пустым")
        if not _ID_PATTERN.fullmatch(values["ID"]):
            raise ValueError("ID должен начинаться с латинской буквы и содержать a-z, 0-9, _")
        if not _CODE_PATTERN.fullmatch(values["код"]):
            raise ValueError("Код должен содержать 1–20 заглавных букв, цифр, _ или -")
        if not _COLOR_PATTERN.fullmatch(values["цвет"]):
            raise ValueError("Цвет должен быть записан как #RRGGBB")
        return ProjectLithotype(
            lithotype_id=values["ID"],
            code=values["код"],
            name_ru=values["русское название"],
            name_en=values["английское название"],
            category=values["категория"],
            color=values["цвет"].lower(),
            pattern_key=values["ключ узора"],
            name_kk=values["казахское название"],
        )

    @staticmethod
    def _from_definition(item: LithotypeDefinition) -> CatalogLithotype:
        return CatalogLithotype(
            item.lithotype_id,
            item.code,
            item.name_ru,
            item.name_en,
            item.category,
            item.color,
            item.pattern_key,
            True,
            item.name_kk,
        )

    @staticmethod
    def _from_project(item: ProjectLithotype) -> CatalogLithotype:
        return CatalogLithotype(
            item.lithotype_id,
            item.code,
            item.name_ru,
            item.name_en,
            item.category,
            item.color,
            item.pattern_key,
            False,
            item.name_kk or item.name_ru,
        )
