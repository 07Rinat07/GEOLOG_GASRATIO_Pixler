from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path


_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True, slots=True)
class LithotypeDefinition:
    lithotype_id: str
    code: str
    name_ru: str
    name_en: str
    category: str
    color: str
    pattern_key: str


def load_lithotype_catalog(path: str | Path | None = None) -> tuple[LithotypeDefinition, ...]:
    if path is None:
        resource = files("geoworkbench").joinpath("resources/lithotypes.ru.json")
        raw = json.loads(resource.read_text(encoding="utf-8"))
    else:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("Неподдерживаемая версия каталога литотипов")
    entries = raw.get("lithotypes")
    if not isinstance(entries, list):
        raise ValueError("Каталог литотипов должен содержать список lithotypes")

    result: list[LithotypeDefinition] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Запись литотипа должна быть объектом")
        definition = LithotypeDefinition(
            lithotype_id=str(entry.get("id", "")).strip(),
            code=str(entry.get("code", entry.get("id", ""))).strip().upper(),
            name_ru=str(entry.get("name_ru", "")).strip(),
            name_en=str(entry.get("name_en", "")).strip(),
            category=str(entry.get("category", "")).strip(),
            color=str(entry.get("color", "")).strip(),
            pattern_key=str(entry.get("pattern_key", "")).strip(),
        )
        if not _ID_PATTERN.fullmatch(definition.lithotype_id):
            raise ValueError(f"Некорректный ID литотипа: {definition.lithotype_id!r}")
        if definition.lithotype_id in seen:
            raise ValueError(f"Повторяющийся ID литотипа: {definition.lithotype_id}")
        if not all(
            (
                definition.code,
                definition.name_ru,
                definition.name_en,
                definition.category,
                definition.pattern_key,
            )
        ):
            raise ValueError(f"Неполная запись литотипа: {definition.lithotype_id}")
        if not _COLOR_PATTERN.fullmatch(definition.color):
            raise ValueError(f"Некорректный цвет литотипа: {definition.lithotype_id}")
        seen.add(definition.lithotype_id)
        result.append(definition)
    return tuple(result)
