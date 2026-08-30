from __future__ import annotations

from dataclasses import dataclass
from html import escape
import re

import numpy as np

from geoworkbench.catalogs.sensors import normalize_unit
from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.services.hydrocarbon_interpretation_modes import (
    HydrocarbonCandidateInterval,
    HydrocarbonInterpretationReport,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.las_parameter_resolver import concentration_scale_to_percent


_RAW_TOTAL_NAMES = (
    "TG_CALC",
    "TOTAL_GAS_CALC",
    "TG",
    "TGAS",
    "TOTALGAS",
    "TOTAL_GAS",
    "SUM_GAS",
    "СУММА_ГАЗОВ",
)
_EPS = np.finfo(np.float64).eps


@dataclass(frozen=True, slots=True)
class IntervalCurveStatistics:
    mnemonic: str
    unit: str
    minimum: float | None
    mean: float | None
    median: float | None
    maximum: float | None
    background: float | None
    valid_count: int
    positive_count: int

    @property
    def has_values(self) -> bool:
        return self.valid_count > 0

    @property
    def is_zero_only(self) -> bool:
        return self.has_values and self.positive_count == 0


@dataclass(frozen=True, slots=True)
class CandidateIntervalGasStatistics:
    primary: IntervalCurveStatistics | None
    raw_total: IntervalCurveStatistics | None
    components: tuple[IntervalCurveStatistics, ...]
    dexp: IntervalCurveStatistics | None


def build_candidate_interval_statistics(
    dataset: Dataset,
    candidate: HydrocarbonCandidateInterval,
) -> CandidateIntervalGasStatistics:
    return build_interval_statistics(
        dataset,
        candidate.top_depth,
        candidate.bottom_depth,
        primary_mnemonic=candidate.primary_mnemonic,
    )


def build_interval_statistics(
    dataset: Dataset,
    top_depth: float,
    bottom_depth: float,
    *,
    primary_mnemonic: str | None = None,
) -> CandidateIntervalGasStatistics:
    depth = np.asarray(dataset.depth, dtype=np.float64)
    mask = (
        np.isfinite(depth)
        & (depth >= min(top_depth, bottom_depth))
        & (depth <= max(top_depth, bottom_depth))
    )
    primary_curve = _find_curve(dataset, (primary_mnemonic,)) if primary_mnemonic else None
    primary = _curve_stats(primary_curve, depth, mask, gas=True)
    raw_curve = _find_curve(dataset, _RAW_TOTAL_NAMES)
    if primary_curve is not None and raw_curve is not None:
        if primary_curve.metadata.curve_id == raw_curve.metadata.curve_id:
            raw_curve = None
    raw_total = _curve_stats(raw_curve, depth, mask, gas=True)

    components: list[IntervalCurveStatistics] = []
    for curve in _component_curves(dataset):
        item = _curve_stats(curve, depth, mask, gas=False)
        if item is not None:
            components.append(item)

    dexp = _curve_stats(_find_curve(dataset, ("DEXPC", "DEXP")), depth, mask, gas=False)
    return CandidateIntervalGasStatistics(primary, raw_total, tuple(components), dexp)


def build_interval_component_sum_statistics(
    dataset: Dataset,
    top_depth: float,
    bottom_depth: float,
) -> IntervalCurveStatistics | None:
    """Return a row-wise sum of every resolved hydrocarbon gas component.

    A common source unit is preserved when all component units match. Mixed known
    concentration units are converted to percent by volume before summation. An
    incompatible mixed-unit set returns ``None`` instead of adding incomparable values.
    Only rows where every selected component is finite contribute to the statistics.
    """

    curves = _component_curves(dataset)
    if not curves:
        return None
    depth = np.asarray(dataset.depth, dtype=np.float64)
    mask = (
        np.isfinite(depth)
        & (depth >= min(top_depth, bottom_depth))
        & (depth <= max(top_depth, bottom_depth))
    )
    source_units = tuple((curve.metadata.unit or "").strip() for curve in curves)
    normalized_units = {normalize_unit(unit).casefold() for unit in source_units}
    arrays = [np.asarray(curve.values, dtype=np.float64) for curve in curves]
    if any(values.shape != depth.shape for values in arrays):
        return IntervalCurveStatistics(
            "SUM_COMPONENTS",
            source_units[0] if len(normalized_units) == 1 else "",
            None,
            None,
            None,
            None,
            None,
            0,
            0,
        )
    if len(normalized_units) == 1:
        unit = source_units[0]
        converted = arrays
    else:
        raw_scales = tuple(concentration_scale_to_percent(unit) for unit in source_units)
        known_scales = {scale for scale in raw_scales if scale is not None}
        if any(scale is None for scale in raw_scales):
            unknown_units = tuple(
                unit
                for unit, scale in zip(source_units, raw_scales, strict=True)
                if scale is None
            )
            if len(known_scales) != 1 or any(unit for unit in unknown_units):
                return None
        inferred_scale = next(iter(known_scales), None)
        scales = tuple(
            scale if scale is not None else inferred_scale for scale in raw_scales
        )
        unit = "%vol"
        converted = []
        for values, scale in zip(arrays, scales, strict=True):
            if scale is None:
                return None
            converted.append(values * scale)
    matrix = np.vstack(converted)
    valid = np.all(np.isfinite(matrix), axis=0)
    summed = np.full(depth.shape, np.nan, dtype=np.float64)
    summed[valid] = np.sum(matrix[:, valid], axis=0)
    return _stats_from_values(
        "SUM_COMPONENTS",
        unit,
        summed,
        depth,
        mask,
        gas=False,
    )


def _component_curves(dataset: Dataset) -> tuple[CurveData, ...]:
    components: list[CurveData] = []
    for name in ("C1", "C2", "C3", "IC4", "NC4", "IC5", "NC5"):
        curve = _find_curve(dataset, (name,))
        if curve is not None:
            components.append(curve)
    for total, iso, normal in (("C4", "IC4", "NC4"), ("C5", "IC5", "NC5")):
        if any(_component_name(item.metadata.original_mnemonic) in {iso, normal} for item in components):
            continue
        curve = _find_curve(dataset, (total,))
        if curve is not None:
            components.append(curve)
    return tuple(components)


def enhanced_fluid_hypothesis_basis(
    base_text: str,
    candidate: HydrocarbonCandidateInterval,
    statistics: CandidateIntervalGasStatistics,
    language: AppLanguage = AppLanguage.RU,
) -> str:
    labels = _labels(language)
    cleaned = base_text.strip()
    if candidate.interval_wetness is not None and abs(candidate.interval_wetness) <= _EPS:
        cleaned = f"{labels['interval_zero']} {cleaned}".strip()
    summary = interval_gas_summary(statistics, language)
    return " ".join(part for part in (summary, cleaned) if part)


def interval_gas_summary(
    statistics: CandidateIntervalGasStatistics,
    language: AppLanguage = AppLanguage.RU,
) -> str:
    labels = _labels(language)
    parts: list[str] = []
    if statistics.raw_total is not None:
        parts.append(_curve_summary(statistics.raw_total, labels["raw"], labels))
    if statistics.primary is not None:
        parts.append(_curve_summary(statistics.primary, labels["normalized"], labels))
    if statistics.components:
        parts.append(
            f"{labels['absolute']}: "
            + absolute_gas_components_summary(statistics.components, language)
        )
    if statistics.dexp is not None and statistics.dexp.has_values:
        parts.append(_stat_triplet(statistics.dexp, labels))
    return ". ".join(parts) + ("." if parts else "")


def absolute_gas_components_summary(
    items: tuple[IntervalCurveStatistics, ...],
    language: AppLanguage = AppLanguage.RU,
) -> str:
    labels = _labels(language)
    if not items:
        return labels["no_data"]
    ordered = sorted(items, key=lambda item: _component_sort_key(_component_name(item.mnemonic)))
    return "; ".join(_stat_triplet(item, labels) for item in ordered)


def interval_gas_table_html(
    report: HydrocarbonInterpretationReport,
    statistics: tuple[CandidateIntervalGasStatistics, ...],
    language: AppLanguage = AppLanguage.RU,
) -> str:
    if not report.candidates:
        return ""
    labels = _labels(language)
    rows = "".join(
        "<tr>"
        f"<td>{candidate.top_depth:.2f}-{candidate.bottom_depth:.2f} {escape(report.depth_unit)}</td>"
        f"<td>{_curve_html(item.raw_total, labels)}</td>"
        f"<td>{_curve_html(item.primary, labels)}</td>"
        f"<td>{escape(absolute_gas_components_summary(item.components, language))}</td>"
        f"<td>{escape(_dexp_text(item.dexp, labels))}</td>"
        "</tr>"
        for candidate, item in zip(report.candidates, statistics, strict=False)
    )
    return (
        f"<h2>{escape(labels['title'])}</h2>"
        f"<p><small>{escape(labels['zero_note'])}</small></p>"
        "<table><thead><tr>"
        f"<th>{escape(labels['interval'])}</th><th>{escape(labels['raw'])}</th>"
        f"<th>{escape(labels['normalized'])}</th><th>{escape(labels['absolute'])}</th><th>DEXP</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )

def manual_section_heading(language: AppLanguage) -> str:
    return _labels(language)["manual"]


def _curve_stats(
    curve: CurveData | None,
    depth: np.ndarray,
    mask: np.ndarray,
    *,
    gas: bool,
) -> IntervalCurveStatistics | None:
    if curve is None:
        return None
    return _stats_from_values(
        curve.metadata.original_mnemonic,
        curve.metadata.unit or "",
        np.asarray(curve.values, dtype=np.float64),
        depth,
        mask,
        gas=gas,
    )


def _stats_from_values(
    mnemonic: str,
    unit: str,
    values: np.ndarray,
    depth: np.ndarray,
    mask: np.ndarray,
    *,
    gas: bool,
) -> IntervalCurveStatistics:
    if values.shape != depth.shape:
        return IntervalCurveStatistics(mnemonic, unit, None, None, None, None, None, 0, 0)
    interval = values[mask & np.isfinite(values)]
    minimum = float(np.min(interval)) if interval.size else None
    mean = float(np.mean(interval)) if interval.size else None
    median = float(np.median(interval)) if interval.size else None
    maximum = float(np.max(interval)) if interval.size else None
    all_mask = np.isfinite(depth) & np.isfinite(values)
    if gas:
        all_mask &= values >= 0.0
    all_values = values[all_mask]
    background = None
    if all_values.size:
        background = (
            float(np.expm1(np.median(np.log1p(all_values))))
            if gas
            else float(np.median(all_values))
        )
    return IntervalCurveStatistics(
        mnemonic,
        unit,
        minimum,
        mean,
        median,
        maximum,
        background,
        int(interval.size),
        int(np.count_nonzero(interval > _EPS)),
    )


def _find_curve(dataset: Dataset, names: tuple[str | None, ...]) -> CurveData | None:
    wanted = {_normalize(name) for name in names if name}
    for name in names:
        if name and (curve := dataset.curve_by_mnemonic(name)) is not None:
            return curve
    for curve in dataset.curves.values():
        aliases = {
            _normalize(curve.metadata.original_mnemonic),
            _normalize(curve.metadata.canonical_mnemonic or ""),
        }
        if wanted & aliases:
            return curve
    return None


def _curve_summary(
    item: IntervalCurveStatistics,
    label: str,
    labels: dict[str, str],
) -> str:
    unit = f" [{item.unit}]" if item.unit else ""
    if not item.has_values:
        return f"{label} {item.mnemonic}{unit}: {labels['no_data']}"
    return f"{label} {item.mnemonic}{unit}: {_statistics_text(item, labels)}"


def _curve_html(item: IntervalCurveStatistics | None, labels: dict[str, str]) -> str:
    if item is None or not item.has_values:
        return "-"
    unit = f" {escape(item.unit)}" if item.unit else ""
    return (
        f"<b>{escape(item.mnemonic)}</b>{unit}<br>"
        f"{escape(_statistics_text(item, labels))}"
    )


def _components_text(
    items: tuple[IntervalCurveStatistics, ...],
    labels: dict[str, str],
) -> str:
    if not items:
        return labels["no_data"]
    ordered = sorted(items, key=lambda item: _component_sort_key(_component_name(item.mnemonic)))
    return "; ".join(_stat_triplet(item, labels) for item in ordered)


def _dexp_text(item: IntervalCurveStatistics | None, labels: dict[str, str]) -> str:
    if item is None or not item.has_values:
        return labels["no_data"]
    return _statistics_text(item, labels)


def _statistics_text(item: IntervalCurveStatistics, labels: dict[str, str]) -> str:
    return (
        f"{labels['minimum']} {_number(item.minimum)}; "
        f"{labels['mean']} {_number(item.mean)}; "
        f"{labels['maximum']} {_number(item.maximum)}"
    )


def _stat_triplet(item: IntervalCurveStatistics, labels: dict[str, str]) -> str:
    unit = f" [{item.unit}]" if item.unit else ""
    return f"{_component_name(item.mnemonic)}{unit}: {_statistics_text(item, labels)}"


def _component_name(mnemonic: str) -> str:
    normalized = _normalize(mnemonic)
    for name in ("IC4", "NC4", "IC5", "NC5", "C1", "C2", "C3", "C4", "C5"):
        if name in normalized:
            return name
    return mnemonic


def _component_sort_key(name: str) -> tuple[int, str]:
    order = {"C1": 0, "C2": 1, "C3": 2, "IC4": 3, "NC4": 4, "C4": 5, "IC5": 6, "NC5": 7, "C5": 8}
    return order.get(name, 99), name

def _normalize(value: str) -> str:
    return re.sub(r"[^0-9A-ZА-ЯЁ]+", "", value.upper())


def _family(mnemonic: str) -> str:
    normalized = _normalize(mnemonic)
    return next((name for name in ("C1", "C2", "C3", "C4", "C5") if name in normalized), mnemonic)


def _range(item: IntervalCurveStatistics) -> str:
    return f"{_number(item.minimum)}-{_number(item.maximum)}"


def _number(value: float | None) -> str:
    return "-" if value is None or not np.isfinite(value) else f"{value:.6g}"


def _drop_sentence(text: str) -> str:
    position = text.find(". ")
    return "" if position < 0 else text[position + 2 :].lstrip()


def _labels(language: AppLanguage) -> dict[str, str]:
    if language is AppLanguage.RU:
        return {
            "raw": "Исходный общий газ",
            "normalized": "Нормализованный газ",
            "absolute": "Абсолютный газ",
            "minimum": "мин",
            "mean": "среднее",
            "maximum": "макс",
            "no_data": "нет данных",
            "interval_zero": (
                "В интервале C2-C5 не зарегистрированы выше нуля; это не доказывает "
                "отсутствие углеводородов без проверки общего газа и качества данных."
            ),
            "title": "Газ по интервалам: минимум, среднее и максимум",
            "zero_note": (
                "0 — реальное нулевое измерение; '-' — нет подходящей кривой или отсчётов."
            ),
            "interval": "Интервал",
            "manual": "Интервалы, подтверждённые геологом",
        }
    if language is AppLanguage.KK:
        return {
            "raw": "Бастапқы жалпы газ",
            "normalized": "Нормаланған газ",
            "absolute": "Абсолюттік газ",
            "minimum": "ең аз",
            "mean": "орташа",
            "maximum": "ең көп",
            "no_data": "дерек жоқ",
            "interval_zero": (
                "Аралықта C2-C5 нөлден жоғары тіркелмеген; жалпы газ бен дерек сапасын "
                "тексермей, бұл көмірсутектердің жоқ екенін дәлелдемейді."
            ),
            "title": "Аралықтар бойынша газ: ең аз, орташа және ең көп",
            "zero_note": "0 — нақты нөлдік өлшем; '-' — сәйкес қисық немесе есеп жоқ.",
            "interval": "Аралық",
            "manual": "Геолог растаған аралықтар",
        }
    return {
        "raw": "Raw total gas",
        "normalized": "Normalized gas",
        "absolute": "Absolute gas",
        "minimum": "min",
        "mean": "mean",
        "maximum": "max",
        "no_data": "no data",
        "interval_zero": (
            "C2-C5 were not recorded above zero in the interval; this does not prove "
            "hydrocarbon absence without total-gas and data-quality review."
        ),
        "title": "Gas by interval: minimum, mean, and maximum",
        "zero_note": "0 is an actual zero measurement; '-' means no suitable curve or samples.",
        "interval": "Interval",
        "manual": "Geologist-confirmed intervals",
    }


__all__ = [
    "CandidateIntervalGasStatistics",
    "IntervalCurveStatistics",
    "build_candidate_interval_statistics",
    "build_interval_component_sum_statistics",
    "build_interval_statistics",
    "absolute_gas_components_summary",
    "enhanced_fluid_hypothesis_basis",
    "interval_gas_summary",
    "interval_gas_table_html",
    "manual_section_heading",
]
