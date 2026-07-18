from __future__ import annotations

from dataclasses import dataclass
from html import escape
import os
from pathlib import Path
import tempfile

from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument

from geoworkbench.domain.models import CuttingsSample
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage


class InterpretationReportError(RuntimeError):
    pass


LBA_FIELDS: tuple[tuple[str, str], ...] = (
    ("group", "lba_group"),
    ("type", "lba_type_id"),
    ("intensity", "lba_intensity"),
    ("color", "lba_color"),
    ("distribution", "lba_distribution"),
    ("cut", "lba_cut"),
    ("cut_speed", "lba_cut_speed"),
    ("cut_color", "lba_cut_color"),
    ("residue", "lba_residue_type"),
    ("residue_color", "lba_residue_color"),
    ("odour", "lba_odour"),
    ("stain", "lba_stain"),
    ("description", "lba_description"),
)


@dataclass(frozen=True, slots=True)
class AnalysisInterpretationEntry:
    sample_id: str
    top_depth: float
    bottom_depth: float
    calcite_percent: float | None
    dolomite_percent: float | None
    insoluble_residue_percent: float | None
    lba_observations: tuple[tuple[str, str], ...]
    interpretation: str | None

    @property
    def has_calcimetry(self) -> bool:
        return self.calcite_percent is not None or self.dolomite_percent is not None

    @property
    def has_lba(self) -> bool:
        return bool(self.lba_observations)


@dataclass(frozen=True, slots=True)
class InterpretationReport:
    project_name: str
    well_name: str
    dataset_name: str | None
    entries: tuple[AnalysisInterpretationEntry, ...]

    @property
    def calcimetry_count(self) -> int:
        return sum(entry.has_calcimetry for entry in self.entries)

    @property
    def lba_count(self) -> int:
        return sum(entry.has_lba for entry in self.entries)

    @property
    def interpreted_count(self) -> int:
        return sum(bool(entry.interpretation) for entry in self.entries)


def build_interpretation_report(session: ProjectSession) -> InterpretationReport:
    well = session.current_well
    if well is None:
        raise RuntimeError("Сначала выберите скважину")
    entries = tuple(
        entry
        for sample in sorted(well.cuttings, key=lambda item: (item.top_depth, item.bottom_depth))
        if (entry := _entry_from_sample(sample)) is not None
    )
    dataset = session.current_dataset
    return InterpretationReport(
        session.project.name,
        well.name,
        dataset.name if dataset is not None else None,
        entries,
    )


def _entry_from_sample(sample: CuttingsSample) -> AnalysisInterpretationEntry | None:
    observations = tuple(
        (key, str(value))
        for key, attribute in LBA_FIELDS
        if (value := getattr(sample, attribute)) is not None and str(value).strip()
    )
    has_calcimetry = sample.calcite_percent is not None or sample.dolomite_percent is not None
    interpretation = (
        sample.analysis_interpretation.strip() if sample.analysis_interpretation else None
    )
    if not has_calcimetry and not observations and not interpretation:
        return None
    return AnalysisInterpretationEntry(
        sample.sample_id,
        sample.top_depth,
        sample.bottom_depth,
        sample.calcite_percent,
        sample.dolomite_percent,
        sample.insoluble_residue_percent,
        observations,
        interpretation,
    )


_LABELS = {
    AppLanguage.RU: {
        "title": "Интерпретация кальциметрии и ЛБА",
        "project": "Проект",
        "well": "Скважина",
        "dataset": "Набор данных",
        "summary": "Сводка",
        "counts": "Кальциметрия: {calc}; ЛБА: {lba}; экспертные заключения: {interpreted}",
        "interval": "Интервал, м",
        "calcimetry": "Кальциметрия",
        "lba": "ЛБА",
        "interpretation": "Интерпретация геолога",
        "insoluble": "Нерастворимый остаток",
        "empty": "Результаты кальциметрии, ЛБА и интерпретации пока не заполнены.",
        "notice": (
            "Исходные наблюдения и экспертное заключение приведены раздельно. "
            "Отчёт не является автоматическим заключением о нефтенасыщении."
        ),
    },
    AppLanguage.KK: {
        "title": "Кальциметрия және ЛБА интерпретациясы",
        "project": "Жоба",
        "well": "Ұңғыма",
        "dataset": "Деректер жиыны",
        "summary": "Жиынтық",
        "counts": "Кальциметрия: {calc}; ЛБА: {lba}; сараптамалық қорытынды: {interpreted}",
        "interval": "Аралық, м",
        "calcimetry": "Кальциметрия",
        "lba": "ЛБА",
        "interpretation": "Геолог интерпретациясы",
        "insoluble": "Ерімейтін қалдық",
        "empty": "Кальциметрия, ЛБА және интерпретация нәтижелері әлі толтырылмаған.",
        "notice": (
            "Бастапқы бақылаулар мен сараптамалық қорытынды бөлек берілген. "
            "Есеп мұнайға қанығу туралы автоматты қорытынды болып табылмайды."
        ),
    },
    AppLanguage.EN: {
        "title": "Calcimetry and LBA interpretation",
        "project": "Project",
        "well": "Well",
        "dataset": "Dataset",
        "summary": "Summary",
        "counts": "Calcimetry: {calc}; LBA: {lba}; expert interpretations: {interpreted}",
        "interval": "Interval, m",
        "calcimetry": "Calcimetry",
        "lba": "LBA",
        "interpretation": "Geologist interpretation",
        "insoluble": "Insoluble residue",
        "empty": "No calcimetry, LBA, or interpretation results have been entered yet.",
        "notice": (
            "Source observations and the expert interpretation are shown separately. "
            "This report is not an automatic conclusion about hydrocarbon saturation."
        ),
    },
}

_LBA_LABELS = {
    AppLanguage.RU: {
        "group": "Группа",
        "type": "Тип",
        "intensity": "Интенсивность",
        "color": "Цвет флуоресценции",
        "distribution": "Распределение",
        "cut": "Cut",
        "cut_speed": "Скорость cut",
        "cut_color": "Цвет cut",
        "residue": "Остаток",
        "residue_color": "Цвет остатка",
        "odour": "Запах",
        "stain": "Масляное окрашивание",
        "description": "Описание",
    },
    AppLanguage.KK: {
        "group": "Топ",
        "type": "Түр",
        "intensity": "Қарқындылық",
        "color": "Флуоресценция түсі",
        "distribution": "Таралуы",
        "cut": "Cut",
        "cut_speed": "Cut жылдамдығы",
        "cut_color": "Cut түсі",
        "residue": "Қалдық",
        "residue_color": "Қалдық түсі",
        "odour": "Иіс",
        "stain": "Майлы боялу",
        "description": "Сипаттама",
    },
    AppLanguage.EN: {
        "group": "Group",
        "type": "Type",
        "intensity": "Intensity",
        "color": "Fluorescence color",
        "distribution": "Distribution",
        "cut": "Cut",
        "cut_speed": "Cut speed",
        "cut_color": "Cut color",
        "residue": "Residue",
        "residue_color": "Residue color",
        "odour": "Odour",
        "stain": "Stain",
        "description": "Description",
    },
}


def interpretation_report_html(
    report: InterpretationReport, language: AppLanguage = AppLanguage.RU
) -> str:
    labels = _LABELS[language]
    summary = labels["counts"].format(
        calc=report.calcimetry_count,
        lba=report.lba_count,
        interpreted=report.interpreted_count,
    )
    rows = "".join(
        _entry_html(entry, labels, _LBA_LABELS[language]) for entry in report.entries
    )
    if not rows:
        rows = f'<tr><td colspan="4">{escape(labels["empty"])}</td></tr>'
    dataset = report.dataset_name or "—"
    return f"""
<!doctype html>
<html><head><meta charset="utf-8"><style>
body {{ font-family: sans-serif; color: #172033; font-size: 10pt; }}
h1 {{ font-size: 17pt; margin-bottom: 10px; }}
.meta {{ margin-bottom: 10px; }}
.notice {{ margin-top: 12px; padding: 7px; background: #fff7d6; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #6b7280; padding: 5px; vertical-align: top; }}
th {{ background: #e8eef7; }}
</style></head><body>
<h1>{escape(labels["title"])}</h1>
<div class="meta"><b>{escape(labels["project"])}:</b> {escape(report.project_name)}<br>
<b>{escape(labels["well"])}:</b> {escape(report.well_name)}<br>
<b>{escape(labels["dataset"])}:</b> {escape(dataset)}</div>
<p><b>{escape(labels["summary"])}:</b> {escape(summary)}</p>
<table><thead><tr><th>{escape(labels["interval"])}</th>
<th>{escape(labels["calcimetry"])}</th><th>{escape(labels["lba"])}</th>
<th>{escape(labels["interpretation"])}</th></tr></thead><tbody>{rows}</tbody></table>
<div class="notice">{escape(labels["notice"])}</div>
</body></html>
""".strip()


def _entry_html(
    entry: AnalysisInterpretationEntry,
    labels: dict[str, str],
    lba_labels: dict[str, str],
) -> str:
    calcimetry = "—"
    if entry.has_calcimetry:
        values = (
            ("CaCO₃", entry.calcite_percent),
            ("CaMg(CO₃)₂", entry.dolomite_percent),
            (labels["insoluble"], entry.insoluble_residue_percent),
        )
        calcimetry = "<br>".join(
            f"{escape(name)}: {_format_percent(value)}" for name, value in values if value is not None
        )
    lba = "<br>".join(
        f"{escape(lba_labels[key])}: {escape(value)}" for key, value in entry.lba_observations
    ) or "—"
    interpretation = escape(entry.interpretation or "—").replace("\n", "<br>")
    return (
        f"<tr><td>{entry.top_depth:g}–{entry.bottom_depth:g}</td>"
        f"<td>{calcimetry}</td><td>{lba}</td><td>{interpretation}</td></tr>"
    )


def _format_percent(value: float) -> str:
    return f"{value:g}%"


def export_interpretation_report_pdf(
    report: InterpretationReport,
    target: str | Path,
    *,
    language: AppLanguage = AppLanguage.RU,
    overwrite: bool = False,
) -> Path:
    destination = Path(target)
    if destination.suffix.casefold() != ".pdf":
        raise InterpretationReportError("Отчёт должен иметь расширение .pdf")
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.stem}-", suffix=".pdf", dir=destination.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        writer = QPdfWriter(str(temporary))
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageMargins(QMarginsF(14.0, 14.0, 14.0, 14.0), QPageLayout.Unit.Millimeter)
        writer.setResolution(300)
        writer.setTitle(_LABELS[language]["title"])
        writer.setCreator("GEOLOG GASRATIO@Pixler")
        document = QTextDocument()
        document.setHtml(interpretation_report_html(report, language))
        document.print_(writer)
        del writer
        if not temporary.exists() or temporary.stat().st_size == 0:
            raise InterpretationReportError("Не удалось сформировать PDF-отчёт")
        os.replace(temporary, destination)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        if isinstance(exc, (FileExistsError, InterpretationReportError)):
            raise
        raise InterpretationReportError(f"Не удалось экспортировать отчёт: {destination}") from exc
    return destination
