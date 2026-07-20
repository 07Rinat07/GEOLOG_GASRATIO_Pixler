from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True, slots=True)
class StratigraphyUnitDefinition:
    unit_id: str
    rank: str
    code: str
    name_ru: str
    name_kk: str
    name_en: str
    color: str
    parent_code: str = ""
    source: str = ""

    def localized_name(self, language: str) -> str:
        if language == "kk":
            return self.name_kk or self.name_ru
        if language == "en":
            return self.name_en or self.name_ru
        return self.name_ru


def load_stratigraphy_catalog(
    path: str | Path | None = None,
) -> tuple[StratigraphyUnitDefinition, ...]:
    if path is None:
        resource = files("geoworkbench").joinpath("resources/stratigraphy.ics.json")
        raw = json.loads(resource.read_text(encoding="utf-8"))
    else:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("Неподдерживаемая версия стратиграфического справочника")
    source = str(raw.get("source", "")).strip()
    entries = raw.get("units")
    if not isinstance(entries, list):
        raise ValueError("Стратиграфический справочник должен содержать список units")
    result: list[StratigraphyUnitDefinition] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Запись стратиграфического справочника должна быть объектом")
        definition = StratigraphyUnitDefinition(
            unit_id=str(entry.get("id", "")).strip(),
            rank=str(entry.get("rank", "")).strip(),
            code=str(entry.get("code", "")).strip(),
            name_ru=str(entry.get("name_ru", "")).strip(),
            name_kk=str(entry.get("name_kk", entry.get("name_ru", ""))).strip(),
            name_en=str(entry.get("name_en", "")).strip(),
            color=str(entry.get("color", "")).strip().lower(),
            parent_code=str(entry.get("parent_code", "")).strip(),
            source=source,
        )
        if not _ID_PATTERN.fullmatch(definition.unit_id):
            raise ValueError(f"Некорректный ID стратиграфической единицы: {definition.unit_id!r}")
        if definition.unit_id in seen:
            raise ValueError(f"Повторяющийся ID стратиграфической единицы: {definition.unit_id}")
        if not all(
            (
                definition.rank,
                definition.code,
                definition.name_ru,
                definition.name_kk,
                definition.name_en,
            )
        ):
            raise ValueError(f"Неполная стратиграфическая запись: {definition.unit_id}")
        if not _COLOR_PATTERN.fullmatch(definition.color):
            raise ValueError(f"Некорректный цвет стратиграфической единицы: {definition.unit_id}")
        seen.add(definition.unit_id)
        result.append(definition)
    return tuple(result)
