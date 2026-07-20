from __future__ import annotations

import re

from geoworkbench.catalogs.sensors import active_sensor_catalog
from geoworkbench.services.localization import AppLanguage

_CYRILLIC_RE = re.compile(r"[А-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі]")

_ENGLISH_NAMES: dict[str, str] = {
    "TOTAL_GAS": "Total Gas",
    "TG": "Total Gas",
    "C1": "Methane",
    "C2": "Ethane",
    "C3": "Propane",
    "C4": "Butane",
    "C5": "Pentane",
    "IC4": "Isobutane",
    "NC4": "n-Butane",
    "IC5": "Isopentane",
    "NC5": "n-Pentane",
    "ROP": "Rate of Penetration",
    "WOB": "Weight on Bit",
    "RPM": "Rotary Speed",
    "TQ": "Rotary Torque",
    "SPP": "Standpipe Pressure",
    "HKLD": "Hook Load",
    "MW_IN": "Mud Density In",
    "MW_OUT": "Mud Density Out",
    "TEMP_IN": "Mud Temperature In",
    "TEMP_OUT": "Mud Temperature Out",
    "PIT_VOL": "Total Pit Volume",
    "FLOW_IN": "Flow In",
    "FLOW_OUT": "Flow Out",
    "GR": "Gamma Ray",
    "SP": "Spontaneous Potential",
    "BHT": "Downhole Temperature",
    "BHP": "Downhole Pressure",
    "HOLE_DEPTH": "Hole Depth",
    "BIT_DEPTH": "Bit Depth",
}

_KAZAKH_NAMES: dict[str, str] = {
    "TOTAL_GAS": "Жалпы газ",
    "TG": "Жалпы газ",
    "C1": "Метан",
    "C2": "Этан",
    "C3": "Пропан",
    "C4": "Бутан",
    "C5": "Пентан",
    "IC4": "Изобутан",
    "NC4": "н-Бутан",
    "IC5": "Изопентан",
    "NC5": "н-Пентан",
    "ROP": "Бұрғылау жылдамдығы",
    "WOB": "Қашауға түсетін салмақ",
    "RPM": "Айналу жиілігі",
    "TQ": "Айналдыру моменті",
    "SPP": "Айдау қысымы",
    "HKLD": "Ілмектегі салмақ",
    "MW_IN": "Кірістегі ерітінді тығыздығы",
    "MW_OUT": "Шығыстағы ерітінді тығыздығы",
    "TEMP_IN": "Кірістегі ерітінді температурасы",
    "TEMP_OUT": "Шығыстағы ерітінді температурасы",
    "PIT_VOL": "Ыдыстардағы жалпы көлем",
    "FLOW_IN": "Кіріс шығыны",
    "FLOW_OUT": "Шығыс шығыны",
    "GR": "Гамма-каротаж",
    "SP": "Өздік потенциал",
    "BHT": "Ұңғыма температурасы",
    "BHP": "Ұңғыма қысымы",
    "HOLE_DEPTH": "Ұңғыма тереңдігі",
    "BIT_DEPTH": "Қашау тереңдігі",
}


def _canonical_title(canonical: str) -> str:
    normalized = canonical.strip().upper()
    if normalized in _ENGLISH_NAMES:
        return _ENGLISH_NAMES[normalized]
    tokens = normalized.replace("_", " ").split()
    return " ".join(token if any(character.isdigit() for character in token) else token.title() for token in tokens)


def localized_curve_name(
    mnemonic: str,
    *,
    description: str = "",
    unit: str = "",
    language: AppLanguage = AppLanguage.RU,
    configured: str = "",
) -> str:
    """Return a readable, language-consistent label for a LAS curve.

    Explicit user names always win. Known mnemonics use the Sensors catalog. Unknown
    curves retain a meaningful LAS description only when it is compatible with the
    active interface language; otherwise their mnemonic remains the safest label.
    """

    explicit = configured.strip()
    if explicit:
        return explicit

    match = active_sensor_catalog().match(
        mnemonic,
        description=description,
        unit=unit,
    )
    if match is not None:
        definition = match.definition
        canonical = definition.canonical_mnemonic.strip().upper()
        if language is AppLanguage.RU:
            return (definition.name_ru or definition.short_name_ru or mnemonic).strip()
        if language is AppLanguage.KK:
            return _KAZAKH_NAMES.get(canonical, _canonical_title(canonical))
        return _ENGLISH_NAMES.get(canonical, _canonical_title(canonical))

    clean_description = description.strip()
    if not clean_description:
        return mnemonic
    if language is AppLanguage.RU:
        return clean_description
    if language is AppLanguage.KK and _CYRILLIC_RE.search(clean_description):
        # Russian vendor descriptions are not silently presented as Kazakh UI text.
        return mnemonic
    if language is AppLanguage.EN and _CYRILLIC_RE.search(clean_description):
        return mnemonic
    return clean_description
