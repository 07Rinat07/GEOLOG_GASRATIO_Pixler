from __future__ import annotations

from geoworkbench.catalogs.sensors import active_sensor_catalog
from geoworkbench.domain.models import CurveData
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.parameter_labels import localized_curve_name


_RU_CURVE_LABELS: dict[str, str] = {
    "TG_CALC": "Общий газ",
    "TG_NORM_CALC": "Нормализованный общий газ",
    "TG_NORM": "Нормализованный общий газ",
    "NORMALIZED_TOTAL_GAS": "Нормализованный общий газ",
    "TOTAL_GAS_NORM": "Нормализованный общий газ",
    "NORM_TG": "Нормализованный общий газ",
    "TGNORM": "Нормализованный общий газ",
    "WH": "Влажность Haworth",
    "BH": "Баланс Haworth",
    "CH": "Характер Haworth",
    "C1_C2": "Отношение C1/C2",
    "C1_C3": "Отношение C1/C3",
    "C1_C4": "Отношение C1/C4",
    "C1_C5": "Отношение C1/C5",
    "DEXP": "D-exponent",
    "DEXPC": "Скорр. D-exponent",
    "NCT": "Тренд норм. уплотнения",
    "DEXPC_NCT": "DEXPC / тренд NCT",
    "OPUS3": "ОПУС-3",
    "OPUS4": "ОПУС-4",
    "OPUS_K1_3": "ОПУС K1-3",
    "OPUS_1_5": "ОПУС 1-5",
}

_EN_CURVE_LABELS: dict[str, str] = {
    "TG_CALC": "Total gas",
    "TG_NORM_CALC": "Normalized total gas",
    "TG_NORM": "Normalized total gas",
    "NORMALIZED_TOTAL_GAS": "Normalized total gas",
    "TOTAL_GAS_NORM": "Normalized total gas",
    "NORM_TG": "Normalized total gas",
    "TGNORM": "Normalized total gas",
    "WH": "Haworth wetness",
    "BH": "Haworth balance",
    "CH": "Haworth character",
    "C1_C2": "C1/C2 ratio",
    "C1_C3": "C1/C3 ratio",
    "C1_C4": "C1/C4 ratio",
    "C1_C5": "C1/C5 ratio",
    "DEXP": "D-exponent",
    "DEXPC": "Corrected D-exponent",
    "NCT": "Normal compaction trend",
    "DEXPC_NCT": "DEXPC / NCT",
}


def report_curve_label_hints(
    report: HydrocarbonInterpretationReport,
) -> dict[str, str]:
    """Map source-only evidence names to an unambiguous reported method channel."""

    hints: dict[str, str] = {}
    for method in report.methods:
        requested = tuple(
            _strip_source_prefix(str(item))
            for item in method.curve_mnemonics
            if str(item).strip()
        )
        available = tuple(
            _strip_source_prefix(str(item))
            for item in method.available_mnemonics
            if str(item).strip()
        )
        if len(requested) != 1 or len(available) != 1:
            continue
        source = available[0].strip().upper()
        canonical = requested[0].strip().upper()
        if source and canonical and source != canonical:
            hints[source] = canonical
    return hints


def curve_display_name(
    curve: CurveData,
    language: AppLanguage,
    *,
    canonical_hint: str | None = None,
) -> str:
    """Return a readable printed curve name, keeping mnemonics only as fallback."""

    metadata = curve.metadata
    original = metadata.original_mnemonic.strip()
    canonical = (metadata.canonical_mnemonic or "").strip()
    hint = (canonical_hint or "").strip()
    candidates = tuple(
        dict.fromkeys(
            item
            for item in (hint, canonical, original)
            if item
        )
    )

    labels = (
        _RU_CURVE_LABELS
        if language is AppLanguage.RU
        else _EN_CURVE_LABELS
        if language is AppLanguage.EN
        else {}
    )
    for candidate in candidates:
        label = labels.get(candidate.upper())
        if label:
            return label

    description = (metadata.description or "").strip()

    for candidate in candidates:
        readable = localized_curve_name(
            candidate,
            description=description,
            unit=metadata.unit or "",
            language=language,
        ).strip()
        if readable and readable.casefold() != candidate.casefold():
            return readable

    if language is AppLanguage.RU:
        catalog = active_sensor_catalog()
        semantic = metadata.semantic
        if semantic is not None and semantic.sensor_id:
            try:
                definition = catalog.definition(semantic.sensor_id)
            except KeyError:
                pass
            else:
                return definition.short_name_ru or definition.name_ru

    if description and description.casefold() not in {
        item.casefold() for item in candidates
    }:
        return _compact_description(description)

    fallback = localized_curve_name(
        hint or canonical or original,
        description=description,
        unit=metadata.unit or "",
        language=language,
    )
    return fallback.replace("_", "/")


def curve_legend_text(
    curve: CurveData,
    low: float,
    high: float,
    language: AppLanguage,
    *,
    canonical_hint: str | None = None,
) -> str:
    label = curve_display_name(
        curve,
        language,
        canonical_hint=canonical_hint,
    )
    unit = f" [{curve.metadata.unit}]" if curve.metadata.unit else ""
    return f"{label}{unit}  p5={low:.4g}; p95={high:.4g}"


def _strip_source_prefix(value: str) -> str:
    stripped = value.strip()
    for prefix in ("server:", "local-calculation:"):
        if stripped.casefold().startswith(prefix):
            return stripped[len(prefix) :].strip()
    return stripped


def _compact_description(value: str, *, maximum: int = 42) -> str:
    text = " ".join(value.split())
    if len(text) <= maximum:
        return text
    return text[: maximum - 1].rstrip() + "…"


__all__ = [
    "curve_display_name",
    "curve_legend_text",
    "report_curve_label_hints",
]
