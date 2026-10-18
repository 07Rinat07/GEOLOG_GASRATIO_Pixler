"""Opt-in source-first HTML of measured gas/geology interval intersections.

Presentation only. Does not diagnose fluid phase or infer missing assays.
The caller must supply a validated MD evidence snapshot from the INTERP-GEO
correlation service; no LAS, well or gas report is read or mutated here.
"""

from __future__ import annotations

from html import escape
from math import isfinite

from geoworkbench.services.interpretation_geology_interval_evidence import (
    EvidenceKind,
    GasGeologyIntervalEvidence,
)
from geoworkbench.services.localization import AppLanguage


_LABELS: dict[AppLanguage, dict[str, str]] = {
    AppLanguage.RU: {
        "title": "Фактическое пересечение газового интервала и геологических данных (MD)",
        "intro": (
            "Показаны только сохранённые наблюдения и измерения. "
            "Отсутствие пробы не означает отрицательного результата; "
            "сопадение по глубине не доказывает состав флюида или продуктивность."
        ),
        "coverage": "Покрытие исходными наблюдениями",
        "kind": "Тип данных",
        "measured": "Покрыто, % длины",
        "source": "Источник (ID записи)",
        "bounds": "Интервал источника",
        "overlap": "Пересечение с газовым интервалом",
        "observed": "Сохранённые показатели",
        "none": "Нет измерений / сведений",
        "interval": "Газовый интервал",
    },
    AppLanguage.KK: {
        "title": "Газ аралығы мен геологиялық деректердің нақты қиылысуы (MD)",
        "intro": (
            "Тек сақталған бақылаулар мен өлшеулер көрсетіледі. "
            "Үлгінің болмауы теріс нәтиже емес; тереңдіктің сәйкес келуі "
            "флюид құрамын немесе қабат өнімділігін дәлелдемейді."
        ),
        "coverage": "Бастапқы бақылаулармен қамтылуы",
        "kind": "Деректер түрі",
        "measured": "Қамтылған ұзындық, %",
        "source": "Дереккөз (жазба ID)",
        "bounds": "Дереккөз аралығы",
        "overlap": "Газ аралығымен қиылысуы",
        "observed": "Сақталған көрсеткіштер",
        "none": "Өлшеулер / мәліметтер жоқ",
        "interval": "Газ аралығы",
    },
    AppLanguage.EN: {
        "title": "Measured gas interval and geological evidence intersection (MD)",
        "intro": (
            "Only saved observations and measurements are shown. "
            "An absent sample is not a negative result; depth overlap "
            "does not prove fluid phase or formation productivity."
        ),
        "coverage": "Coverage by source observations",
        "kind": "Evidence type",
        "measured": "Covered length, %",
        "source": "Source record ID",
        "bounds": "Source interval",
        "overlap": "Gas interval intersection",
        "observed": "Recorded measurements",
        "none": "No measurement / record",
        "interval": "Gas interval",
    },
}

_KINDS: dict[EvidenceKind, dict[AppLanguage, str]] = {
    "lithology": {
        AppLanguage.RU: "Литология",
        AppLanguage.KK: "Литология",
        AppLanguage.EN: "Lithology",
    },
    "cuttings": {
        AppLanguage.RU: "Шлам",
        AppLanguage.KK: "Шлам",
        AppLanguage.EN: "Cuttings",
    },
    "lba": {
        AppLanguage.RU: "ЛБА",
        AppLanguage.KK: "ЛБА",
        AppLanguage.EN: "LBA",
    },
    "calcimetry": {
        AppLanguage.RU: "Кальциметрия",
        AppLanguage.KK: "Кальциметрия",
        AppLanguage.EN: "Calcimetry",
    },
    "stratigraphy": {
        AppLanguage.RU: "Стратиграфия",
        AppLanguage.KK: "Стратиграфия",
        AppLanguage.EN: "Stratigraphy",
    },
}


def geology_interval_evidence_html(
    evidence: GasGeologyIntervalEvidence,
    language: AppLanguage = AppLanguage.RU,
) -> str:
    """Render a bounded, escaped view of one already verified MD snapshot.

    Zero *coverage* displays as unavailable rather than as a false negative.
    A measured zero carbonate value remains visible as '0'. Coverage is a
    depth-union fraction, never a percentage of positive assay results.
    """

    if evidence.depth_unit != "m" or not (
        isfinite(evidence.gas_top)
        and isfinite(evidence.gas_bottom)
        and evidence.gas_bottom > evidence.gas_top
    ):
        raise ValueError("Source evidence must use an increasing MD interval in metres")
    words = _LABELS[language]

    def fmt(value: float) -> str:
        return f"{value:.2f}"

    def interval(low: float, high: float) -> str:
        return f"{fmt(low)}–{fmt(high)} m"

    def td(value: object) -> str:
        return f"<td>{escape(str(value))}</td>"

    coverage_rows: list[str] = []
    for kind, fraction in evidence.coverage_by_kind:
        if kind not in _KINDS or not isfinite(fraction) or not 0.0 <= fraction <= 1.0:
            raise ValueError("Invalid measured geology coverage entry")
        result = f"{100.0 * fraction:.1f}%" if fraction > 0.0 else words["none"]
        coverage_rows.append(
            f"<tr>{td(_KINDS[kind][language])}{td(result)}</tr>"
        )

    observed_rows: list[str] = []
    for item in evidence.intersections:
        if item.kind not in _KINDS or not (
            evidence.gas_top <= item.overlap_top < item.overlap_bottom <= evidence.gas_bottom
        ):
            raise ValueError("Evidence observation is outside the requested gas interval")
        measurements = "; ".join(f"{key}: {value}" for key, value in item.attributes)
        observed_rows.append(
            "<tr>" + "".join((
                td(_KINDS[item.kind][language]),
                td(item.source_id),
                td(interval(item.source_top, item.source_bottom)),
                td(interval(item.overlap_top, item.overlap_bottom)),
                td(measurements),
            )) + "</tr>"
        )

    head = (
        "<section class='gas-geology-evidence' data-axis='MD' "
        f"data-axis-id='{escape(evidence.depth_axis_id, quote=True)}' "
        f"data-dataset-id='{escape(evidence.dataset_id, quote=True)}'>"
        f"<h2>{escape(words['title'])}</h2>"
        f"<p>{escape(words['intro'])}</p>"
        f"<p>{escape(words['interval'])}: "
        f"{escape(interval(evidence.gas_top, evidence.gas_bottom))}</p>"
    )
    overview = (
        f"<h3>{escape(words['coverage'])}</h3><table><thead><tr>"
        f"<th>{escape(words['kind'])}</th><th>{escape(words['measured'])}</th>"
        "</tr></thead><tbody>" + "".join(coverage_rows) + "</tbody></table>"
    )
    observations = (
        "<table><thead><tr>"
        + "".join(
            f"<th>{escape(words[name])}</th>"
            for name in ("kind", "source", "bounds", "overlap", "observed")
        )
        + "</tr></thead><tbody>"
        + ("".join(observed_rows) if observed_rows else (
            f"<tr><td colspan='5'>{escape(words['none'])}</td></tr>"
        ))
        + "</tbody></table>"
    )
    return head + overview + observations + "</section>"


__all__ = ["geology_interval_evidence_html"]
