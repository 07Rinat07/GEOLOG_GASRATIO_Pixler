from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path


_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_LANGUAGES = ("ru", "kk", "en")


@dataclass(frozen=True, slots=True)
class RockDescriptionTemplate:
    template_id: str
    name_ru: str
    name_kk: str
    name_en: str
    text_ru: str
    text_kk: str
    text_en: str

    def localized(self, language: str) -> tuple[str, str]:
        normalized = language if language in _LANGUAGES else "ru"
        return (
            str(getattr(self, f"name_{normalized}")),
            str(getattr(self, f"text_{normalized}")),
        )


@dataclass(frozen=True, slots=True)
class RockDescriptionTemplateCatalog:
    templates: tuple[RockDescriptionTemplate, ...]
    formula: dict[str, str]
    warning: dict[str, str]

    def localized_guidance(self, language: str) -> tuple[str, str]:
        normalized = language if language in _LANGUAGES else "ru"
        return self.formula[normalized], self.warning[normalized]


def load_rock_description_templates(
    path: str | Path | None = None,
) -> RockDescriptionTemplateCatalog:
    if path is None:
        resource = files("geoworkbench").joinpath(
            "resources/rock_description_templates.json"
        )
        raw = json.loads(resource.read_text(encoding="utf-8"))
    else:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("Неподдерживаемая версия каталога описаний пород")

    formula = _localized_mapping(raw.get("formula"), field_name="formula")
    warning = _localized_mapping(raw.get("warning"), field_name="warning")
    entries = raw.get("templates")
    if not isinstance(entries, list):
        raise ValueError("Каталог описаний пород должен содержать список templates")

    templates: list[RockDescriptionTemplate] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Шаблон описания породы должен быть объектом")
        template_id = str(entry.get("id", "")).strip()
        if not _ID_PATTERN.fullmatch(template_id):
            raise ValueError(f"Некорректный ID шаблона описания: {template_id!r}")
        if template_id in seen:
            raise ValueError(f"Повторяющийся ID шаблона описания: {template_id}")
        names = _localized_mapping(entry.get("name"), field_name=f"{template_id}.name")
        texts = _localized_mapping(entry.get("text"), field_name=f"{template_id}.text")
        templates.append(
            RockDescriptionTemplate(
                template_id=template_id,
                name_ru=names["ru"],
                name_kk=names["kk"],
                name_en=names["en"],
                text_ru=texts["ru"],
                text_kk=texts["kk"],
                text_en=texts["en"],
            )
        )
        seen.add(template_id)
    if not templates:
        raise ValueError("Каталог описаний пород не может быть пустым")
    return RockDescriptionTemplateCatalog(tuple(templates), formula, warning)


def _localized_mapping(value: object, *, field_name: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"Поле {field_name} должно содержать переводы RU/KK/EN")
    result = {language: str(value.get(language, "")).strip() for language in _LANGUAGES}
    if not all(result.values()):
        raise ValueError(f"Поле {field_name} содержит неполные переводы RU/KK/EN")
    return result
