from __future__ import annotations

from dataclasses import dataclass
import re

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


LBA_TYPE_STYLES: tuple[LbaTypeStyle, ...] = (
    LbaTypeStyle(
        "light",
        "ЛБ",
        "лёгкий битумоид",
        "жеңіл битумоид",
        "light bitumen",
        "#22d3d6",
        ("LB", "LIGHT", "ЛЕГКИЙ", "ЛЁГКИЙ"),
    ),
    LbaTypeStyle(
        "oily",
        "МБ",
        "маслянистый битумоид",
        "майлы битумоид",
        "low-oil bitumen",
        "#facc15",
        ("LOB", "OILY", "LOWOIL", "МАСЛЯНИСТЫЙ"),
    ),
    LbaTypeStyle(
        "oily_resinous",
        "МСБ",
        "маслянисто-смолистый битумоид",
        "майлы-шайырлы битумоид",
        "middle-oil bitumen",
        "#fb923c",
        ("MOB", "OILYRESINOUS", "MIDDLEOIL", "МАСЛЯНИСТОСМОЛИСТЫЙ"),
    ),
    LbaTypeStyle(
        "resinous",
        "СБ",
        "смолистый битумоид",
        "шайырлы битумоид",
        "high-oil bitumen",
        "#be3144",
        ("HOB", "RESINOUS", "HIGHOIL", "СМОЛИСТЫЙ"),
    ),
    LbaTypeStyle(
        "resin_asphaltene",
        "САБ",
        "смолисто-асфальтеновый битумоид",
        "шайырлы-асфальтенді битумоид",
        "very-high-oil bitumen",
        "#8b5757",
        ("VHO", "RESINASPHALTENE", "VERYHIGHOIL", "СМОЛИСТОАСФАЛЬТЕНОВЫЙ"),
    ),
)


_NORMALIZE_RE = re.compile(r"[^0-9A-ZА-ЯЁӘҒҚҢӨҰҮҺІ]+")


def normalize_lba_type_key(value: str | None) -> str:
    if not value:
        return ""
    return _NORMALIZE_RE.sub("", value.strip().upper().replace("Ё", "Е"))


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
    names = {
        AppLanguage.RU: {
            1: "единичные точки",
            2: "фрагментарное кольцо",
            3: "тонкое сплошное кольцо",
            4: "толстое кольцо",
            5: "сплошное пятно",
        },
        AppLanguage.KK: {
            1: "жекелеген нүктелер",
            2: "үзік сақина",
            3: "жұқа тұтас сақина",
            4: "қалың сақина",
            5: "тұтас дақ",
        },
        AppLanguage.EN: {
            1: "isolated points",
            2: "fragmentary ring",
            3: "thin continuous ring",
            4: "thick ring",
            5: "continuous spot",
        },
    }
    return names[language][intensity]
