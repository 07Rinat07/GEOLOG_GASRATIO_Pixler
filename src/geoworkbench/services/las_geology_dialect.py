from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
import unicodedata


class GeologyChannelRole(StrEnum):
    PRIMARY_LITHOLOGY = "primary_lithology"
    CUTTINGS_CODE = "cuttings_code"
    CUTTINGS_AMOUNT = "cuttings_amount"
    CALCITE = "calcite"
    DOLOMITE = "dolomite"
    LEGACY_CARBONATE = "legacy_carbonate"
    LBA_GROUP = "lba_group"
    LBA_INTENSITY = "lba_intensity"
    LBA_TYPE = "lba_type"
    LBA_COLOR = "lba_color"
    STRATIGRAPHY_CODE = "stratigraphy_code"
    DESCRIPTION_ID = "description_id"


@dataclass(frozen=True, slots=True)
class GeologyChannelMatch:
    role: GeologyChannelRole
    slot: int | None = None
    confidence: float = 1.0
    matched_by: str = "mnemonic_alias"


_TOKEN = re.compile(r"[^0-9A-ZА-ЯЁ]+", re.IGNORECASE)
_SLOT = re.compile(
    r"^(?:ПОРОДА|ROCK|LITH|LITHOLOGY)_?(?P<slot>[1-5])_?"
    r"(?P<field>КОД|CODE|КОЛИЧ|AMOUNT|PCT|PERCENT|PERCENTAGE)$",
    re.IGNORECASE,
)


def normalize_geology_mnemonic(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value)).strip().upper().replace("Ё", "Е")
    return _TOKEN.sub("_", text).strip("_")


_ALIASES: dict[GeologyChannelRole, frozenset[str]] = {
    GeologyChannelRole.PRIMARY_LITHOLOGY: frozenset(
        normalize_geology_mnemonic(value)
        for value in (
            "КОД_ПОРОДЫ",
            "LITH_CODE",
            "LITHOLOGY_CODE",
            "ROCK_CODE",
            "LITHCODE",
        )
    ),
    GeologyChannelRole.CALCITE: frozenset(
        normalize_geology_mnemonic(value)
        for value in ("CACO3", "CALCITE", "CACO3_(КАЛЬЦИТ)", "КАЛЬЦИТ")
    ),
    GeologyChannelRole.DOLOMITE: frozenset(
        normalize_geology_mnemonic(value)
        for value in ("CAMG_CO3_2", "DOLOMITE", "DOLO", "ДОЛОМИТ")
    ),
    GeologyChannelRole.LEGACY_CARBONATE: frozenset(
        normalize_geology_mnemonic(value)
        for value in (
            "КАРБОНАТНОСТЬ",
            "CARBONATE",
            "CARBONATE_CONTENT",
            "TOTAL_CARBONATE",
            "CARBONATES",
        )
    ),
    GeologyChannelRole.LBA_GROUP: frozenset(
        normalize_geology_mnemonic(value)
        for value in (
            "LBA_GROUP",
            "ЛБА_ГРУППА",
            "LBA_GRP",
            "LBA_CLASS",
            "ЛБА_КЛАСС",
        )
    ),
    GeologyChannelRole.LBA_INTENSITY: frozenset(
        normalize_geology_mnemonic(value)
        for value in (
            "INTENSITY_LBA",
            "LBA_INTENSITY",
            "ЛБА_ИНТЕНСИВНОСТЬ",
            "LBA_INT",
        )
    ),
    GeologyChannelRole.LBA_TYPE: frozenset(
        normalize_geology_mnemonic(value)
        for value in ("LBA_TYPE", "ЛБА_ТИП", "LBA_KIND")
    ),
    GeologyChannelRole.LBA_COLOR: frozenset(
        normalize_geology_mnemonic(value)
        for value in ("ZVET_LBA", "LBA_COLOR", "ЛБА_ЦВЕТ", "LBA_COLOUR")
    ),
    GeologyChannelRole.STRATIGRAPHY_CODE: frozenset(
        normalize_geology_mnemonic(value)
        for value in (
            "STRAT_CODE",
            "СТРАТ_КОД",
            "STRATIGRAPHY_CODE",
            "STRATCODE",
        )
    ),
    GeologyChannelRole.DESCRIPTION_ID: frozenset(
        normalize_geology_mnemonic(value)
        for value in (
            "GEO_DESC_ID",
            "ОПИСАНИЕ_ID",
            "DESCRIPTION_ID",
            "LITH_DESC_ID",
            "GEO_DESCRIPTION_ID",
        )
    ),
}


def resolve_geology_channel(
    mnemonic: str,
    *,
    description: str = "",
    unit: str = "",
) -> GeologyChannelMatch | None:
    """Resolve a portable geology role conservatively.

    Exact mnemonic aliases are authoritative. Description-based fallback is used
    only for strongly identifying phrases and compatible code/percent units.
    Unknown vendor curves remain ordinary LAS curves.
    """

    normalized = normalize_geology_mnemonic(mnemonic)
    slot_match = _SLOT.fullmatch(normalized)
    if slot_match is not None:
        slot = int(slot_match.group("slot"))
        field = slot_match.group("field").upper()
        role = (
            GeologyChannelRole.CUTTINGS_CODE
            if field in {"КОД", "CODE"}
            else GeologyChannelRole.CUTTINGS_AMOUNT
        )
        return GeologyChannelMatch(role=role, slot=slot)

    for role, aliases in _ALIASES.items():
        if normalized in aliases:
            return GeologyChannelMatch(role=role)

    desc = unicodedata.normalize("NFKC", description).casefold().replace("ё", "е")
    normalized_unit = normalize_geology_mnemonic(unit)
    percent_like = normalized_unit in {"", "PCT", "PERCENT"}
    code_like = normalized_unit in {"", "CODE", "ID", "INT"}

    if percent_like:
        if "caco3" in desc or "calcite" in desc or "кальцит" in desc:
            return GeologyChannelMatch(
                GeologyChannelRole.CALCITE,
                confidence=0.9,
                matched_by="description+uom",
            )
        if "camg" in desc or "dolomite" in desc or "доломит" in desc:
            return GeologyChannelMatch(
                GeologyChannelRole.DOLOMITE,
                confidence=0.9,
                matched_by="description+uom",
            )
        if "carbonate content" in desc or "карбонатност" in desc:
            return GeologyChannelMatch(
                GeologyChannelRole.LEGACY_CARBONATE,
                confidence=0.85,
                matched_by="description+uom",
            )

    if code_like:
        has_lba = "lba" in desc or "лба" in desc
        if has_lba and ("group" in desc or "групп" in desc or "class" in desc):
            return GeologyChannelMatch(
                GeologyChannelRole.LBA_GROUP,
                confidence=0.85,
                matched_by="description+uom",
            )
        if has_lba and ("intens" in desc or "интенсив" in desc):
            return GeologyChannelMatch(
                GeologyChannelRole.LBA_INTENSITY,
                confidence=0.85,
                matched_by="description+uom",
            )
        if has_lba and ("type" in desc or "тип" in desc or "kind" in desc):
            return GeologyChannelMatch(
                GeologyChannelRole.LBA_TYPE,
                confidence=0.85,
                matched_by="description+uom",
            )
        if has_lba and ("color" in desc or "colour" in desc or "цвет" in desc):
            return GeologyChannelMatch(
                GeologyChannelRole.LBA_COLOR,
                confidence=0.85,
                matched_by="description+uom",
            )
        if ("stratigraph" in desc or "стратиграф" in desc) and (
            "code" in desc or "код" in desc
        ):
            return GeologyChannelMatch(
                GeologyChannelRole.STRATIGRAPHY_CODE,
                confidence=0.85,
                matched_by="description+uom",
            )
        if (
            ("description" in desc or "описани" in desc)
            and ("id" in desc or "идентифик" in desc or "код" in desc)
        ):
            return GeologyChannelMatch(
                GeologyChannelRole.DESCRIPTION_ID,
                confidence=0.85,
                matched_by="description+uom",
            )
    return None


__all__ = [
    "GeologyChannelMatch",
    "GeologyChannelRole",
    "normalize_geology_mnemonic",
    "resolve_geology_channel",
]
