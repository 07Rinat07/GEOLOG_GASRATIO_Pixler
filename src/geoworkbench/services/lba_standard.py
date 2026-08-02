from __future__ import annotations

from dataclasses import dataclass
import re

from geoworkbench.services.localization import AppLanguage


_NORMALIZE_RE = re.compile(r"[^0-9A-ZА-ЯЁӘҒҚҢӨҰҮҺІ]+")


def normalize_lba_key(value: str | None) -> str:
    if not value:
        return ""
    return _NORMALIZE_RE.sub("", value.strip().upper().replace("Ё", "Е"))


@dataclass(frozen=True, slots=True)
class LbaFluorescenceColor:
    code: str
    name_ru: str
    name_kk: str
    name_en: str

    def localized_name(self, language: AppLanguage) -> str:
        if language is AppLanguage.KK:
            return self.name_kk
        if language is AppLanguage.EN:
            return self.name_en
        return self.name_ru

    def label(self, language: AppLanguage) -> str:
        """Return the compact code used inside the narrow LBA graph column."""

        return self.code

    def selection_label(self, language: AppLanguage) -> str:
        """Return the explanatory label used by the sample editor combobox."""

        return f"{self.code} — {self.localized_name(language)}"


@dataclass(frozen=True, slots=True)
class LbaStandardGroup:
    group: int
    type_id: str
    code: str
    type_name_ru: str
    type_name_kk: str
    type_name_en: str
    composition_ru: str
    composition_kk: str
    composition_en: str
    colors: tuple[LbaFluorescenceColor, ...]
    display_color: str
    aliases: tuple[str, ...] = ()

    def localized_type_name(self, language: AppLanguage) -> str:
        if language is AppLanguage.KK:
            return self.type_name_kk
        if language is AppLanguage.EN:
            return self.type_name_en
        return self.type_name_ru

    def localized_composition(self, language: AppLanguage) -> str:
        if language is AppLanguage.KK:
            return self.composition_kk
        if language is AppLanguage.EN:
            return self.composition_en
        return self.composition_ru


def _color(code: str, ru: str, en: str) -> LbaFluorescenceColor:
    return LbaFluorescenceColor(code, ru, ru, en)


LBA_STANDARD_GROUPS: tuple[LbaStandardGroup, ...] = (
    LbaStandardGroup(
        1,
        "light",
        "ЛБ",
        "лёгкий битумоид",
        "жеңіл битумоид",
        "light bitumen",
        "УВ-флюиды без смол и асфальтенов",
        "шайырлар мен асфальтендері жоқ көмірсутек флюидтері",
        "hydrocarbon fluids without resins or asphaltenes",
        (_color("БГ", "беловато-голубой", "whitish blue"),),
        "#22d3d6",
        ("LB", "LIGHT", "ЛЕГКИЙ", "ЛЁГКИЙ"),
    ),
    LbaStandardGroup(
        2,
        "oily",
        "МБ",
        "маслянистый битумоид",
        "майлы битумоид",
        "oily bitumen",
        "Нефть и битумоиды с низким содержанием смол; асфальтены отсутствуют",
        "шайыры аз мұнай мен битумоидтар; асфальтендер жоқ",
        "oil and bitumen with low resin content and no asphaltenes",
        (
            _color("Б", "белый", "white"),
            _color("ГЖ", "голубовато-жёлтый", "bluish yellow"),
            _color("БЖ", "беловато-жёлтый", "whitish yellow"),
        ),
        "#facc15",
        ("LOB", "OILY", "LOWOIL", "МАСЛЯНИСТЫЙ"),
    ),
    LbaStandardGroup(
        3,
        "oily_resinous",
        "МСБ",
        "маслянисто-смолистый битумоид",
        "майлы-шайырлы битумоид",
        "oily-resinous bitumen",
        "Нефть и битумоиды: масел более 60%, асфальтенов 1–2%",
        "мұнай мен битумоидтар: майлар 60%-дан көп, асфальтендер 1–2%",
        "oil and bitumen with more than 60% oils and 1–2% asphaltenes",
        (
            _color("Ж", "жёлтый", "yellow"),
            _color("ОЖ", "оранжево-жёлтый", "orange-yellow"),
            _color("СК", "светло-коричневый", "light brown"),
        ),
        "#fb923c",
        ("MOB", "OILYRESINOUS", "MIDDLEOIL", "МАСЛЯНИСТОСМОЛИСТЫЙ"),
    ),
    LbaStandardGroup(
        4,
        "resinous",
        "СБ",
        "смолистый битумоид",
        "шайырлы битумоид",
        "resinous bitumen",
        "Нефть и битумоиды с содержанием асфальтенов 3–20%",
        "асфальтендері 3–20% мұнай мен битумоидтар",
        "oil and bitumen with 3–20% asphaltenes",
        (
            _color("ОК", "оранжево-коричневый", "orange-brown"),
            _color("СК", "светло-коричневый", "light brown"),
            _color("К", "коричневый", "brown"),
        ),
        "#be3144",
        ("HOB", "RESINOUS", "HIGHOIL", "СМОЛИСТЫЙ"),
    ),
    LbaStandardGroup(
        5,
        "resin_asphaltene",
        "САБ",
        "смолисто-асфальтеновый битумоид",
        "шайырлы-асфальтенді битумоид",
        "resinous-asphaltenic bitumen",
        "Битумоиды с содержанием асфальтенов более 20%",
        "асфальтендері 20%-дан көп битумоидтар",
        "bitumen with more than 20% asphaltenes",
        (
            _color("ТК", "тёмно-коричневый", "dark brown"),
            _color("ЗК", "зеленовато-коричневый", "greenish brown"),
            _color("КК", "красновато-коричневый", "reddish brown"),
            _color("ЧК", "чёрно-коричневый", "black-brown"),
            _color("Ч", "чёрный", "black"),
        ),
        "#8b5757",
        ("VHO", "RESINASPHALTENE", "VERYHIGHOIL", "СМОЛИСТОАСФАЛЬТЕНОВЫЙ"),
    ),
)

_GROUP_BY_NUMBER = {item.group: item for item in LBA_STANDARD_GROUPS}
_GROUP_BY_TYPE: dict[str, LbaStandardGroup] = {}
_GROUPS_BY_COLOR: dict[str, tuple[LbaStandardGroup, ...]] = {}
for _group in LBA_STANDARD_GROUPS:
    for _value in (_group.type_id, _group.code, *_group.aliases):
        _GROUP_BY_TYPE[normalize_lba_key(_value)] = _group
    for _item_color in _group.colors:
        _key = normalize_lba_key(_item_color.code)
        _GROUPS_BY_COLOR[_key] = (*_GROUPS_BY_COLOR.get(_key, ()), _group)


@dataclass(frozen=True, slots=True)
class LbaStandardAssessment:
    standard: LbaStandardGroup
    intensity: int | None
    color_code: str | None
    conflicts: tuple[str, ...] = ()

    @property
    def consistent(self) -> bool:
        return not self.conflicts


def lba_standard_group(group: int | None) -> LbaStandardGroup | None:
    return _GROUP_BY_NUMBER.get(group) if isinstance(group, int) else None


def lba_standard_type(value: str | None) -> LbaStandardGroup | None:
    return _GROUP_BY_TYPE.get(normalize_lba_key(value))


def lba_groups_for_color(value: str | None) -> tuple[LbaStandardGroup, ...]:
    return _GROUPS_BY_COLOR.get(_color_code_key(value), ())


def assess_lba_standard(
    *,
    group: int | None,
    type_id: str | None,
    color: str | None,
    intensity: int | None,
) -> LbaStandardAssessment | None:
    group_match = lba_standard_group(group)
    type_match = lba_standard_type(type_id)
    color_matches = lba_groups_for_color(color)
    color_match = (
        group_match
        if group_match in color_matches
        else type_match
        if type_match in color_matches
        else color_matches[0]
        if len(color_matches) == 1
        else None
    )
    standard = type_match or color_match or group_match
    if standard is None:
        return None
    conflicts: list[str] = []
    if group_match is not None and group_match is not standard:
        conflicts.append(
            f"группа {group_match.group} не соответствует типу {standard.code}"
        )
    if type_match is not None and type_match is not standard:
        conflicts.append(
            f"тип {type_match.code} не соответствует группе {standard.group}"
        )
    if color_matches and standard not in color_matches:
        conflicts.append(
            f"цвет {_display_color_code(color)} не относится к группе {standard.group}"
        )
    normalized_intensity = (
        intensity
        if isinstance(intensity, int)
        and not isinstance(intensity, bool)
        and 1 <= intensity <= 5
        else None
    )
    return LbaStandardAssessment(
        standard,
        normalized_intensity,
        _display_color_code(color) or None,
        tuple(conflicts),
    )


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


def describe_lba_assessment(
    assessment: LbaStandardAssessment,
    language: AppLanguage,
) -> str:
    standard = assessment.standard
    if language is AppLanguage.KK:
        parts = [
            f"{standard.group}-топ",
            f"{standard.code} — {standard.localized_type_name(language)}",
            standard.localized_composition(language),
        ]
        if assessment.color_code:
            parts.append(f"түс {assessment.color_code}")
        if assessment.intensity is not None:
            parts.append(
                f"қарқындылық {assessment.intensity}: "
                f"{lba_intensity_name(assessment.intensity, language)}"
            )
        if assessment.conflicts:
            parts.append("сәйкессіздік: " + "; ".join(assessment.conflicts))
        return "; ".join(parts)
    if language is AppLanguage.EN:
        parts = [
            f"group {standard.group}",
            f"{standard.code} — {standard.localized_type_name(language)}",
            standard.localized_composition(language),
        ]
        if assessment.color_code:
            parts.append(f"colour {assessment.color_code}")
        if assessment.intensity is not None:
            parts.append(
                f"intensity {assessment.intensity}: "
                f"{lba_intensity_name(assessment.intensity, language)}"
            )
        if assessment.conflicts:
            parts.append("mismatch: " + "; ".join(assessment.conflicts))
        return "; ".join(parts)
    parts = [
        f"группа {standard.group}",
        f"{standard.code} — {standard.localized_type_name(language)}",
        standard.localized_composition(language),
    ]
    if assessment.color_code:
        parts.append(f"цвет {assessment.color_code}")
    if assessment.intensity is not None:
        parts.append(
            f"интенсивность {assessment.intensity}: "
            f"{lba_intensity_name(assessment.intensity, language)}"
        )
    if assessment.conflicts:
        parts.append("несоответствие: " + "; ".join(assessment.conflicts))
    return "; ".join(parts)


def all_lba_color_labels(language: AppLanguage) -> tuple[str, ...]:
    seen: set[str] = set()
    labels: list[str] = []
    for group in LBA_STANDARD_GROUPS:
        for item in group.colors:
            if item.code in seen:
                continue
            seen.add(item.code)
            labels.append(item.selection_label(language))
    return tuple(labels)


def lba_color_code(value: str | None) -> str:
    """Return the compact fluorescence code accepted by graph columns and PDF."""

    return _display_color_code(value)


def _display_color_code(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    return re.split(r"\s*[—–-]\s*|\s+", raw, maxsplit=1)[0].upper()


def _color_code_key(value: str | None) -> str:
    return normalize_lba_key(_display_color_code(value))
