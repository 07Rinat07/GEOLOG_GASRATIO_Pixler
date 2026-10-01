from __future__ import annotations

import re

from geoworkbench.catalogs.sensors import active_sensor_catalog
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.text_normalization import clean_display_text, clean_mnemonic

_CYRILLIC_RE = re.compile(r"[А-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі]")
_VENDOR_SENSOR_CODE_RE = re.compile(r"^(?:S|GID)\d+$", re.IGNORECASE)
_GENERIC_SOURCE_CHANNEL_RE = re.compile(
    r"^(?:исходн(?:ый|ая|ое)\s+(?:канал|кривая)|source\s+channel|"
    r"бастапқы\s+арна|канал)\s*(?:S|GID)?\d*$",
    re.IGNORECASE,
)

_RUSSIAN_NAMES: dict[str, str] = {
    "TOTAL_GAS": "Общий газ",
    "TG": "Общий газ",
    "TG_NORM": "Нормализованный общий газ",
    "TG_NORM_CALC": "Расчётный нормализованный общий газ",
    "C1": "Содержание метана",
    "C2": "Этан",
    "C3": "Пропан",
    "C4": "Бутан",
    "C5": "Пентан",
    "IC4": "Изобутан",
    "NC4": "н-Бутан",
    "IC5": "Изопентан",
    "NC5": "н-Пентан",
    "H2S": "Сероводород",
    "CO2": "Диоксид углерода",
    "N2": "Азот",
    "C1_NORM": "Нормализованный метан",
    "C1_NORM_REF": "Нормализованный метан по опорной кривой",
    "C2_NORM": "Нормализованный этан",
    "C3_NORM": "Нормализованный пропан",
    "IC4_NORM": "Нормализованный изобутан",
    "NC4_NORM": "Нормализованный н-бутан",
    "IC5_NORM": "Нормализованный изопентан",
    "NC5_NORM": "Нормализованный н-пентан",
    "WH": "Влажность Haworth",
    "BH": "Баланс Haworth",
    "CH": "Характер Haworth",
    "C1_C2": "Отношение C1/C2",
    "C1_C3": "Отношение C1/C3",
    "C1_C4": "Отношение C1/C4",
    "C1_C5": "Отношение C1/C5",
    "DEXP": "D-exponent",
    "DEXPC": "Скорректированный D-exponent",
    "DEXPC_NCT": "DEXPC / тренд NCT",
    "NCT": "Тренд нормального уплотнения",
    "OPUS3": "ОПУС-3",
    "OPUS_TG_PCT": "Общий газ ОПУС",
    "OPUS4": "ОПУС-4",
    "OPUS_K1_3": "ОПУС K1-3",
    "OPUS_1_5": "ОПУС 1-5",
}

_ENGLISH_NAMES: dict[str, str] = {
    "TOTAL_GAS": "Total Gas",
    "TG": "Total Gas",
    "TG_NORM": "Normalized Total Gas",
    "TG_NORM_CALC": "Calculated Normalized Total Gas",
    "C1_NORM": "Normalized Methane",
    "C1_NORM_REF": "Reference-normalized Methane",
    "C2_NORM": "Normalized Ethane",
    "C3_NORM": "Normalized Propane",
    "IC4_NORM": "Normalized Isobutane",
    "NC4_NORM": "Normalized n-Butane",
    "IC5_NORM": "Normalized Isopentane",
    "NC5_NORM": "Normalized n-Pentane",
    "C1": "Methane",
    "C2": "Ethane",
    "C3": "Propane",
    "C4": "Butane",
    "C5": "Pentane",
    "IC4": "Isobutane",
    "NC4": "n-Butane",
    "IC5": "Isopentane",
    "NC5": "n-Pentane",
    "H2S": "Hydrogen sulfide",
    "CO2": "Carbon dioxide",
    "N2": "Nitrogen",
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
    "WH": "Haworth Wetness",
    "BH": "Haworth Balance",
    "CH": "Haworth Character",
    "C1_C2": "C1/C2 Ratio",
    "C1_C3": "C1/C3 Ratio",
    "C1_C4": "C1/C4 Ratio",
    "C1_C5": "C1/C5 Ratio",
    "DEXP": "D-exponent",
    "DEXPC": "Corrected D-exponent",
    "DEXPC_NCT": "DEXPC / NCT trend",
    "NCT": "Normal Compaction Trend",
    "OPUS3": "OPUS-3",
    "OPUS_TG_PCT": "OPUS total gas",
    "OPUS4": "OPUS-4",
    "OPUS_K1_3": "OPUS K1-3",
    "OPUS_1_5": "OPUS 1-5",
}

_KAZAKH_NAMES: dict[str, str] = {
    "TOTAL_GAS": "Жалпы газ",
    "TG": "Жалпы газ",
    "TG_NORM": "Нормаланған жалпы газ",
    "TG_NORM_CALC": "Есептелген нормаланған жалпы газ",
    "C1_NORM": "Нормаланған метан",
    "C1_NORM_REF": "Тірек қисығы бойынша нормаланған метан",
    "C2_NORM": "Нормаланған этан",
    "C3_NORM": "Нормаланған пропан",
    "IC4_NORM": "Нормаланған изобутан",
    "NC4_NORM": "Нормаланған н-бутан",
    "IC5_NORM": "Нормаланған изопентан",
    "NC5_NORM": "Нормаланған н-пентан",
    "C1": "Метан",
    "C2": "Этан",
    "C3": "Пропан",
    "C4": "Бутан",
    "C5": "Пентан",
    "IC4": "Изобутан",
    "NC4": "н-Бутан",
    "IC5": "Изопентан",
    "NC5": "н-Пентан",
    "H2S": "Күкіртсутек",
    "CO2": "Көмірқышқыл газы",
    "N2": "Азот",
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
    "WH": "Haworth ылғалдылығы",
    "BH": "Haworth балансы",
    "CH": "Haworth сипаты",
    "C1_C2": "C1/C2 қатынасы",
    "C1_C3": "C1/C3 қатынасы",
    "C1_C4": "C1/C4 қатынасы",
    "C1_C5": "C1/C5 қатынасы",
    "DEXP": "D-exponent",
    "DEXPC": "Түзетілген D-exponent",
    "DEXPC_NCT": "DEXPC / NCT тренді",
    "NCT": "Қалыпты тығыздалу тренді",
    "OPUS_TG_PCT": "ОПУС жалпы газы",
    "OPUS3": "ОПУС-3",
    "OPUS4": "ОПУС-4",
    "OPUS_K1_3": "ОПУС K1-3",
    "OPUS_1_5": "ОПУС 1-5",
}


def _canonical_title(canonical: str) -> str:
    normalized = canonical.strip().upper()
    if normalized in _ENGLISH_NAMES:
        return _ENGLISH_NAMES[normalized]
    tokens = normalized.replace("_", " ").split()
    return " ".join(
        token if any(character.isdigit() for character in token) else token.title()
        for token in tokens
    )


_REPORT_LEGACY_CANONICAL: dict[str, str] = {
    # Legacy GID observed in the interpretation-method source mapping.
    # Keep this presentation-only: domain/audit data retains the exact S224 code.
    "S224": "DEXP",
}


_SOURCE_REFERENCE_LABELS: dict[AppLanguage, dict[str, str]] = {
    AppLanguage.RU: {
        "server": "Сервер/файл",
        "local-calculation": "Локальный расчёт",
    },
    AppLanguage.KK: {
        "server": "Сервер/файл",
        "local-calculation": "Жергілікті есеп",
    },
    AppLanguage.EN: {
        "server": "Server/file",
        "local-calculation": "Local calculation",
    },
}


def localized_curve_reference(
    reference: str,
    *,
    language: AppLanguage = AppLanguage.RU,
) -> str:
    """Humanize one or more report curve references without exposing source mnemonics.

    Domain/report objects keep exact mnemonics for reproducibility. This helper is
    presentation-only: visible reports get a localized physical parameter name,
    while source prefixes remain readable provenance labels.
    """

    parts: list[str] = []
    for raw_part in str(reference).split("|"):
        part = raw_part.strip()
        if not part:
            continue
        source = ""
        mnemonic = part
        for prefix in ("server:", "local-calculation:"):
            if part.casefold().startswith(prefix):
                source = prefix[:-1]
                mnemonic = part[len(prefix) :].strip()
                break
        display_mnemonic = _REPORT_LEGACY_CANONICAL.get(
            mnemonic.strip().upper(),
            mnemonic,
        )
        readable = localized_curve_name(display_mnemonic, language=language)
        if source:
            source_label = _SOURCE_REFERENCE_LABELS[language].get(source, source)
            parts.append(f"{source_label}: {readable}")
        else:
            parts.append(readable)
    return " | ".join(dict.fromkeys(parts))


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

    mnemonic = clean_mnemonic(mnemonic)
    description = clean_display_text(description)
    unit = clean_display_text(unit)
    explicit = clean_display_text(configured)

    match = active_sensor_catalog().match(
        mnemonic,
        description=description,
        unit=unit,
    )
    # Old layouts often persisted the raw LAS mnemonic as ``display_name``.
    # That is not a deliberate user caption and must not suppress a newly
    # available catalog translation such as S300 -> Давление на манифольде.
    technical_names = {mnemonic.casefold()}
    generated_names = set(technical_names)
    if match is not None:
        definition = match.definition
        canonical = definition.canonical_mnemonic.strip().upper()
        generated_names.update(
            name.strip().casefold()
            for name in (
                definition.canonical_mnemonic,
                definition.name_ru,
                definition.short_name_ru,
                _ENGLISH_NAMES.get(canonical, ""),
                _KAZAKH_NAMES.get(canonical, ""),
                _canonical_title(canonical),
            )
            if name and name.strip()
        )
    if explicit and explicit.casefold() not in generated_names:
        return explicit

    if match is not None:
        definition = match.definition
        canonical = definition.canonical_mnemonic.strip().upper()
        if language is AppLanguage.RU:
            # Legacy Sensors.DB gas rows often use a technical code (C1, C2, ...)
            # as both the long and short Russian caption.  Reports should show
            # the physical parameter name while retaining the mnemonic separately
            # where traceability is needed.
            return _RUSSIAN_NAMES.get(
                canonical,
                (definition.name_ru or definition.short_name_ru or mnemonic).strip(),
            )
        if language is AppLanguage.KK:
            return _KAZAKH_NAMES.get(canonical, _canonical_title(canonical))
        return _ENGLISH_NAMES.get(canonical, _canonical_title(canonical))

    canonical = mnemonic.strip().upper()
    known_names = (
        _RUSSIAN_NAMES
        if language is AppLanguage.RU
        else _KAZAKH_NAMES
        if language is AppLanguage.KK
        else _ENGLISH_NAMES
    )
    if canonical in known_names:
        return known_names[canonical]

    clean_description = description.strip()
    is_vendor_code = bool(_VENDOR_SENSOR_CODE_RE.fullmatch(mnemonic))
    is_generic_description = bool(
        clean_description and _GENERIC_SOURCE_CHANNEL_RE.fullmatch(clean_description)
    )
    if is_vendor_code and (not clean_description or is_generic_description):
        if language is AppLanguage.KK:
            return "Анықталмаған арна"
        if language is AppLanguage.EN:
            return "Unknown channel"
        return "Неопределённый канал"
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
