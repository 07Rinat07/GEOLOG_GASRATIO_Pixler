"""Opt-in source-first HTML of measured gas/geology interval intersections.

Presentation only. Does not diagnose fluid phase or infer missing assays.
The caller must supply a validated MD evidence snapshot from the INTERP-GEO
correlation service; no LAS, well or gas report is read or mutated here.
"""

from __future__ import annotations

from dataclasses import dataclass
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
        "uncovered": "Интервалы без наблюдений (MD)",
        "complete": "Непокрытых интервалов нет",
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
        "uncovered": "Бақылаусыз аралықтар (MD)",
        "complete": "Қамтылмаған аралықтар жоқ",
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
        "uncovered": "Intervals without observations (MD)",
        "complete": "No uncovered intervals",
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


# Values and record IDs remain verbatim; only the schema-owned field names
# are localized. Percent units belong to measured composition, not LBA codes.
_ATTRIBUTE_LABELS = {
    "lithotype_id": ("ID литотипа", "Литотип ID", "Lithotype ID"),
    "description": ("Описание", "Сипаттама", "Description"),
    "lba_group": ("Группа ЛБА", "ЛБА тобы", "LBA group"),
    "lba_type_id": ("ID типа ЛБА", "ЛБА түрінің ID", "LBA type ID"),
    "lba_intensity": ("Интенсивность ЛБА", "ЛБА қарқындылығы", "LBA intensity"),
    "lba_color": ("Цвет ЛБА", "ЛБА түсі", "LBA color"),
    "lba_distribution": ("Распределение ЛБА", "ЛБА таралуы", "LBA distribution"),
    "lba_cut": ("Вытяжка ЛБА", "ЛБА сорындысы", "LBA solvent cut"),
    "lba_cut_speed": ("Скорость вытяжки ЛБА", "ЛБА сорындысының жылдамдығы", "LBA cut speed"),
    "lba_cut_color": ("Цвет вытяжки ЛБА", "ЛБА сорындысының түсі", "LBA cut color"),
    "lba_residue_type": ("Остаток ЛБА", "ЛБА қалдығы", "LBA residue"),
    "lba_residue_color": ("Цвет остатка ЛБА", "ЛБА қалдығының түсі", "LBA residue color"),
    "lba_odour": ("Запах ЛБА", "ЛБА иісі", "LBA odour"),
    "lba_stain": ("Пятно ЛБА", "ЛБА дағы", "LBA stain"),
    "lba_description": ("Описание ЛБА", "ЛБА сипаттамасы", "LBA description"),
    "calcite_percent": ("Кальцит, %", "Кальцит, %", "Calcite, %"),
    "dolomite_percent": ("Доломит, %", "Доломит, %", "Dolomite, %"),
    "total_carbonate_percent": ("Общие карбонаты, %", "Жалпы карбонаттар, %", "Total carbonate, %"),
    "code": ("Код", "Код", "Code"),
    "name": ("Название", "Атауы", "Name"),
    "rank": ("Ранг", "Дәрежесі", "Rank"),
}


def _measurement_label(key: str, language: AppLanguage) -> str:
    column = {AppLanguage.RU: 0, AppLanguage.KK: 1, AppLanguage.EN: 2}[language]
    if key.startswith("lithotype:"):
        return f"{_ATTRIBUTE_LABELS['lithotype_id'][column]} {key[len('lithotype:'):]}, %"
    labels = _ATTRIBUTE_LABELS.get(key)
    return labels[column] if labels is not None else key


@dataclass(frozen=True, slots=True)
class GeologyEvidenceTable:
    title: str
    intro: str
    interval: str
    coverage_title: str
    coverage_headings: tuple[str, ...]
    coverage_rows: tuple[tuple[str, ...], ...]
    headings: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


def geology_interval_evidence_table(
    evidence: GasGeologyIntervalEvidence,
    language: AppLanguage = AppLanguage.RU,
) -> GeologyEvidenceTable:
    """Project a bounded, escaped view of one already verified MD snapshot.

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

    coverage_rows: list[tuple[str, ...]] = []
    for kind, fraction in evidence.coverage_by_kind:
        if kind not in _KINDS or not isfinite(fraction) or not 0.0 <= fraction <= 1.0:
            raise ValueError("Invalid measured geology coverage entry")
        result = f"{100.0 * fraction:.1f}%" if fraction > 0.0 else words["none"]
        gaps = evidence.uncovered_intervals(kind)
        uncovered = "; ".join(interval(low, high) for low, high in gaps) if gaps else words["complete"]
        coverage_rows.append(
            (_KINDS[kind][language], result, uncovered)
        )

    observed_rows: list[tuple[str, ...]] = []
    for item in evidence.intersections:
        if item.kind not in _KINDS or not (
            evidence.gas_top <= item.overlap_top < item.overlap_bottom <= evidence.gas_bottom
        ):
            raise ValueError("Evidence observation is outside the requested gas interval")
        measurements = "; ".join(
            f"{_measurement_label(key, language)}: {value}" for key, value in item.attributes
        )
        observed_rows.append((
            _KINDS[item.kind][language], item.source_id,
            interval(item.source_top, item.source_bottom),
            interval(item.overlap_top, item.overlap_bottom), measurements,
        ))
    return GeologyEvidenceTable(
        words["title"], words["intro"],
        f"{words['interval']}: {interval(evidence.gas_top, evidence.gas_bottom)}",
        words["coverage"], (words["kind"], words["measured"], words["uncovered"]), tuple(coverage_rows),
        tuple(words[name] for name in ("kind", "source", "bounds", "overlap", "observed")),
        tuple(observed_rows),
    )


def geology_interval_evidence_html(
    evidence: GasGeologyIntervalEvidence,
    language: AppLanguage = AppLanguage.RU,
) -> str:
    presentation = geology_interval_evidence_table(evidence, language)

    def table(headings: tuple[str, ...], rows: tuple[tuple[str, ...], ...]) -> str:
        return (
            "<table><thead><tr>"
            + "".join(f"<th>{escape(cell)}</th>" for cell in headings)
            + "</tr></thead><tbody>"
            + "".join("<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>" for row in rows)
            + ("" if rows else f"<tr><td colspan='5'>{escape(_LABELS[language]['none'])}</td></tr>")
            + "</tbody></table>"
        )

    head = (
        "<section class='gas-geology-evidence' data-axis='MD' "
        f"data-axis-id='{escape(evidence.depth_axis_id, quote=True)}' "
        f"data-dataset-id='{escape(evidence.dataset_id, quote=True)}'>"
        f"<h2>{escape(presentation.title)}</h2>"
        f"<p>{escape(presentation.intro)}</p>"
        f"<p>{escape(presentation.interval)}</p>"
    )
    return (
        head + f"<h3>{escape(presentation.coverage_title)}</h3>"
        + table(presentation.coverage_headings, presentation.coverage_rows)
        + table(presentation.headings, presentation.rows) + "</section>"
    )


__all__ = ["geology_interval_evidence_html", "geology_interval_evidence_table"]
