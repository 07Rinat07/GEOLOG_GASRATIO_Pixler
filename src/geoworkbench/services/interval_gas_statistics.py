from __future__ import annotations

from dataclasses import dataclass
from html import escape
import re

import numpy as np

from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.services.hydrocarbon_interpretation_modes import (
    HydrocarbonCandidateInterval,
    HydrocarbonInterpretationReport,
)
from geoworkbench.services.localization import AppLanguage


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
    for name in ("C1", "C2", "C3"):
        item = _curve_stats(_find_curve(dataset, (name,)), depth, mask, gas=False)
        if item is not None:
            components.append(item)
    for total, iso, normal in (("C4", "IC4", "NC4"), ("C5", "IC5", "NC5")):
        item = _component_stats(dataset, depth, mask, total, iso, normal)
        if item is not None:
            components.append(item)

    dexp = _curve_stats(_find_curve(dataset, ("DEXPC", "DEXP")), depth, mask, gas=False)
    return CandidateIntervalGasStatistics(primary, raw_total, tuple(components), dexp)


def enhanced_fluid_hypothesis_basis(
    base_text: str,
    candidate: HydrocarbonCandidateInterval,
    statistics: CandidateIntervalGasStatistics,
    language: AppLanguage = AppLanguage.RU,
) -> str:
    labels = _labels(language)
    cleaned = base_text.strip()
    interval_zero = candidate.interval_wetness is not None and abs(candidate.interval_wetness) <= _EPS
    background_zero = (
        candidate.background_wetness is not None
        and abs(candidate.background_wetness) <= _EPS
    )
    if interval_zero and background_zero:
        cleaned = _drop_sentence(cleaned)
        if candidate.interval_balance is None and candidate.interval_character is None:
            cleaned = _drop_sentence(cleaned)
        cleaned = f"{labels['wetness_zero']} {cleaned}".strip()
    elif interval_zero:
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
    components = {_family(item.mnemonic): item for item in statistics.components}
    if (c1 := components.get("C1")) is not None:
        parts.append(f"C1: {_range(c1)} {c1.unit}".strip())
    heavier = [components[name] for name in ("C2", "C3", "C4", "C5") if name in components]
    if heavier and all(item.is_zero_only for item in heavier):
        parts.append(labels["heavy_zero"])
    elif heavier:
        parts.append("C2-C5: " + "; ".join(f"{_family(x.mnemonic)} {_range(x)}" for x in heavier))
    if statistics.dexp is not None and statistics.dexp.has_values:
        item = statistics.dexp
        parts.append(
            f"{item.mnemonic}: min {_number(item.minimum)}, "
            f"{labels['median']} {_number(item.median)}, max {_number(item.maximum)}"
        )
    return ". ".join(parts) + ("." if parts else "")


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
        f"<td>{escape(_components_text(item.components, labels))}</td>"
        f"<td>{escape(_dexp_text(item.dexp, labels))}</td>"
        "</tr>"
        for candidate, item in zip(report.candidates, statistics, strict=False)
    )
    return (
        f"<h2>{escape(labels['title'])}</h2>"
        f"<p><small>{escape(labels['zero_note'])}</small></p>"
        "<table><thead><tr>"
        f"<th>{escape(labels['interval'])}</th><th>{escape(labels['raw'])}</th>"
        f"<th>{escape(labels['normalized'])}</th><th>C1-C5</th><th>DEXP</th>"
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


def _component_stats(
    dataset: Dataset,
    depth: np.ndarray,
    mask: np.ndarray,
    total: str,
    iso: str,
    normal: str,
) -> IntervalCurveStatistics | None:
    if curve := _find_curve(dataset, (total,)):
        return _curve_stats(curve, depth, mask, gas=False)
    curves = tuple(curve for name in (iso, normal) if (curve := _find_curve(dataset, (name,))))
    if not curves:
        return None
    values = np.zeros(depth.shape, dtype=np.float64)
    valid = np.zeros(depth.shape, dtype=bool)
    for curve in curves:
        source = np.asarray(curve.values, dtype=np.float64)
        if source.shape != depth.shape:
            continue
        finite = np.isfinite(source)
        values[finite] += source[finite]
        valid |= finite
    values[~valid] = np.nan
    return _stats_from_values(
        f"{iso}+{normal}",
        next((curve.metadata.unit or "" for curve in curves), ""),
        values,
        depth,
        mask,
        gas=False,
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
    return (
        f"{label} {item.mnemonic}{unit}: {labels['background']} {_number(item.background)}, "
        f"min {_number(item.minimum)}, {labels['mean']} {_number(item.mean)}, "
        f"{labels['median']} {_number(item.median)}, max {_number(item.maximum)}"
    )


def _curve_html(item: IntervalCurveStatistics | None, labels: dict[str, str]) -> str:
    if item is None or not item.has_values:
        return "-"
    unit = f" {escape(item.unit)}" if item.unit else ""
    return (
        f"<b>{escape(item.mnemonic)}</b>{unit}<br>"
        f"{escape(labels['background'])} {_number(item.background)}; min {_number(item.minimum)}; "
        f"{escape(labels['mean'])} {_number(item.mean)}; "
        f"{escape(labels['median'])} {_number(item.median)}; max {_number(item.maximum)}"
    )


def _components_text(
    items: tuple[IntervalCurveStatistics, ...],
    labels: dict[str, str],
) -> str:
    if not items:
        return labels["no_data"]
    values = {_family(item.mnemonic): item for item in items}
    parts = [f"C1: {_range(values['C1'])} {values['C1'].unit}".strip()] if "C1" in values else []
    heavier = [values[name] for name in ("C2", "C3", "C4", "C5") if name in values]
    if heavier and all(item.is_zero_only for item in heavier):
        parts.append(labels["heavy_zero"])
    else:
        parts.extend(f"{_family(item.mnemonic)}: {_range(item)} {item.unit}".strip() for item in heavier)
    return "; ".join(parts)


def _dexp_text(item: IntervalCurveStatistics | None, labels: dict[str, str]) -> str:
    if item is None or not item.has_values:
        return labels["no_data"]
    return f"min {_number(item.minimum)}; {labels['median']} {_number(item.median)}; max {_number(item.maximum)}"


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
    common = {"median": "median", "mean": "mean", "background": "background", "no_data": "no data"}
    if language is AppLanguage.RU:
        return {
            **common,
            "raw": "Исходный общий газ",
            "normalized": "Нормализованный газ",
            "median": "медиана",
            "mean": "среднее",
            "background": "фон",
            "no_data": "нет данных",
            "heavy_zero": "C2-C5: выше нуля не зарегистрированы",
            "wetness_zero": (
                "C2-C5 в интервале и на фоне не зарегистрированы выше нуля; нулевая доля "
                "не используется как самостоятельное доказательство сухого газа."
            ),
            "interval_zero": (
                "В интервале C2-C5 не зарегистрированы выше нуля; 0 без общего газа и "
                "контроля качества не доказывает отсутствие углеводородов."
            ),
            "title": "Показания газа по интервалам",
            "zero_note": (
                "0 — реальное нулевое измерение; '-' — нет подходящей кривой или отсчётов. "
                "Фон указан в единицах соответствующей газовой кривой."
            ),
            "interval": "Интервал",
            "manual": "Интервалы, подтверждённые геологом",
        }
    if language is AppLanguage.KK:
        return {
            **common,
            "raw": "Бастапқы жалпы газ",
            "normalized": "Нормаланған газ",
            "median": "медиана",
            "mean": "орташа",
            "background": "фон",
            "no_data": "дерек жоқ",
            "heavy_zero": "C2-C5: нөлден жоғары мәндер тіркелмеген",
            "wetness_zero": (
                "Аралықта және фонда C2-C5 нөлден жоғары тіркелмеген; нөлдік үлес құрғақ "
                "газдың жеке дәлелі ретінде қолданылмайды."
            ),
            "interval_zero": (
                "Аралықта C2-C5 нөлден жоғары тіркелмеген; жалпы газ бен сапа бақылауынсыз "
                "0 көмірсутектер жоқ екенін дәлелдемейді."
            ),
            "title": "Аралықтар бойынша газ көрсеткіштері",
            "zero_note": (
                "0 — нақты нөлдік өлшем; '-' — сәйкес қисық немесе есеп жоқ. Фон газ "
                "қисығының бірліктерімен берілген."
            ),
            "interval": "Аралық",
            "manual": "Геолог растаған аралықтар",
        }
    return {
        **common,
        "raw": "Raw total gas",
        "normalized": "Normalized gas",
        "heavy_zero": "C2-C5: no values above zero were recorded",
        "wetness_zero": (
            "C2-C5 were not recorded above zero in the interval or background; a zero share "
            "is not standalone evidence of dry gas."
        ),
        "interval_zero": (
            "C2-C5 were not recorded above zero; zero does not prove hydrocarbon absence "
            "without total-gas and quality context."
        ),
        "title": "Gas readings by interval",
        "zero_note": (
            "0 is an actual zero measurement; '-' means no suitable curve or samples. "
            "Background is reported in the gas curve's units."
        ),
        "interval": "Interval",
        "manual": "Geologist-confirmed intervals",
    }


__all__ = [
    "CandidateIntervalGasStatistics",
    "IntervalCurveStatistics",
    "build_candidate_interval_statistics",
    "build_interval_statistics",
    "enhanced_fluid_hypothesis_basis",
    "interval_gas_summary",
    "interval_gas_table_html",
    "manual_section_heading",
]
