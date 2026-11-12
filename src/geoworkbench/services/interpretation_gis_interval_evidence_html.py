"""Localized read-only presentation of combined MD evidence.

The GIS table describes discrete rows; geological coverage remains a separate
depth-union table. This is a presentation adapter, not a report approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from geoworkbench.services.interpretation_geology_interval_evidence import EvidenceKind
from geoworkbench.services.interpretation_geology_interval_evidence_html import (
    geology_interval_evidence_html,
)
from geoworkbench.services.interpretation_gis_interval_evidence import (
    GasGeologyGisIntervalEvidence,
)
from geoworkbench.services.localization import AppLanguage


@dataclass(frozen=True, slots=True)
class GisEvidenceTable:
    title: str
    notice: str
    headings: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    empty: str


_LABELS = {
    AppLanguage.RU: (
        "Исходные отсчёты ГИС (MD)",
        "Число отсчётов и крайние точки не означают непрерывное покрытие. "
        "Совпадение глубин не доказывает насыщение или продуктивность.",
        ("Кривая (ключ)", "ID кривой", "ID набора", "Единица", "Происхождение",
         "Строки", "Конечные значения", "Пропуски", "Границы MD, м",
         "Диапазон значений", "Состояние"),
        "Кривые ГИС не выбраны", "Заблокировано", "Нет строк",
        "Нет конечных значений", "Проверено",
    ),
    AppLanguage.KK: (
        "ГИС бастапқы есептері (MD)",
        "Есептер саны мен шеткі нүктелер үздіксіз қамтуды білдірмейді. "
        "Тереңдіктің сәйкес келуі қанығуды немесе өнімділікті дәлелдемейді.",
        ("Қисық (кілт)", "Қисық ID", "Жинақ ID", "Өлшем бірлігі", "Дерек көзі",
         "Жолдар", "Ақырлы мәндер", "Бос мәндер", "MD шектері, м",
         "Мәндер ауқымы", "Күйі"),
        "ГИС қисықтары таңдалмаған", "Бұғатталған", "Жолдар жоқ",
        "Ақырлы мәндер жоқ", "Тексерілді",
    ),
    AppLanguage.EN: (
        "Source GIS samples (MD)",
        "Sample counts and endpoint bounds do not establish continuous coverage. "
        "Matching depths do not prove saturation or productivity.",
        ("Curve (key)", "Curve ID", "Dataset ID", "Unit", "Provenance",
         "Rows", "Finite values", "Missing", "MD bounds, m", "Value range", "Status"),
        "No GIS curves selected", "Blocked", "No rows", "No finite values", "Reviewed",
    ),
}


def _bounds(values: tuple[float, float] | None) -> str:
    return "—" if values is None else f"{values[0]}–{values[1]}"


def gis_interval_evidence_table(
    evidence: GasGeologyGisIntervalEvidence,
    language: AppLanguage = AppLanguage.RU,
) -> GisEvidenceTable:
    """Keep source identifiers and units intact, without inventing measurements."""
    title, notice, headings, empty, blocked, no_rows, no_values, reviewed = _LABELS[language]
    rows: list[tuple[str, ...]] = []
    seen: set[str] = set()
    for item in evidence.gis:
        if item.curve_key in seen:
            raise ValueError("Duplicate GIS evidence key")
        seen.add(item.curve_key)
        source = item.source
        if source is not None and source.curve_key != item.curve_key:
            raise ValueError("GIS evidence curve identity mismatch")
        identity = (
            item.curve_key,
            source.curve_id if source is not None else "—",
            source.source_dataset_id if source is not None else "—",
            (source.unit or "—") if source is not None else "—",
            source.provenance if source is not None else "—",
        )
        review = item.review
        if review is None:
            # Blocked inputs have no observed counts; zero would invent data.
            status = blocked + (": " + "; ".join(item.issues) if item.issues else "")
            rows.append(identity + ("—",) * 5 + (status,))
            continue
        if (
            source is None or review.source != source or item.issues
            or review.top_md_m != evidence.geology.gas_top
            or review.bottom_md_m != evidence.geology.gas_bottom
        ):
            raise ValueError("GIS evidence source or MD interval mismatch")
        if (
            min(review.sample_count, review.finite_count, review.missing_count) < 0
            or review.finite_count + review.missing_count != review.sample_count
        ):
            raise ValueError("Invalid GIS evidence sample counts")
        status = no_rows if review.sample_count == 0 else (
            no_values if review.finite_count == 0 else reviewed
        )
        rows.append(identity + (
            str(review.sample_count), str(review.finite_count), str(review.missing_count),
            _bounds(review.finite_md_bounds), _bounds(review.finite_value_bounds), status,
        ))
    return GisEvidenceTable(title, notice, headings, tuple(rows), empty)


def geology_gis_interval_evidence_html(
    evidence: GasGeologyGisIntervalEvidence,
    language: AppLanguage = AppLanguage.RU,
    *,
    fields: tuple[tuple[EvidenceKind, str], ...] = (),
) -> str:
    """Render separate geology and GIS sections for an already reviewed snapshot."""
    geology = geology_interval_evidence_html(evidence.geology, language, fields=fields)
    gis = gis_interval_evidence_table(evidence, language)
    headings = "".join(f"<th>{escape(cell)}</th>" for cell in gis.headings)
    rows = "".join(
        "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>"
        for row in gis.rows
    )
    if not rows:
        rows = f"<tr><td colspan='{len(gis.headings)}'>{escape(gis.empty)}</td></tr>"
    return (
        geology + "<section class='gas-gis-evidence' data-axis='MD' "
        f"data-dataset-id='{escape(evidence.geology.dataset_id, quote=True)}' "
        f"data-axis-id='{escape(evidence.geology.depth_axis_id, quote=True)}'>"
        f"<h2>{escape(gis.title)}</h2><p>{escape(gis.notice)}</p>"
        f"<table><thead><tr>{headings}</tr></thead><tbody>{rows}</tbody></table></section>"
    )


__all__ = ["GisEvidenceTable", "gis_interval_evidence_table", "geology_gis_interval_evidence_html"]
