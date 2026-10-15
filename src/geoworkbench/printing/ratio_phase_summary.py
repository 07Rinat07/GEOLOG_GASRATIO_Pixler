"""Readable, evidence-bounded phase key for the Pixler/Haworth print page."""

from __future__ import annotations

from collections import defaultdict
from html import escape
from math import isfinite

from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonCandidateInterval,
    HydrocarbonInterpretationReport,
    fluid_hypothesis_label,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.printing.hydrocarbon_fluid_markers import fluid_marker_spec


def ratio_phase_summary_html(
    report: HydrocarbonInterpretationReport,
    language: AppLanguage,
) -> str:
    """Print *reported* preliminary phase hypotheses, not inferred scatter colours.

    A depth-colour in the Pixler panel identifies the source depth, not the
    presence of oil/gas. Zones absent from the candidate list are unclassified.
    """
    labels = {
        AppLanguage.RU: (
            "Предварительные фазы по выделенным интервалам",
            "Интервал глубины",
            "Предварительная гипотеза",
            "Макс. robust z",
            "Цвет точек и линий Пикслера (Pixler) показывает глубину, а не тип флюида.",
            "Не выделено аномальных интервалов по выбранному порогу.",
            "Непродуктивность интервала и промышленный приток по газовым отношениям не устанавливаются. Жидкая УВ-фаза не является доказательством нефти.",
            "Показаны наиболее выраженные интервалы каждой группы; полный перечень — в таблице ниже.",
        ),
        AppLanguage.KK: (
            "Бөлінген аралықтар бойынша алдын ала фазалар",
            "Тереңдік аралығы",
            "Алдын ала болжам",
            "Макс. robust z",
            "Pixler нүктелері мен сызықтарының түсі флюид түрін емес, тереңдікті көрсетеді.",
            "Таңдалған шек бойынша аномальды аралықтар бөлінбеді.",
            "Өнімсіздік пен өнеркәсіптік ағын тек газ қатынастарымен дәлелденбейді. Сұйық көмірсутек фазасы мұнай табылғанын білдірмейді.",
            "Әр топтың ең айқын аралықтары көрсетілген; толық тізім төмендегі кестеде.",
        ),
        AppLanguage.EN: (
            "Preliminary phases of candidate intervals",
            "Depth interval",
            "Preliminary hypothesis",
            "Max robust z",
            "Pixler point and line colours indicate depth, not fluid phase.",
            "No anomaly intervals were identified at the selected threshold.",
            "Non-productivity and commercial flow cannot be inferred from gas ratios. A liquid-hydrocarbon hypothesis does not prove oil.",
            "The strongest intervals from each group are shown; the complete list follows in the report.",
        ),
    }[language]
    title, interval, phase, strength, colour_note, empty_note, caution, subset_note = labels

    groups: dict[str, list[HydrocarbonCandidateInterval]] = defaultdict(list)
    for candidate in report.candidates:
        spec = fluid_marker_spec(candidate.fluid_hypothesis)
        groups[f"{spec.code} · {fluid_hypothesis_label(candidate, language)}"].append(candidate)

    rows: list[tuple[HydrocarbonCandidateInterval, str]] = []
    for phase_name in sorted(groups):
        ranked = sorted(
            groups[phase_name],
            key=lambda item: (
                -float(item.max_robust_z) if isfinite(float(item.max_robust_z)) else 0.0,
                item.top_depth,
            ),
        )
        rows.extend((candidate, phase_name) for candidate in ranked[:3])
    rows.sort(key=lambda pair: (pair[0].top_depth, pair[0].bottom_depth))
    counts = "; ".join(f"{escape(name)}: {len(items)}" for name, items in sorted(groups.items()))
    parts = [
        "<h2>" + escape(title) + "</h2>",
        "<p>" + escape(colour_note) + "</p>",
        "<p>" + (counts or escape(empty_note)) + "</p>",
    ]
    if rows:
        parts.append(
            "<table style='width:100%'>"
            "<colgroup><col style='width:28%'><col style='width:50%'><col style='width:22%'></colgroup>"
            "<thead><tr>"
            + "".join("<th>" + escape(value) + "</th>" for value in (interval, phase, strength))
            + "</tr></thead><tbody>"
        )
        for candidate, phase_name in rows:
            parts.append(
                "<tr><td>"
                + escape(f"{candidate.top_depth:.2f}–{candidate.bottom_depth:.2f} {report.depth_unit}")
                + "</td><td>" + escape(phase_name)
                + "</td><td>" + escape(f"{candidate.max_robust_z:.2f}")
                + "</td></tr>"
            )
        parts.append("</tbody></table>")
        parts.append("<p>" + escape(subset_note) + "</p>")
    parts.append("<p>" + escape(caution) + "</p>")
    return "<html><body>" + "".join(parts) + "</body></html>"


__all__ = ["ratio_phase_summary_html"]
