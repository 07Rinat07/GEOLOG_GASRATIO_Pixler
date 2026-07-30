from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.services.lba_standard import (
    LBA_STANDARD_GROUPS,
    lba_intensity_name as standard_lba_intensity_name,
    normalize_lba_key,
)
from geoworkbench.services.localization import AppLanguage


@dataclass(frozen=True, slots=True)
class LbaTypeStyle:
    type_id: str
    code: str
    name_ru: str
    name_kk: str
    name_en: str
    color: str
    aliases: tuple[str, ...] = ()

    def localized_name(self, language: AppLanguage) -> str:
        if language is AppLanguage.KK:
            return self.name_kk
        if language is AppLanguage.EN:
            return self.name_en
        return self.name_ru


LBA_TYPE_STYLES: tuple[LbaTypeStyle, ...] = tuple(
    LbaTypeStyle(
        group.type_id,
        group.code,
        group.type_name_ru,
        group.type_name_kk,
        group.type_name_en,
        group.display_color,
        group.aliases,
    )
    for group in LBA_STANDARD_GROUPS
)


def normalize_lba_type_key(value: str | None) -> str:
    return normalize_lba_key(value)


_STYLE_BY_KEY: dict[str, LbaTypeStyle] = {}
for _style in LBA_TYPE_STYLES:
    for _value in (_style.type_id, _style.code, *_style.aliases):
        _STYLE_BY_KEY[normalize_lba_type_key(_value)] = _style


UNKNOWN_LBA_STYLE = LbaTypeStyle(
    "unknown",
    "?",
    "неопределённый битумоид",
    "анықталмаған битумоид",
    "unresolved bitumen",
    "#94a3b8",
)


def resolve_lba_type_style(value: str | None) -> LbaTypeStyle:
    return _STYLE_BY_KEY.get(normalize_lba_type_key(value), UNKNOWN_LBA_STYLE)


def normalized_lba_intensity(value: int | None) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 1 <= value <= 5 else None


def lba_intensity_name(intensity: int, language: AppLanguage) -> str:
    return standard_lba_intensity_name(intensity, language)
