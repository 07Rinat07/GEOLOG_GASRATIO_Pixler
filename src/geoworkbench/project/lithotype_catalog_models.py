from __future__ import annotations

from dataclasses import dataclass


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
    overridden: bool = False
    source: str = "system"
    aliases: tuple[str, ...] = ()

    def localized_name(self, language: str) -> str:
        if language == "kk":
            return self.name_kk or self.name_ru
        if language == "en":
            return self.name_en
        return self.name_ru
