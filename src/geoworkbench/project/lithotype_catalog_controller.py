from __future__ import annotations

import re
from dataclasses import dataclass

from geoworkbench.catalogs.lithotypes import LithotypeDefinition, load_lithotype_catalog
from geoworkbench.domain.models import ProjectLithotype
from geoworkbench.form_constructor.asset_install import (
    factory_asset_to_project_lithotype,
    load_factory_constructor_registry,
)
from geoworkbench.project.lithotype_catalog_models import CatalogLithotype
from geoworkbench.project.session import ProjectSession


_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")
_CODE_PATTERN = re.compile(r"^[A-ZА-Я0-9][A-ZА-Я0-9_-]{0,19}$")
_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(slots=True)
class LithotypeCatalogController:
    session: ProjectSession

    def available(self) -> tuple[CatalogLithotype, ...]:
        base = self._base_catalog()
        merged = dict(base)
        for record in self.session.project.lithotypes.values():
            merged[record.lithotype_id] = self._from_project(
                record,
                overridden=record.lithotype_id in base,
            )
        order = {"system": 0, "factory": 1, "project_override": 2, "project": 3}
        return tuple(
            sorted(
                merged.values(),
                key=lambda item: (
                    order.get(item.source, 9),
                    item.category.casefold(),
                    item.name_ru.casefold(),
                    item.code.casefold(),
                    item.lithotype_id,
                ),
            )
        )

    def get(self, lithotype_id: str) -> CatalogLithotype:
        for item in self.available():
            if item.lithotype_id == lithotype_id:
                return item
        raise KeyError(f"Литотип не найден: {lithotype_id}")

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
        if (
            lithotype_id not in self.session.project.lithotypes
            and lithotype_id not in self._base_catalog()
        ):
            raise KeyError(f"Литотип не найден: {lithotype_id}")
        record = self._validate(
            lithotype_id, code, name_ru, name_en, category, color, pattern_key, name_kk
        )
        self._ensure_unique(record, excluded_id=lithotype_id)
        self.session.project.lithotypes[lithotype_id] = record
        self.session.dirty = True
        return self._from_project(record, overridden=lithotype_id in self._base_catalog())

    def remove(self, lithotype_id: str) -> CatalogLithotype:
        try:
            record = self.session.project.lithotypes[lithotype_id]
        except KeyError as exc:
            raise KeyError(
                f"Системный или неизвестный литотип нельзя удалить: {lithotype_id}"
            ) from exc
        base_exists = lithotype_id in self._base_catalog()
        used = [
            interval
            for well in self.session.project.wells.values()
            for interval in well.lithology
            if interval.lithotype_id == lithotype_id
        ]
        if used and not base_exists:
            raise ValueError("Литотип используется в литологических интервалах")
        del self.session.project.lithotypes[lithotype_id]
        self.session.dirty = True
        return self._from_project(record, overridden=base_exists)

    def _ensure_unique(self, record: ProjectLithotype, *, excluded_id: str | None = None) -> None:
        base = self._base_catalog()
        current_code: str | None = None
        if excluded_id is not None:
            current = self.session.project.lithotypes.get(excluded_id) or base.get(excluded_id)
            current_code = current.code.casefold() if current is not None else None

        if excluded_id is None and record.lithotype_id in base:
            raise ValueError(
                "Заводской литотип изменяется кнопкой «Сохранить изменения», "
                "а не добавляется повторно"
            )

        # A newly entered code must not collide with any visible catalog row.
        # Imported legacy/factory rows may already contain historical aliases with
        # the same code, therefore an update that leaves its own code unchanged
        # is allowed and does not manufacture a new conflict.
        check_code = current_code is None or record.code.casefold() != current_code
        for item in self.available():
            if item.lithotype_id == excluded_id:
                continue
            if item.lithotype_id == record.lithotype_id:
                raise ValueError(f"ID литотипа уже существует: {record.lithotype_id}")
            if check_code and item.code.casefold() == record.code.casefold():
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
            raise ValueError(
                "ID должен начинаться с латинской буквы и содержать a-z, 0-9, _ или -"
            )
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
            False,
            "system",
        )

    @staticmethod
    def _from_project(
        item: ProjectLithotype,
        *,
        overridden: bool = False,
    ) -> CatalogLithotype:
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
            overridden,
            "project_override" if overridden else "project",
        )

    def _base_catalog(self) -> dict[str, CatalogLithotype]:
        result = {
            item.lithotype_id: self._from_definition(item)
            for item in load_lithotype_catalog()
        }
        try:
            registry = load_factory_constructor_registry()
        except (OSError, RuntimeError, ValueError):
            return result
        for asset in registry.all(kind="lithology_pattern"):
            record = factory_asset_to_project_lithotype(asset)
            # The compact built-in catalog keeps its historical identifiers.
            # Factory bitmap identifiers use the ``lithology-`` namespace, so
            # both layers can coexist without silently replacing one another.
            result.setdefault(
                record.lithotype_id,
                CatalogLithotype(
                    record.lithotype_id,
                    record.code,
                    record.name_ru,
                    record.name_en,
                    record.category,
                    record.color,
                    record.pattern_key,
                    True,
                    record.name_kk or record.name_ru,
                    False,
                    "factory",
                    asset.aliases,
                ),
            )
        return result
