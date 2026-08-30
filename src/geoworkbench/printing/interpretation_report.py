from __future__ import annotations

from dataclasses import dataclass
from html import escape
from math import ceil, floor, isfinite
import os
from pathlib import Path
import tempfile

from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument

from geoworkbench.domain.models import CuttingsSample, Dataset
from geoworkbench.project.lithotype_catalog_controller import LithotypeCatalogController
from geoworkbench.project.lithotype_catalog_models import CatalogLithotype
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.stratigraphy_catalog_controller import (
    StratigraphyCatalogController,
)
from geoworkbench.project.stratigraphy_controller import stratigraphy_rank_order
from geoworkbench.services.lba_standard import (
    LbaStandardAssessment,
    assess_lba_standard,
    describe_lba_assessment,
    lba_color_code,
)
from geoworkbench.services.interval_gas_statistics import (
    IntervalCurveStatistics,
    build_interval_component_sum_statistics,
    build_interval_statistics,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.report_passport import ReportPassport
from geoworkbench.services.report_output_transaction import (
    execute_report_output_transaction,
)
from geoworkbench.printing.unicode_support import preflight_texts, print_font


class InterpretationReportError(RuntimeError):
    pass


_MAX_METER_ROWS = 50_000


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
class GeologicalRockComponent:
    lithotype_id: str
    code: str
    name_ru: str
    name_kk: str
    name_en: str
    percentage: float

    def localized_name(self, language: AppLanguage) -> str:
        if language is AppLanguage.KK:
            return self.name_kk or self.name_ru
        if language is AppLanguage.EN:
            return self.name_en or self.name_ru
        return self.name_ru


@dataclass(frozen=True, slots=True)
class GeologicalStratigraphyEntry:
    interval_id: str
    top_depth: float
    bottom_depth: float
    rank: str | None
    code: str
    name_ru: str
    name_kk: str
    name_en: str
    description: str | None

    def localized_name(self, language: AppLanguage) -> str:
        if language is AppLanguage.KK:
            return self.name_kk or self.name_ru
        if language is AppLanguage.EN:
            return self.name_en or self.name_ru
        return self.name_ru


@dataclass(frozen=True, slots=True)
class MeterGeologyEntry:
    top_depth: float
    bottom_depth: float
    sampling_coverage: float
    sample_intervals: tuple[tuple[float, float], ...]
    rock_components: tuple[GeologicalRockComponent, ...]
    rock_descriptions: tuple[str, ...]
    stratigraphy: tuple[GeologicalStratigraphyEntry, ...]


@dataclass(frozen=True, slots=True)
class GeologicalGasStatistics:
    kind: str
    mnemonic: str
    unit: str
    minimum: float | None
    mean: float | None
    maximum: float | None
    valid_count: int


@dataclass(frozen=True, slots=True)
class AnalysisInterpretationEntry:
    sample_id: str
    top_depth: float
    bottom_depth: float
    calcite_percent: float | None
    dolomite_percent: float | None
    insoluble_residue_percent: float | None
    lba_observations: tuple[tuple[str, str], ...]
    lba_standard_assessment: LbaStandardAssessment | None
    interpretation: str | None
    rock_components: tuple[GeologicalRockComponent, ...]
    rock_description: str | None
    stratigraphy: tuple[GeologicalStratigraphyEntry, ...]
    gas_statistics: tuple[GeologicalGasStatistics, ...]

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
    depth_unit: str
    entries: tuple[AnalysisInterpretationEntry, ...]
    meter_geology: tuple[MeterGeologyEntry, ...]
    stratigraphy: tuple[GeologicalStratigraphyEntry, ...]

    @property
    def sample_count(self) -> int:
        return len(self.entries)

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
    lithotypes = {
        item.lithotype_id: item for item in LithotypeCatalogController(session).available()
    }
    stratigraphy = _build_stratigraphy_snapshot(session)
    dataset = session.current_dataset
    entries = tuple(
        _entry_from_sample(
            sample,
            lithotypes=lithotypes,
            stratigraphy=stratigraphy,
            dataset=dataset,
        )
        for sample in sorted(
            well.cuttings,
            key=lambda item: (item.top_depth, item.bottom_depth),
        )
    )
    depth_unit = (
        (dataset.active_index.unit or "m")
        if dataset is not None
        else "m"
    )
    return InterpretationReport(
        session.project.name,
        well.name,
        dataset.name if dataset is not None else None,
        depth_unit,
        entries,
        _build_meter_geology(entries, stratigraphy),
        stratigraphy,
    )


def _entry_from_sample(
    sample: CuttingsSample,
    *,
    lithotypes: dict[str, CatalogLithotype],
    stratigraphy: tuple[GeologicalStratigraphyEntry, ...],
    dataset: Dataset | None,
) -> AnalysisInterpretationEntry:
    observations = tuple(
        (key, str(value))
        for key, attribute in LBA_FIELDS
        if (value := getattr(sample, attribute)) is not None and str(value).strip()
    )
    interpretation = (
        sample.analysis_interpretation.strip() if sample.analysis_interpretation else None
    )
    lba_standard_assessment = assess_lba_standard(
        group=sample.lba_group,
        type_id=sample.lba_type_id,
        color=lba_color_code(sample.lba_color),
        intensity=sample.lba_intensity,
    )
    components = tuple(
        sorted(
            (
                _rock_component(component.lithotype_id, component.percentage, lithotypes)
                for component in sample.components
            ),
            key=lambda item: (-item.percentage, item.code.casefold(), item.lithotype_id),
        )
    )
    rock_description = _rich_text_to_plain(sample.description)
    sample_stratigraphy = _overlapping_stratigraphy(
        stratigraphy,
        sample.top_depth,
        sample.bottom_depth,
    )
    return AnalysisInterpretationEntry(
        sample.sample_id,
        sample.top_depth,
        sample.bottom_depth,
        sample.calcite_percent,
        sample.dolomite_percent,
        sample.insoluble_residue_percent,
        observations,
        lba_standard_assessment,
        interpretation,
        components,
        rock_description or None,
        sample_stratigraphy,
        _build_sample_gas_statistics(dataset, sample.top_depth, sample.bottom_depth),
    )


def _build_sample_gas_statistics(
    dataset: Dataset | None,
    top_depth: float,
    bottom_depth: float,
) -> tuple[GeologicalGasStatistics, ...]:
    if dataset is None:
        return ()
    interval = build_interval_statistics(dataset, top_depth, bottom_depth)
    rows: list[GeologicalGasStatistics] = []
    if interval.raw_total is not None:
        rows.append(_geological_gas_statistics("total", interval.raw_total))
    rows.extend(
        _geological_gas_statistics("component", item)
        for item in interval.components
    )
    component_sum = build_interval_component_sum_statistics(
        dataset,
        top_depth,
        bottom_depth,
    )
    if component_sum is not None:
        rows.append(_geological_gas_statistics("sum", component_sum))
    return tuple(rows)


def _geological_gas_statistics(
    kind: str,
    item: IntervalCurveStatistics,
) -> GeologicalGasStatistics:
    return GeologicalGasStatistics(
        kind,
        item.mnemonic,
        item.unit,
        item.minimum,
        item.mean,
        item.maximum,
        item.valid_count,
    )


def _rock_component(
    lithotype_id: str,
    percentage: float,
    lithotypes: dict[str, CatalogLithotype],
) -> GeologicalRockComponent:
    definition = lithotypes.get(lithotype_id)
    if definition is None:
        return GeologicalRockComponent(
            lithotype_id,
            lithotype_id.upper(),
            lithotype_id,
            lithotype_id,
            lithotype_id,
            float(percentage),
        )
    return GeologicalRockComponent(
        lithotype_id,
        definition.code,
        definition.name_ru,
        definition.name_kk or definition.name_ru,
        definition.name_en or definition.name_ru,
        float(percentage),
    )


def _build_stratigraphy_snapshot(
    session: ProjectSession,
) -> tuple[GeologicalStratigraphyEntry, ...]:
    well = session.current_well
    if well is None:
        return ()
    catalog = {
        (item.rank.strip().casefold(), item.code.strip().casefold()): item
        for item in StratigraphyCatalogController(session).available()
    }
    result: list[GeologicalStratigraphyEntry] = []
    for interval in sorted(
        well.stratigraphy,
        key=lambda item: (
            item.top_depth,
            item.bottom_depth,
            stratigraphy_rank_order(item.rank),
            item.code.casefold(),
            item.interval_id,
        ),
    ):
        definition = catalog.get(
            ((interval.rank or "").strip().casefold(), interval.code.strip().casefold())
        )
        if interval.name:
            names = (interval.name, interval.name, interval.name)
        elif definition is not None:
            names = (
                definition.name_ru,
                definition.name_kk or definition.name_ru,
                definition.name_en or definition.name_ru,
            )
        else:
            names = (interval.code, interval.code, interval.code)
        result.append(
            GeologicalStratigraphyEntry(
                interval.interval_id,
                float(interval.top_depth),
                float(interval.bottom_depth),
                interval.rank,
                interval.code,
                names[0],
                names[1],
                names[2],
                interval.description
                or (definition.description if definition is not None else None)
                or None,
            )
        )
    return tuple(result)


def _overlapping_stratigraphy(
    stratigraphy: tuple[GeologicalStratigraphyEntry, ...],
    top_depth: float,
    bottom_depth: float,
) -> tuple[GeologicalStratigraphyEntry, ...]:
    return tuple(
        item
        for item in stratigraphy
        if item.top_depth < bottom_depth and item.bottom_depth > top_depth
    )


def _build_meter_geology(
    entries: tuple[AnalysisInterpretationEntry, ...],
    stratigraphy: tuple[GeologicalStratigraphyEntry, ...],
) -> tuple[MeterGeologyEntry, ...]:
    meter_indexes: set[int] = set()
    for entry in entries:
        if not isfinite(entry.top_depth) or not isfinite(entry.bottom_depth):
            continue
        meter_indexes.update(range(floor(entry.top_depth), ceil(entry.bottom_depth)))
        if len(meter_indexes) > _MAX_METER_ROWS:
            raise InterpretationReportError(
                "Метровая геологическая таблица превышает безопасный предел "
                f"{_MAX_METER_ROWS} строк"
            )

    result: list[MeterGeologyEntry] = []
    for meter_index in sorted(meter_indexes):
        top = float(meter_index)
        bottom = top + 1.0
        overlapping = tuple(
            entry
            for entry in entries
            if entry.top_depth < bottom and entry.bottom_depth > top
        )
        if not overlapping:
            continue
        overlaps = tuple(
            (
                max(top, entry.top_depth),
                min(bottom, entry.bottom_depth),
            )
            for entry in overlapping
        )
        component_weight = sum(
            max(0.0, min(bottom, entry.bottom_depth) - max(top, entry.top_depth))
            for entry in overlapping
            if entry.rock_components
        )
        weighted: dict[str, tuple[GeologicalRockComponent, float]] = {}
        if component_weight > 0.0:
            for entry in overlapping:
                overlap = max(
                    0.0,
                    min(bottom, entry.bottom_depth) - max(top, entry.top_depth),
                )
                for component in entry.rock_components:
                    current = weighted.get(component.lithotype_id)
                    contribution = component.percentage * overlap
                    weighted[component.lithotype_id] = (
                        component,
                        contribution + (current[1] if current is not None else 0.0),
                    )
        components = tuple(
            sorted(
                (
                    GeologicalRockComponent(
                        component.lithotype_id,
                        component.code,
                        component.name_ru,
                        component.name_kk,
                        component.name_en,
                        contribution / component_weight,
                    )
                    for component, contribution in weighted.values()
                ),
                key=lambda item: (-item.percentage, item.code.casefold()),
            )
        )
        descriptions = tuple(
            dict.fromkeys(
                entry.rock_description
                for entry in overlapping
                if entry.rock_description
            )
        )
        sample_intervals = tuple(
            dict.fromkeys((entry.top_depth, entry.bottom_depth) for entry in overlapping)
        )
        result.append(
            MeterGeologyEntry(
                top,
                bottom,
                min(1.0, _interval_union_length(overlaps)),
                sample_intervals,
                components,
                descriptions,
                _overlapping_stratigraphy(stratigraphy, top, bottom),
            )
        )
    return tuple(result)


def _interval_union_length(intervals: tuple[tuple[float, float], ...]) -> float:
    ordered = sorted(
        (top, bottom)
        for top, bottom in intervals
        if isfinite(top) and isfinite(bottom) and bottom > top
    )
    if not ordered:
        return 0.0
    total = 0.0
    current_top, current_bottom = ordered[0]
    for top, bottom in ordered[1:]:
        if top <= current_bottom:
            current_bottom = max(current_bottom, bottom)
            continue
        total += current_bottom - current_top
        current_top, current_bottom = top, bottom
    return total + current_bottom - current_top


def _rich_text_to_plain(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if "<" not in text or ">" not in text:
        return text
    document = QTextDocument()
    document.setHtml(text)
    return document.toPlainText().strip()


_LABELS = {
    AppLanguage.RU: {
        "title": "Геологический отчёт по шламу, стратиграфии, газу, кальциметрии и ЛБА",
        "project": "Проект",
        "well": "Скважина",
        "dataset": "Набор данных",
        "summary": "Сводка",
        "counts": (
            "фактических отборов: {samples}; метровых строк: {meters}; "
            "стратиграфических интервалов: {strat}; кальциметрия: {calc}; "
            "ЛБА: {lba}; заключения геолога: {interpreted}"
        ),
        "meter_section": "Описание пород по метровым интервалам",
        "meter_note": (
            "Производная сводка по фиксированному шагу 1 м. Процент покрытия показывает, "
            "какая часть метра обеспечена фактическим отбором; состав усредняется по длине "
            "только между реально перекрывающими метр пробами."
        ),
        "sample_section": "Фактические интервалы отбора шлама",
        "gas_lba_section": "Газ и ЛБА по фактическим интервалам отбора",
        "gas_note": (
            "Total Gas показан только при наличии отдельной кривой. Сумма компонентов "
            "рассчитана отдельно по доступным компонентам и не подменяет Total Gas."
        ),
        "stratigraphy_section": "Стратиграфия по всей глубине скважины",
        "interval": "Интервал",
        "sample_intervals": "Фактический отбор",
        "coverage": "Покрытие отбором",
        "composition": "Породы и содержание",
        "rock_description": "Описание пород",
        "stratigraphy": "Стратиграфия",
        "rank": "Ранг",
        "code": "Код",
        "name": "Название",
        "description": "Описание",
        "calcimetry": "Кальциметрия",
        "gas": "Газ: минимум / среднее / максимум",
        "gas_total": "Total Gas (отдельная кривая)",
        "gas_component_sum": "Сумма компонентов",
        "minimum": "мин",
        "mean": "среднее",
        "maximum": "макс",
        "samples": "отсчётов",
        "no_gas": "Газовые кривые не найдены",
        "no_values": "нет отсчётов в интервале",
        "lba": "Подробные данные ЛБА",
        "interpretation": "Интерпретация геолога",
        "insoluble": "Нерастворимый остаток",
        "lba_standard": "Оценка по стандарту ЛБА",
        "empty": "Геологические данные пока не заполнены.",
        "no_samples": "Фактические интервалы отбора шлама не заполнены.",
        "no_stratigraphy": "Стратиграфические интервалы не заполнены.",
        "no_lba": "ЛБА не заполнен",
        "notice": (
            "Фактические отборы, исходные наблюдения ЛБА, расчётная метровая сводка и "
            "экспертное заключение приведены раздельно. Отчёт не является автоматическим "
            "заключением о нефтенасыщении."
        ),
    },
    AppLanguage.KK: {
        "title": "Шлам, стратиграфия, газ, кальциметрия және ЛБА бойынша геологиялық есеп",
        "project": "Жоба",
        "well": "Ұңғыма",
        "dataset": "Деректер жиыны",
        "summary": "Жиынтық",
        "counts": (
            "нақты сынама: {samples}; метрлік жол: {meters}; стратиграфиялық аралық: "
            "{strat}; кальциметрия: {calc}; ЛБА: {lba}; геолог қорытындысы: {interpreted}"
        ),
        "meter_section": "Метрлік аралықтар бойынша жыныс сипаттамасы",
        "meter_note": (
            "1 м тұрақты қадаммен жасалған туынды жиынтық. Қамту пайызы метрдің нақты "
            "сынамаға негізделген бөлігін көрсетеді; құрам тек метрді нақты қиып өтетін "
            "сынамалар арасында ұзындық бойынша орташаланады."
        ),
        "sample_section": "Шлам алудың нақты аралықтары",
        "gas_lba_section": "Нақты сынама аралықтары бойынша газ және ЛБА",
        "gas_note": (
            "Total Gas тек бөлек қисық болғанда көрсетіледі. Компоненттер қосындысы "
            "қолжетімді компоненттерден бөлек есептеледі және Total Gas-ты алмастырмайды."
        ),
        "stratigraphy_section": "Ұңғыманың толық тереңдігі бойынша стратиграфия",
        "interval": "Аралық",
        "sample_intervals": "Нақты сынама",
        "coverage": "Сынамамен қамту",
        "composition": "Жыныстар және мөлшері",
        "rock_description": "Жыныс сипаттамасы",
        "stratigraphy": "Стратиграфия",
        "rank": "Дәреже",
        "code": "Код",
        "name": "Атауы",
        "description": "Сипаттама",
        "calcimetry": "Кальциметрия",
        "gas": "Газ: ең аз / орташа / ең көп",
        "gas_total": "Total Gas (бөлек қисық)",
        "gas_component_sum": "Компоненттер қосындысы",
        "minimum": "ең аз",
        "mean": "орташа",
        "maximum": "ең көп",
        "samples": "есеп",
        "no_gas": "Газ қисықтары табылмады",
        "no_values": "аралықта есеп жоқ",
        "lba": "ЛБА толық деректері",
        "interpretation": "Геолог интерпретациясы",
        "insoluble": "Ерімейтін қалдық",
        "lba_standard": "ЛБА стандарты бойынша бағалау",
        "empty": "Геологиялық деректер әлі толтырылмаған.",
        "no_samples": "Шлам алудың нақты аралықтары толтырылмаған.",
        "no_stratigraphy": "Стратиграфиялық аралықтар толтырылмаған.",
        "no_lba": "ЛБА толтырылмаған",
        "notice": (
            "Нақты сынамалар, ЛБА бастапқы бақылаулары, есептелген метрлік жиынтық және "
            "сараптамалық қорытынды бөлек берілген. Есеп мұнайға қанығу туралы автоматты "
            "қорытынды болып табылмайды."
        ),
    },
    AppLanguage.EN: {
        "title": "Geological report: cuttings, stratigraphy, gas, calcimetry and LBA",
        "project": "Project",
        "well": "Well",
        "dataset": "Dataset",
        "summary": "Summary",
        "counts": (
            "actual samples: {samples}; one-metre rows: {meters}; stratigraphic intervals: "
            "{strat}; calcimetry: {calc}; LBA: {lba}; geologist interpretations: {interpreted}"
        ),
        "meter_section": "Rock description by one-metre interval",
        "meter_note": (
            "Derived summary at a fixed one-metre step. Sampling coverage shows how much of "
            "each metre is supported by actual samples; composition is length-weighted only "
            "between samples that really overlap that metre."
        ),
        "sample_section": "Actual cuttings sampling intervals",
        "gas_lba_section": "Gas and LBA by actual sampling interval",
        "gas_note": (
            "Total Gas is shown only when a dedicated curve is present. The component sum is "
            "calculated separately from available components and does not replace Total Gas."
        ),
        "stratigraphy_section": "Whole-well stratigraphy",
        "interval": "Interval",
        "sample_intervals": "Actual sampling",
        "coverage": "Sampling coverage",
        "composition": "Rocks and percentage",
        "rock_description": "Rock description",
        "stratigraphy": "Stratigraphy",
        "rank": "Rank",
        "code": "Code",
        "name": "Name",
        "description": "Description",
        "calcimetry": "Calcimetry",
        "gas": "Gas: minimum / mean / maximum",
        "gas_total": "Total Gas (dedicated curve)",
        "gas_component_sum": "Component sum",
        "minimum": "min",
        "mean": "mean",
        "maximum": "max",
        "samples": "samples",
        "no_gas": "No gas curves found",
        "no_values": "no samples in interval",
        "lba": "Detailed LBA data",
        "interpretation": "Geologist interpretation",
        "insoluble": "Insoluble residue",
        "lba_standard": "Standard LBA assessment",
        "empty": "No geological data have been entered yet.",
        "no_samples": "No actual cuttings sampling intervals have been entered.",
        "no_stratigraphy": "No stratigraphic intervals have been entered.",
        "no_lba": "No LBA data",
        "notice": (
            "Actual samples, source LBA observations, the derived one-metre summary, and the "
            "expert interpretation are shown separately. This report is not an automatic "
            "conclusion about hydrocarbon saturation."
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
        samples=report.sample_count,
        meters=len(report.meter_geology),
        strat=len(report.stratigraphy),
        calc=report.calcimetry_count,
        lba=report.lba_count,
        interpreted=report.interpreted_count,
    )
    meter_rows = "".join(
        _meter_entry_html(entry, language, report.depth_unit)
        for entry in report.meter_geology
    )
    if not meter_rows:
        meter_rows = f'<tr><td colspan="6">{escape(labels["no_samples"])}</td></tr>'
    sample_rows = "".join(
        _entry_html(
            entry,
            labels,
            language,
            report.depth_unit,
        )
        for entry in report.entries
    )
    if not sample_rows:
        sample_rows = f'<tr><td colspan="6">{escape(labels["no_samples"])}</td></tr>'
    analysis_rows = "".join(
        _sample_analysis_entry_html(
            entry,
            labels,
            _LBA_LABELS[language],
            language,
            report.depth_unit,
        )
        for entry in report.entries
    )
    if not analysis_rows:
        analysis_rows = f'<tr><td colspan="3">{escape(labels["no_samples"])}</td></tr>'
    stratigraphy_rows = "".join(
        _stratigraphy_entry_html(entry, language, report.depth_unit)
        for entry in report.stratigraphy
    )
    if not stratigraphy_rows:
        stratigraphy_rows = (
            f'<tr><td colspan="5">{escape(labels["no_stratigraphy"])}</td></tr>'
        )
    dataset = report.dataset_name or "—"
    interval_heading = f'{escape(labels["interval"])}, {escape(report.depth_unit)}'
    return f"""
<!doctype html>
<html><head><meta charset="utf-8"><style>
html, body {{ background: #ffffff; color: #172033; }}
body {{ font-size: 9pt; }}
h1 {{ font-size: 17pt; margin-bottom: 10px; }}
h2 {{ font-size: 13pt; margin: 16px 0 6px 0; page-break-after: avoid; }}
.meta {{ margin-bottom: 10px; }}
.section-note {{ margin: 0 0 7px 0; color: #475569; }}
.notice-table {{ margin-top: 12px; width: 100%; }}
.notice-table td {{ padding: 7px; background: #fff7d6; border: none; border-left: 4px solid #d59b00; }}
.new-page {{ page-break-before: always; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 10px; }}
thead {{ display: table-header-group; }}
th, td {{ border: 1px solid #6b7280; padding: 4px; vertical-align: top; }}
th {{ background: #e8eef7; color: #172033; }}
td {{ background: #ffffff; color: #172033; }}
.meter-table {{ font-size: 8pt; }}
.sample-table {{ font-size: 7.3pt; }}
.analysis-table {{ font-size: 7.5pt; }}
.stratigraphy-table {{ font-size: 8pt; }}
.detail-line {{ margin-bottom: 2px; }}
.gas-line {{ margin-bottom: 5px; }}
</style></head><body>
<h1>{escape(labels["title"])}</h1>
<div class="meta"><b>{escape(labels["project"])}:</b> {escape(report.project_name)}<br>
<b>{escape(labels["well"])}:</b> {escape(report.well_name)}<br>
<b>{escape(labels["dataset"])}:</b> {escape(dataset)}</div>
<p><b>{escape(labels["summary"])}:</b> {escape(summary)}</p>
<h2>{escape(labels["meter_section"])}</h2>
<p class="section-note">{escape(labels["meter_note"])}</p>
<table class="meter-table"><thead><tr><th>{interval_heading}</th>
<th>{escape(labels["sample_intervals"])}</th><th>{escape(labels["coverage"])}</th>
<th>{escape(labels["composition"])}</th><th>{escape(labels["rock_description"])}</th>
<th>{escape(labels["stratigraphy"])}</th></tr></thead><tbody>{meter_rows}</tbody></table>
<h2 class="new-page">{escape(labels["sample_section"])}</h2>
<table class="sample-table"><thead><tr><th>{interval_heading}</th>
<th>{escape(labels["composition"])}</th><th>{escape(labels["rock_description"])}</th>
<th>{escape(labels["stratigraphy"])}</th><th>{escape(labels["calcimetry"])}</th>
<th>{escape(labels["interpretation"])}</th>
</tr></thead><tbody>{sample_rows}</tbody></table>
<h2 class="new-page">{escape(labels["gas_lba_section"])}</h2>
<p class="section-note">{escape(labels["gas_note"])}</p>
<table class="analysis-table"><thead><tr><th>{interval_heading}</th>
<th>{escape(labels["gas"])}</th><th>{escape(labels["lba"])}</th>
</tr></thead><tbody>{analysis_rows}</tbody></table>
<h2 class="new-page">{escape(labels["stratigraphy_section"])}</h2>
<table class="stratigraphy-table"><thead><tr><th>{interval_heading}</th>
<th>{escape(labels["rank"])}</th><th>{escape(labels["code"])}</th>
<th>{escape(labels["name"])}</th><th>{escape(labels["description"])}</th>
</tr></thead><tbody>{stratigraphy_rows}</tbody></table>
<table class="notice-table"><tr><td>{escape(labels["notice"])}</td></tr></table>
</body></html>
""".strip()


def _meter_entry_html(
    entry: MeterGeologyEntry,
    language: AppLanguage,
    depth_unit: str,
) -> str:
    samples = "<br>".join(
        _format_depth_interval(top, bottom, depth_unit)
        for top, bottom in entry.sample_intervals
    ) or "—"
    descriptions = "<br><br>".join(
        _text_html(item) for item in entry.rock_descriptions
    ) or "—"
    return (
        f"<tr><td>{_format_depth_interval(entry.top_depth, entry.bottom_depth, depth_unit)}</td>"
        f"<td>{samples}</td>"
        f"<td>{entry.sampling_coverage * 100.0:.1f}%</td>"
        f"<td>{_components_html(entry.rock_components, language)}</td>"
        f"<td>{descriptions}</td>"
        f"<td>{_stratigraphy_html(entry.stratigraphy, language, depth_unit)}</td></tr>"
    )


def _entry_html(
    entry: AnalysisInterpretationEntry,
    labels: dict[str, str],
    language: AppLanguage,
    depth_unit: str,
) -> str:
    calcimetry = _calcimetry_html(entry, labels)
    interpretation = _text_html(entry.interpretation) if entry.interpretation else "—"
    return (
        f"<tr><td>{_format_depth_interval(entry.top_depth, entry.bottom_depth, depth_unit)}</td>"
        f"<td>{_components_html(entry.rock_components, language)}</td>"
        f"<td>{_text_html(entry.rock_description) if entry.rock_description else '—'}</td>"
        f"<td>{_stratigraphy_html(entry.stratigraphy, language, depth_unit)}</td>"
        f"<td>{calcimetry}</td><td>{interpretation}</td></tr>"
    )


def _sample_analysis_entry_html(
    entry: AnalysisInterpretationEntry,
    labels: dict[str, str],
    lba_labels: dict[str, str],
    language: AppLanguage,
    depth_unit: str,
) -> str:
    return (
        f"<tr><td>{_format_depth_interval(entry.top_depth, entry.bottom_depth, depth_unit)}</td>"
        f"<td>{_gas_html(entry, labels)}</td>"
        f"<td>{_lba_html(entry, labels, lba_labels, language)}</td></tr>"
    )


def _stratigraphy_entry_html(
    entry: GeologicalStratigraphyEntry,
    language: AppLanguage,
    depth_unit: str,
) -> str:
    return (
        f"<tr><td>{_format_depth_interval(entry.top_depth, entry.bottom_depth, depth_unit)}</td>"
        f"<td>{escape(entry.rank or '—')}</td><td>{escape(entry.code)}</td>"
        f"<td>{escape(entry.localized_name(language))}</td>"
        f"<td>{_text_html(entry.description) if entry.description else '—'}</td></tr>"
    )


def _components_html(
    components: tuple[GeologicalRockComponent, ...],
    language: AppLanguage,
) -> str:
    if not components:
        return "—"
    return "<br>".join(
        f"{escape(component.localized_name(language))} "
        f"({escape(component.code)}): {_format_percent(component.percentage)}"
        for component in components
    )


def _stratigraphy_html(
    entries: tuple[GeologicalStratigraphyEntry, ...],
    language: AppLanguage,
    depth_unit: str,
) -> str:
    if not entries:
        return "—"
    return "<br>".join(
        f"{escape(entry.rank or '—')}; {escape(entry.code)} - "
        f"{escape(entry.localized_name(language))} "
        f"({_format_depth_interval(entry.top_depth, entry.bottom_depth, depth_unit)})"
        + (f": {_text_html(entry.description)}" if entry.description else "")
        for entry in entries
    )


def _calcimetry_html(
    entry: AnalysisInterpretationEntry,
    labels: dict[str, str],
) -> str:
    if not entry.has_calcimetry:
        return "—"
    values = (
        ("CaCO₃", entry.calcite_percent),
        ("CaMg(CO₃)₂", entry.dolomite_percent),
        (labels["insoluble"], entry.insoluble_residue_percent),
    )
    return "<br>".join(
        f"{escape(name)}: {_format_percent(value)}"
        for name, value in values
        if value is not None
    )


def _lba_html(
    entry: AnalysisInterpretationEntry,
    labels: dict[str, str],
    lba_labels: dict[str, str],
    language: AppLanguage,
) -> str:
    if not entry.has_lba:
        return escape(labels["no_lba"])
    observations = dict(entry.lba_observations)
    parts = [
        f'<div class="detail-line"><b>{escape(lba_labels[key])}:</b> '
        f"{escape(observations.get(key, '—'))}</div>"
        for key, _attribute in LBA_FIELDS
    ]
    if entry.lba_standard_assessment is not None:
        parts.append(
            f'<div class="detail-line"><b>{escape(labels["lba_standard"])}:</b> '
            f"{escape(describe_lba_assessment(entry.lba_standard_assessment, language))}</div>"
        )
    return "".join(parts)


def _gas_html(
    entry: AnalysisInterpretationEntry,
    labels: dict[str, str],
) -> str:
    if not entry.gas_statistics:
        return escape(labels["no_gas"])
    rows: list[str] = []
    for item in entry.gas_statistics:
        if item.kind == "total":
            name = f'{labels["gas_total"]}: {item.mnemonic}'
        elif item.kind == "sum":
            name = labels["gas_component_sum"]
        else:
            name = item.mnemonic
        unit = f" [{item.unit}]" if item.unit else ""
        if item.valid_count:
            statistics = (
                f'{labels["minimum"]} {_format_gas_value(item.minimum)}; '
                f'{labels["mean"]} {_format_gas_value(item.mean)}; '
                f'{labels["maximum"]} {_format_gas_value(item.maximum)}; '
                f'{labels["samples"]}: {item.valid_count}'
            )
        else:
            statistics = labels["no_values"]
        rows.append(
            f'<div class="gas-line"><b>{escape(name + unit)}:</b> '
            f"{escape(statistics)}</div>"
        )
    return "".join(rows)


def _format_gas_value(value: float | None) -> str:
    if value is None or not isfinite(value):
        return "—"
    return f"{value:.6g}"


def _format_depth_interval(top: float, bottom: float, unit: str) -> str:
    suffix = f" {escape(unit)}" if unit else ""
    return f"{top:g}-{bottom:g}{suffix}"


def _text_html(value: str | None) -> str:
    return escape(value or "").replace("\r\n", "\n").replace("\r", "\n").replace(
        "\n", "<br>"
    )


def _format_percent(value: float) -> str:
    return f"{value:g}%"


def export_interpretation_report_pdf(
    report: InterpretationReport,
    target: str | Path,
    *,
    language: AppLanguage = AppLanguage.RU,
    overwrite: bool = False,
    passport: ReportPassport | None = None,
) -> Path:
    destination = Path(target)
    if destination.suffix.casefold() != ".pdf":
        raise InterpretationReportError("Отчёт должен иметь расширение .pdf")
    if passport is not None:
        try:
            transaction = execute_report_output_transaction(
                destination,
                lambda staged: export_interpretation_report_pdf(
                    report,
                    staged,
                    language=language,
                    overwrite=False,
                    passport=None,
                ),
                passport,
                overwrite=overwrite,
            )
        except (FileExistsError, InterpretationReportError):
            raise
        except Exception as exc:
            raise InterpretationReportError(
                f"Не удалось зафиксировать PDF-отчёт и Report Passport: {destination}"
            ) from exc
        return transaction.primary_path
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
        writer.setPageOrientation(QPageLayout.Orientation.Landscape)
        writer.setPageMargins(QMarginsF(14.0, 14.0, 14.0, 14.0), QPageLayout.Unit.Millimeter)
        writer.setResolution(300)
        writer.setTitle(_LABELS[language]["title"])
        writer.setCreator("GEOLOG GASRATIO@Pixler")
        html = interpretation_report_html(report, language)
        unicode_report = preflight_texts([html])
        if not unicode_report.ok:
            raise InterpretationReportError(unicode_report.error_message())
        document = QTextDocument()
        document.setDefaultFont(print_font(10.0, text=html))
        document.setHtml(html)
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
