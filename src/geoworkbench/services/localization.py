from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from importlib.resources import files
from typing import Any

from PySide6.QtCore import QSettings


class AppLanguage(StrEnum):
    RU = "ru"
    KK = "kk"
    EN = "en"


LANGUAGE_NAMES = {
    AppLanguage.RU: "Русский",
    AppLanguage.KK: "Қазақша",
    AppLanguage.EN: "English",
}


def load_catalog(language: AppLanguage) -> dict[str, str]:
    resource = files("geoworkbench").joinpath("resources", "i18n", f"{language.value}.json")
    payload = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in payload.items()
    ):
        raise RuntimeError(f"Некорректный каталог локализации: {language.value}")
    return payload


@dataclass(slots=True)
class Localizer:
    language: AppLanguage
    catalog: dict[str, str]

    @classmethod
    def create(cls, language: AppLanguage) -> Localizer:
        return cls(language, load_catalog(language))

    def text(self, key: str, **values: object) -> str:
        template = self.catalog.get(key)
        if template is None:
            template = load_catalog(AppLanguage.RU).get(key, key)
        return template.format(**values)


@dataclass(slots=True)
class LanguageSettings:
    settings: Any

    @classmethod
    def system(cls) -> LanguageSettings:
        return cls(QSettings())

    def current(self) -> AppLanguage | None:
        value = self.settings.value("ui/language")
        try:
            return AppLanguage(str(value)) if value else None
        except ValueError:
            return None

    def save(self, language: AppLanguage) -> None:
        self.settings.setValue("ui/language", language.value)
        self.settings.sync()
