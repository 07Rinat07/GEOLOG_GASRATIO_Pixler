from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape

import numpy as np

from geoworkbench.domain.models import Dataset
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.las_parameter_resolver import (
    ParameterResolutionError,
    resolve_gas_ratio_inputs,
)
from geoworkbench.services.localization import AppLanguage


@dataclass(frozen=True, slots=True)
class InterpretationMethodStatus:
    method: str
    curve_mnemonics: tuple[str, ...]
    available_mnemonics: tuple[str, ...]
    source: str

    @property
    def available(self) -> bool:
        return bool(self.available_mnemonics)


@dataclass(frozen=True, slots=True)
class HydrocarbonCandidateInterval:
    top_depth: float
    bottom_depth: float
    sample_count: int
    anomaly_strength: str
    primary_mnemonic: str
    max_robust_z: float
    max_primary_value: float
    fluid_hypothesis: str
    interval_wetness: float | None
    background_wetness: float | None
    wetness_robust_z: float | None
    metrics: tuple[tuple[str, float], ...]
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ManualInterpretationInterval:
    interpretation_name: str
    top_depth: float
    bottom_depth: float
    interval_type: str
    label: str
    comment: str


@dataclass(frozen=True, slots=True)
class HydrocarbonInterpretationReport:
    project_name: str
    well_name: str
    dataset_id: str
    dataset_name: str
    generated_at: str
    depth_unit: str
    threshold: float
    primary_mnemonic: str | None
    baseline_median: float | None
    robust_scale: float | None
    methods: tuple[InterpretationMethodStatus, ...]
    candidates: tuple[HydrocarbonCandidateInterval, ...]
    manual_intervals: tuple[ManualInterpretationInterval, ...]
    warnings: tuple[str, ...]


_METHODS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    (
        "Haworth wetness/balance/character",
        ("WH", "BH", "CH"),
        "Haworth, Sellens & Whittaker (1985), AAPG Bulletin 69(8), 1305–1310.",
    ),
    (
        "Pixler hydrocarbon ratios",
        ("C1_C2", "C1_C3", "C1_C4", "C1_C5"),
        "Pixler (1969), Journal of Petroleum Technology. DOI 10.2118/2254-PA.",
    ),
    (
        "Drilling-normalized methane",
        ("C1_NORM",),
        "US20140379265A1, Equation 2.",
    ),
    (
        "Jorden–Shirley / Rehm–McClendon d-exponent",
        ("DEXP", "DEXPC", "NCT", "DEXPC_NCT"),
        "Jorden & Shirley (1966), SPE 1407; Rehm & McClendon (1971), SPE 3601.",
    ),
)

_PRIMARY_GAS_ORDER = ("C1_NORM", "TG_NORM", "TG_CALC", "TG", "TGAS", "TOTALGAS", "TOTAL_GAS")
_CONTEXT_CURVES = (
    "WH",
    "BH",
    "CH",
    "C1_C2",
    "C1_C3",
    "C1_C4",
    "C1_C5",
    "DEXP",
    "DEXPC",
    "DEXPC_NCT",
)
_FLUID_CHARACTER_Z_THRESHOLD = 2.0


def build_hydrocarbon_interpretation_report(
    session: ProjectSession,
    *,
    threshold: float = 3.0,
) -> HydrocarbonInterpretationReport:
    if not np.isfinite(threshold) or not 2.0 <= threshold <= 10.0:
        raise ValueError("Порог robust z должен находиться в диапазоне 2–10")
    dataset = session.current_dataset
    well = session.current_well
    if dataset is None or well is None:
        raise RuntimeError("Сначала выберите скважину и набор данных")

    methods = tuple(_method_status(dataset, *spec) for spec in _METHODS)
    manual = tuple(
        ManualInterpretationInterval(
            interpretation.name,
            interval.top_depth,
            interval.bottom_depth,
            interval.interval_type,
            interval.label,
            interval.comment or "",
        )
        for interpretation in sorted(
            well.interpretations.values(), key=lambda item: item.name.casefold()
        )
        for interval in sorted(
            interpretation.intervals,
            key=lambda item: (item.top_depth, item.bottom_depth, item.label.casefold()),
        )
    )

    available_primary_curves = tuple(
        curve
        for mnemonic in _PRIMARY_GAS_ORDER
        if (curve := dataset.curve_by_mnemonic(mnemonic)) is not None
    )
    primary = next(
        (
            curve
            for curve in available_primary_curves
            if _valid_gas_sample_count(dataset, curve.values) >= 20
        ),
        available_primary_curves[0] if available_primary_curves else None,
    )
    warnings = [
        (
            "Автоматически отмечаются только кандидаты по относительной газовой аномалии. "
            "Это не заключение о насыщении, типе флюида или промышленной продуктивности."
        ),
        (
            "Предварительная интерпретация флюида сравнивает долю C2–C5 с фоном "
            "текущей скважины и выдаёт «вероятный газ», «вероятные жидкие УВ» "
            "либо «смешанный/неопределённый тип». Категория «вода» по mud-gas "
            "не назначается."
        ),
        (
            "Перед принятием интервалов проверьте газовый лаг, режим дегазатора, единицы, "
            "буровой режим, литологию и локально откалиброванные фоновые уровни."
        ),
        (
            "DEXP/DEXPC используются как контекст бурения и давления, а не как "
            "самостоятельный признак углеводородов."
        ),
    ]
    candidates: tuple[HydrocarbonCandidateInterval, ...] = ()
    baseline_median: float | None = None
    robust_scale: float | None = None
    primary_name: str | None = None
    if primary is None:
        warnings.append(
            "Нет C1_NORM, TG_NORM, TG_CALC или исходного Total Gas: автоматический поиск не выполнен."
        )
    else:
        primary_name = primary.metadata.original_mnemonic
        (
            candidates,
            baseline_median,
            robust_scale,
            detection_warning,
        ) = _detect_candidates(dataset, primary_name, threshold)
        if detection_warning:
            warnings.append(detection_warning)

    return HydrocarbonInterpretationReport(
        session.project.name,
        well.name,
        dataset.dataset_id,
        dataset.name,
        datetime.now().astimezone().isoformat(timespec="seconds"),
        dataset.active_index.unit or "",
        float(threshold),
        primary_name,
        baseline_median,
        robust_scale,
        methods,
        candidates,
        manual,
        tuple(warnings),
    )


def _method_status(
    dataset: Dataset,
    method: str,
    mnemonics: tuple[str, ...],
    source: str,
) -> InterpretationMethodStatus:
    available: list[str] = []
    seen: set[str] = set()
    for mnemonic in mnemonics:
        curve = dataset.curve_by_mnemonic(mnemonic)
        if curve is None or curve.metadata.curve_id in seen:
            continue
        seen.add(curve.metadata.curve_id)
        available.append(curve.metadata.original_mnemonic)
    return InterpretationMethodStatus(method, mnemonics, tuple(available), source)


def _detect_candidates(
    dataset: Dataset,
    primary_mnemonic: str,
    threshold: float,
) -> tuple[
    tuple[HydrocarbonCandidateInterval, ...],
    float | None,
    float | None,
    str | None,
]:
    primary_curve = dataset.curve_by_mnemonic(primary_mnemonic)
    if primary_curve is None:
        return (), None, None, "Основная газовая кривая не найдена."
    depth = np.asarray(dataset.depth, dtype=np.float64)
    values = np.asarray(primary_curve.values, dtype=np.float64)
    if values.shape != depth.shape:
        return (), None, None, "Основная газовая кривая имеет неверное число отсчётов."
    valid = np.isfinite(depth) & np.isfinite(values) & (values >= 0.0)
    if np.count_nonzero(valid) < 20:
        return (
            (),
            None,
            None,
            "Для устойчивого фонового уровня требуется не менее 20 корректных газовых отсчётов.",
        )
    transformed = np.full(values.shape, np.nan, dtype=np.float64)
    transformed[valid] = np.log1p(values[valid])
    finite_values = transformed[valid]
    median, scale = _robust_center_scale(finite_values)
    if scale is None:
        return (), median, None, "Газовая кривая не имеет достаточного разброса для поиска аномалий."

    robust_z = np.full(values.shape, np.nan, dtype=np.float64)
    robust_z[valid] = (transformed[valid] - median) / scale
    flagged = valid & (robust_z >= threshold)
    if not np.any(flagged):
        return (), median, scale, None

    valid_depth = np.sort(np.unique(depth[valid]))
    differences = np.diff(valid_depth)
    positive_steps = differences[np.isfinite(differences) & (differences > 0.0)]
    step = float(np.median(positive_steps)) if positive_steps.size else 1.0
    max_gap = max(step * 2.5, np.finfo(np.float64).eps)
    flagged_indices = np.flatnonzero(flagged)
    flagged_indices = flagged_indices[np.argsort(depth[flagged_indices], kind="stable")]
    fluid_context = _build_fluid_interpretation_context(
        dataset,
        valid & ~flagged,
    )
    groups: list[list[int]] = []
    for row_index in flagged_indices:
        if not groups or depth[row_index] - depth[groups[-1][-1]] > max_gap:
            groups.append([int(row_index)])
        else:
            groups[-1].append(int(row_index))

    overall_top = float(np.min(depth[valid]))
    overall_bottom = float(np.max(depth[valid]))
    candidates: list[HydrocarbonCandidateInterval] = []
    for group in groups:
        group_indices = np.asarray(group, dtype=np.int64)
        top = max(overall_top, float(np.min(depth[group_indices])) - step / 2.0)
        bottom = min(overall_bottom, float(np.max(depth[group_indices])) + step / 2.0)
        if bottom <= top:
            bottom = top + step
        maximum_z = float(np.nanmax(robust_z[group_indices]))
        maximum_primary = float(np.nanmax(values[group_indices]))
        context_mask = np.isfinite(depth) & (depth >= top) & (depth <= bottom)
        metrics = _interval_metrics(dataset, context_mask)
        (
            fluid_hypothesis,
            interval_wetness,
            background_wetness,
            wetness_robust_z,
        ) = _preliminary_fluid_hypothesis(
            context_mask,
            fluid_context,
        )
        anomaly_strength = (
            "high"
            if maximum_z >= 6.0 and group_indices.size >= 2
            else "medium"
            if maximum_z >= 4.0 or group_indices.size >= 2
            else "low"
        )
        evidence_parts = [
            f"{primary_mnemonic}: max robust z = {maximum_z:.2f} (threshold {threshold:.2f})",
            f"{primary_mnemonic}: max = {maximum_primary:.6g}",
            f"flagged samples = {group_indices.size}",
        ]
        if metrics:
            evidence_parts.append(
                "context medians: "
                + ", ".join(f"{name}={value:.6g}" for name, value in metrics)
            )
        candidates.append(
            HydrocarbonCandidateInterval(
                top,
                bottom,
                int(group_indices.size),
                anomaly_strength,
                primary_mnemonic,
                maximum_z,
                maximum_primary,
                fluid_hypothesis,
                interval_wetness,
                background_wetness,
                wetness_robust_z,
                metrics,
                tuple(evidence_parts),
            )
        )
    return tuple(candidates), median, scale, None


def _robust_center_scale(values: np.ndarray) -> tuple[float, float | None]:
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    scale = 1.4826 * mad
    if not np.isfinite(scale) or scale <= np.finfo(np.float64).eps:
        q25, q75 = np.percentile(values, [25.0, 75.0])
        scale = float((q75 - q25) / 1.349)
    if not np.isfinite(scale) or scale <= np.finfo(np.float64).eps:
        scale = float(np.std(values))
    if not np.isfinite(scale) or scale <= np.finfo(np.float64).eps:
        return median, None
    return median, scale


def _build_fluid_interpretation_context(
    dataset: Dataset,
    background_mask: np.ndarray,
) -> tuple[np.ndarray | None, float | None, float | None]:
    try:
        gases = resolve_gas_ratio_inputs(dataset)
    except (ParameterResolutionError, ValueError):
        return None, None, None
    c1 = gases["C1"]
    arrays = tuple(gases.values())
    if any(values.shape != c1.shape for values in arrays) or c1.shape != background_mask.shape:
        return None, None, None

    c4 = _summed_component(gases, "C4", "IC4", "NC4", c1)
    c5 = _summed_component(gases, "C5", "IC5", "NC5", c1)
    heavier = gases["C2"] + gases["C3"] + c4 + c5
    total = c1 + heavier
    wetness = np.full(c1.shape, np.nan, dtype=np.float64)
    valid = np.isfinite(c1) & np.isfinite(heavier) & np.isfinite(total) & (total > 0.0)
    wetness[valid] = 100.0 * heavier[valid] / total[valid]

    background_values = wetness[background_mask & valid]
    if background_values.size < 20:
        return wetness, None, None
    background_median, background_scale = _robust_center_scale(background_values)
    return wetness, background_median, background_scale


def _preliminary_fluid_hypothesis(
    interval_mask: np.ndarray,
    context: tuple[np.ndarray | None, float | None, float | None],
) -> tuple[str, float | None, float | None, float | None]:
    wetness, background_median, background_scale = context
    if wetness is None or background_median is None:
        return "insufficient_data", None, None, None
    interval_values = wetness[interval_mask & np.isfinite(wetness)]
    if interval_values.size == 0:
        return "insufficient_data", None, None, None
    interval_median = float(np.median(interval_values))
    if background_scale is None:
        return "indeterminate", interval_median, background_median, None
    relative_z = (interval_median - background_median) / background_scale
    if relative_z >= _FLUID_CHARACTER_Z_THRESHOLD:
        hypothesis = "probable_liquid_hydrocarbons"
    elif relative_z <= -_FLUID_CHARACTER_Z_THRESHOLD:
        hypothesis = "probable_gas"
    else:
        hypothesis = "indeterminate"
    return hypothesis, interval_median, background_median, float(relative_z)


def _summed_component(
    gases: dict[str, np.ndarray],
    total_name: str,
    iso_name: str,
    normal_name: str,
    template: np.ndarray,
) -> np.ndarray:
    if iso_name in gases or normal_name in gases:
        return gases.get(iso_name, np.zeros_like(template)) + gases.get(
            normal_name,
            np.zeros_like(template),
        )
    return gases.get(total_name, np.zeros_like(template))


def _valid_gas_sample_count(dataset: Dataset, values: np.ndarray) -> int:
    depth = np.asarray(dataset.depth)
    candidate = np.asarray(values)
    if candidate.shape != depth.shape:
        return 0
    return int(np.count_nonzero(np.isfinite(depth) & np.isfinite(candidate) & (candidate >= 0.0)))


def _interval_metrics(dataset: Dataset, mask: np.ndarray) -> tuple[tuple[str, float], ...]:
    metrics: list[tuple[str, float]] = []
    for mnemonic in _CONTEXT_CURVES:
        curve = dataset.curve_by_mnemonic(mnemonic)
        if curve is None:
            continue
        values = np.asarray(curve.values, dtype=np.float64)
        if values.shape != mask.shape:
            continue
        finite = mask & np.isfinite(values)
        if np.any(finite):
            metrics.append((mnemonic, float(np.median(values[finite]))))
    return tuple(metrics)


_HTML_LABELS = {
    AppLanguage.RU: {
        "title": "Отчёт по интерпретации газового каротажа",
        "project": "Проект",
        "well": "Скважина",
        "dataset": "Набор данных",
        "created": "Сформирован",
        "primary": "Основная кривая",
        "threshold": "Порог robust z",
        "methods": "Методы и доступность",
        "method": "Метод",
        "curves": "Доступные кривые",
        "source": "Источник",
        "candidates": "Кандидатные интервалы УВ-проявлений",
        "interval": "Интервал",
        "strength": "Относительная сила аномалии",
        "samples": "Отсчётов",
        "evidence": "Основание",
        "hypothesis": "Предварительная интерпретация",
        "manual": "Интервалы, подтверждённые геологом",
        "interpretation": "Интерпретация",
        "type": "Тип",
        "label": "Подпись",
        "comment": "Комментарий",
        "warnings": "Ограничения методики",
        "empty": "Кандидатные интервалы по выбранному порогу не найдены.",
        "no_manual": "Подтверждённые геологом интервалы пока не заполнены.",
        "hypothesis_probable_gas": "вероятный газ",
        "hypothesis_probable_liquid_hydrocarbons": (
            "вероятные жидкие УВ (нефть/конденсат)"
        ),
        "hypothesis_indeterminate": "УВ-проявление смешанного/неопределённого типа",
        "hypothesis_insufficient_data": (
            "газовое УВ-проявление; C1–C5 недостаточно для определения типа"
        ),
        "wetness_basis": (
            "Относительная доля C2–C5: интервал {interval:.2f}%, "
            "фон {background:.2f}%, robust z={robust_z:.2f}."
        ),
        "wetness_no_scale": (
            "Относительная доля C2–C5: интервал {interval:.2f}%, "
            "фон {background:.2f}%; фон не имеет устойчивого разброса."
        ),
        "wetness_insufficient": (
            "Для интерпретации нужны согласованные C1–C5 и не менее 20 фоновых отсчётов."
        ),
        "low": "низкая",
        "medium": "средняя",
        "high": "высокая",
        "yes": "доступен",
        "no": "нет кривых",
    },
    AppLanguage.KK: {
        "title": "Газ каротажын интерпретациялау есебі",
        "project": "Жоба",
        "well": "Ұңғыма",
        "dataset": "Деректер жинағы",
        "created": "Құрылған",
        "primary": "Негізгі қисық",
        "threshold": "Robust z шегі",
        "methods": "Әдістер және қолжетімділік",
        "method": "Әдіс",
        "curves": "Қолжетімді қисықтар",
        "source": "Дереккөз",
        "candidates": "Көмірсутек көріністерінің кандидат аралықтары",
        "interval": "Аралық",
        "strength": "Аномалияның салыстырмалы күші",
        "samples": "Есептер",
        "evidence": "Негіз",
        "hypothesis": "Алдын ала интерпретация",
        "manual": "Геолог растаған аралықтар",
        "interpretation": "Интерпретация",
        "type": "Түр",
        "label": "Белгі",
        "comment": "Түсініктеме",
        "warnings": "Әдістеме шектеулері",
        "empty": "Таңдалған шек бойынша кандидат аралықтар табылмады.",
        "no_manual": "Геолог растаған аралықтар әлі толтырылмаған.",
        "hypothesis_probable_gas": "ықтимал газ",
        "hypothesis_probable_liquid_hydrocarbons": (
            "ықтимал сұйық көмірсутектер (мұнай/конденсат)"
        ),
        "hypothesis_indeterminate": "аралас/анықталмаған түрдегі көмірсутек көрінісі",
        "hypothesis_insufficient_data": (
            "газдық көмірсутек көрінісі; түрін анықтау үшін C1–C5 жеткіліксіз"
        ),
        "wetness_basis": (
            "C2–C5 салыстырмалы үлесі: аралық {interval:.2f}%, "
            "фон {background:.2f}%, robust z={robust_z:.2f}."
        ),
        "wetness_no_scale": (
            "C2–C5 салыстырмалы үлесі: аралық {interval:.2f}%, "
            "фон {background:.2f}%; фонның тұрақты шашырауы жоқ."
        ),
        "wetness_insufficient": (
            "Интерпретация үшін үйлесімді C1–C5 және кемінде 20 фондық есеп қажет."
        ),
        "low": "төмен",
        "medium": "орташа",
        "high": "жоғары",
        "yes": "қолжетімді",
        "no": "қисықтар жоқ",
    },
    AppLanguage.EN: {
        "title": "Mud-gas interpretation report",
        "project": "Project",
        "well": "Well",
        "dataset": "Dataset",
        "created": "Generated",
        "primary": "Primary curve",
        "threshold": "Robust z threshold",
        "methods": "Methods and availability",
        "method": "Method",
        "curves": "Available curves",
        "source": "Source",
        "candidates": "Candidate hydrocarbon-show intervals",
        "interval": "Interval",
        "strength": "Relative anomaly strength",
        "samples": "Samples",
        "evidence": "Evidence",
        "hypothesis": "Preliminary interpretation",
        "manual": "Geologist-confirmed intervals",
        "interpretation": "Interpretation",
        "type": "Type",
        "label": "Label",
        "comment": "Comment",
        "warnings": "Method limitations",
        "empty": "No candidate intervals were found at the selected threshold.",
        "no_manual": "No geologist-confirmed intervals have been entered.",
        "hypothesis_probable_gas": "probable gas",
        "hypothesis_probable_liquid_hydrocarbons": (
            "probable liquid hydrocarbons (oil/condensate)"
        ),
        "hypothesis_indeterminate": "mixed/indeterminate hydrocarbon show",
        "hypothesis_insufficient_data": (
            "gas hydrocarbon show; insufficient C1–C5 to determine fluid type"
        ),
        "wetness_basis": (
            "Relative C2–C5 fraction: interval {interval:.2f}%, "
            "background {background:.2f}%, robust z={robust_z:.2f}."
        ),
        "wetness_no_scale": (
            "Relative C2–C5 fraction: interval {interval:.2f}%, "
            "background {background:.2f}%; background has no robust spread."
        ),
        "wetness_insufficient": (
            "Interpretation requires consistent C1–C5 and at least 20 background samples."
        ),
        "low": "low",
        "medium": "medium",
        "high": "high",
        "yes": "available",
        "no": "no curves",
    },
}


def hydrocarbon_interpretation_html(
    report: HydrocarbonInterpretationReport,
    language: AppLanguage = AppLanguage.RU,
) -> str:
    labels = _HTML_LABELS[language]
    method_rows = "".join(
        "<tr>"
        f"<td>{escape(method.method)}</td>"
        f"<td>{escape(', '.join(method.available_mnemonics) or labels['no'])}</td>"
        f"<td>{escape(method.source)}</td>"
        "</tr>"
        for method in report.methods
    )
    candidate_rows = "".join(
        "<tr>"
        f"<td>{candidate.top_depth:.2f}–{candidate.bottom_depth:.2f} "
        f"{escape(report.depth_unit)}</td>"
        f"<td>{escape(labels[candidate.anomaly_strength])}</td>"
        f"<td>{escape(fluid_hypothesis_label(candidate, language))}<br>"
        f"<small>{escape(fluid_hypothesis_basis(candidate, language))}</small></td>"
        f"<td>{candidate.sample_count}</td>"
        f"<td>{escape('; '.join(candidate.evidence))}</td>"
        "</tr>"
        for candidate in report.candidates
    )
    if not candidate_rows:
        candidate_rows = f"<tr><td colspan='5'>{escape(labels['empty'])}</td></tr>"
    manual_rows = "".join(
        "<tr>"
        f"<td>{escape(interval.interpretation_name)}</td>"
        f"<td>{interval.top_depth:.2f}–{interval.bottom_depth:.2f} "
        f"{escape(report.depth_unit)}</td>"
        f"<td>{escape(interval.interval_type)}</td>"
        f"<td>{escape(interval.label)}</td>"
        f"<td>{escape(interval.comment)}</td>"
        "</tr>"
        for interval in report.manual_intervals
    )
    if not manual_rows:
        manual_rows = f"<tr><td colspan='5'>{escape(labels['no_manual'])}</td></tr>"
    warnings = "".join(f"<li>{escape(item)}</li>" for item in report.warnings)
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
html, body {{ background: #ffffff; color: #172033; }}
body {{ font-family: Arial, sans-serif; font-size: 10pt; }}
h1 {{ font-size: 18pt; }} h2 {{ margin-top: 18px; font-size: 13pt; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ border: 1px solid #8290a3; padding: 5px; vertical-align: top;
          color: #172033; }}
th {{ background: #dce8f4; color: #10243a; }}
td {{ background: #ffffff; }}
small {{ color: #44566c; }}
.notice {{ color: #3d3300; background: #fff7d6;
           border-left: 4px solid #d59b00; padding: 8px 12px; }}
</style></head><body>
<h1>{escape(labels['title'])}</h1>
<p><b>{escape(labels['project'])}:</b> {escape(report.project_name)}<br>
<b>{escape(labels['well'])}:</b> {escape(report.well_name)}<br>
<b>{escape(labels['dataset'])}:</b> {escape(report.dataset_name)}<br>
<b>{escape(labels['created'])}:</b> {escape(report.generated_at)}<br>
<b>{escape(labels['primary'])}:</b> {escape(report.primary_mnemonic or '—')}<br>
<b>{escape(labels['threshold'])}:</b> {report.threshold:.2f}</p>
<h2>{escape(labels['methods'])}</h2>
<table><thead><tr><th>{escape(labels['method'])}</th><th>{escape(labels['curves'])}</th>
<th>{escape(labels['source'])}</th></tr></thead><tbody>{method_rows}</tbody></table>
<h2>{escape(labels['candidates'])}</h2>
<table><thead><tr><th>{escape(labels['interval'])}</th><th>{escape(labels['strength'])}</th>
<th>{escape(labels['hypothesis'])}</th><th>{escape(labels['samples'])}</th>
<th>{escape(labels['evidence'])}</th></tr></thead>
<tbody>{candidate_rows}</tbody></table>
<h2>{escape(labels['manual'])}</h2>
<table><thead><tr><th>{escape(labels['interpretation'])}</th>
<th>{escape(labels['interval'])}</th><th>{escape(labels['type'])}</th>
<th>{escape(labels['label'])}</th><th>{escape(labels['comment'])}</th></tr></thead>
<tbody>{manual_rows}</tbody></table>
<div class="notice"><h2>{escape(labels['warnings'])}</h2><ul>{warnings}</ul></div>
</body></html>"""


def fluid_hypothesis_label(
    candidate: HydrocarbonCandidateInterval,
    language: AppLanguage = AppLanguage.RU,
) -> str:
    labels = _HTML_LABELS[language]
    return labels[f"hypothesis_{candidate.fluid_hypothesis}"]


def fluid_hypothesis_basis(
    candidate: HydrocarbonCandidateInterval,
    language: AppLanguage = AppLanguage.RU,
) -> str:
    labels = _HTML_LABELS[language]
    if (
        candidate.interval_wetness is None
        or candidate.background_wetness is None
    ):
        return labels["wetness_insufficient"]
    if candidate.wetness_robust_z is None:
        return labels["wetness_no_scale"].format(
            interval=candidate.interval_wetness,
            background=candidate.background_wetness,
        )
    return labels["wetness_basis"].format(
        interval=candidate.interval_wetness,
        background=candidate.background_wetness,
        robust_z=candidate.wetness_robust_z,
    )
