from __future__ import annotations

import re
from html import escape

from geoworkbench.calculations.gas_ratio import OPUS_SCREENING_FORMULAS
from geoworkbench.calculations.pixler import build_all_sourced_formula_registry
from geoworkbench.domain.models import Dataset
from geoworkbench.printing.hydrocarbon_interpretation_curve_labels import (
    curve_display_name,
    report_curve_label_hints,
)
from geoworkbench.printing.hydrocarbon_interpretation_pdf_chart import _panel_curves
from geoworkbench.services.hydrocarbon_interpretation import HydrocarbonInterpretationReport
from geoworkbench.services.localization import AppLanguage


# Keep the methodology page focused on interpretation methods rather than
# ordinary acquisition/context channels. These curves may still be plotted on
# the chart; they are intentionally omitted only from "Chart explanations".
_EXCLUDED_EXPLANATION_IDENTIFIERS = frozenset(
    {
        # Drilling speed.
        "ROP",
        "ROP_AVG",
        "ROP5",
        "ROPA",
        "GID106",
        # Flow in/out.
        "FLOW_IN",
        "FLOW",
        "QIN",
        "MFIA",
        "GID1001",
        "FLOW_OUT",
        "QOUT",
        "MFOA",
        "MFOP",
        "GID1003",
        # Total/combustible gas source and calculated aliases.
        "TG",
        "TGAS",
        "TOTALGAS",
        "TOTAL_GAS",
        "TG_CALC",
        "GASA",
        "GID1500",
    }
)

_EXCLUDED_EXPLANATION_RU_TITLES = frozenset(
    {
        "скорость бур",
        "скорость бурения по глубине",
        "расх на вх",
        "расход на входе",
        "расх на вых",
        "расход на выходе",
        "общий газ",
        "сод горюч газ",
        "суммарное сод горючих газов",
    }
)


def _normalized_ru_explanation_title(value: str) -> str:
    """Normalize punctuation so acquisition aliases cannot leak into methodology."""

    return " ".join(
        re.sub(r"[^0-9a-zа-яё]+", " ", value.casefold()).split()
    )


_LABELS = {
    AppLanguage.RU: {
        "title": "Пояснения к графикам",
        "parameter": "Параметр",
        "definition": "Назначение и расчётное соотношение",
        "WH": "Доля компонентов C2–C5 в сумме C1–C5, %.",
        "BH": "Отношение лёгких компонентов C1–C2 к тяжёлым C3–C5.",
        "CH": "Отношение суммы компонентов C4–C5 к пропану C3.",
        "pair": "Кривые Wh и Bh рассматриваются совместно; ΣC4 = iC4 + nC4, ΣC5 = iC5 + nC5.",
        "source": "Значения показанной кривой; единица указана в подписи.",
        "opus": "Расчётный показатель ОПУС по профилю отчёта.",
        "basis": "ОПУС: pi = 100 × Ci / Σ(C1…C5); C4 и C5 включают соответствующие изомеры.",
    },
    AppLanguage.KK: {
        "title": "Графиктерге түсіндірмелер",
        "parameter": "Параметр",
        "definition": "Мақсаты және есептеу қатынасы",
        "WH": "C1–C5 қосындысындағы C2–C5 компоненттерінің үлесі, %.",
        "BH": "Жеңіл C1–C2 компоненттерінің ауыр C3–C5 компоненттеріне қатынасы.",
        "CH": "C4–C5 компоненттері қосындысының C3 пропанына қатынасы.",
        "pair": "Wh және Bh қисықтары бірге қарастырылады; ΣC4 = iC4 + nC4, ΣC5 = iC5 + nC5.",
        "source": "Көрсетілген қисықтың мәндері; өлшем бірлігі қолтаңбада берілген.",
        "opus": "Есеп профилі бойынша ОПУС есептік көрсеткіші.",
        "basis": "ОПУС: pi = 100 × Ci / Σ(C1…C5); C4 және C5 тиісті изомерлерді қамтиды.",
    },
    AppLanguage.EN: {
        "title": "Chart explanations",
        "parameter": "Parameter",
        "definition": "Meaning and calculation",
        "WH": "Share of C2–C5 components in the C1–C5 total, %.",
        "BH": "Ratio of light C1–C2 components to heavy C3–C5 components.",
        "CH": "Ratio of the C4–C5 component sum to propane C3.",
        "pair": "Read Wh and Bh together; ΣC4 = iC4 + nC4, ΣC5 = iC5 + nC5.",
        "source": "Values of the displayed curve; the legend gives its unit.",
        "opus": "Calculated OPUS indicator from the report profile.",
        "basis": "OPUS: pi = 100 × Ci / Σ(C1…C5); C4 and C5 include their respective isomers.",
    },
}


def interpretation_chart_key_html(
    report: HydrocarbonInterpretationReport,
    dataset: Dataset,
    language: AppLanguage,
) -> str:
    """Explain only displayed channels, taking formulas from their calculation contracts."""
    labels = _LABELS[language]
    hints = report_curve_label_hints(report)
    profiles = build_all_sourced_formula_registry().available()
    # Normalization has multiple profiles: a mnemonic alone must not select one.
    expressions: dict[str, set[str]] = {}
    for profile in profiles:
        expressions.setdefault(profile.output_mnemonic.upper(), set()).add(profile.expression)
    expressions["TG_NORM_CALC"] = expressions.get("TG_NORM", set())
    opus_formulas = dict(OPUS_SCREENING_FORMULAS)
    rows: list[str] = []
    seen: set[str] = set()
    for _panel, curves in _panel_curves(report, dataset):
        for curve in curves:
            canonical = (
                hints.get(curve.metadata.original_mnemonic.upper())
                or curve.metadata.canonical_mnemonic
                or curve.metadata.original_mnemonic
            ).upper()
            identifiers = {
                canonical,
                curve.metadata.original_mnemonic.strip().upper(),
                (curve.metadata.canonical_mnemonic or "").strip().upper(),
            }
            title = curve_display_name(curve, language, canonical_hint=canonical)
            if identifiers & _EXCLUDED_EXPLANATION_IDENTIFIERS:
                continue
            if (
                language is AppLanguage.RU
                and _normalized_ru_explanation_title(title)
                in _EXCLUDED_EXPLANATION_RU_TITLES
            ):
                continue
            if canonical in seen:
                continue
            seen.add(canonical)
            candidates = expressions.get(canonical, set())
            formula = next(iter(candidates)) if len(candidates) == 1 else ""
            formula = opus_formulas.get(canonical, formula)
            meaning = labels.get(canonical, labels["opus"] if canonical in opus_formulas
                                 else labels["source"])
            detail = escape(meaning)
            if formula:
                detail += "<br/><b>" + escape(formula) + "</b>"
            rows.append(
                "<tr><td><b>" + escape(title) + "</b></td><td>" + detail + "</td></tr>"
            )
    if not rows:
        return ""
    notes = ""
    if {"WH", "BH"} <= seen:
        notes += "<p>" + escape(labels["pair"]) + "</p>"
    if any(name in opus_formulas for name in seen):
        notes += "<p>" + escape(labels["basis"]) + "</p>"
    return (
        "<h2>" + escape(labels["title"]) + "</h2>"
        '<table width="100%" border="1" cellspacing="0" cellpadding="5">'
        "<thead><tr><th>" + escape(labels["parameter"]) + "</th><th>"
        + escape(labels["definition"]) + "</th></tr></thead><tbody>"
        + "".join(rows) + "</tbody></table>" + notes
    )
