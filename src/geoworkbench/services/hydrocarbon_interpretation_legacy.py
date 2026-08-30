from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape

import numpy as np

from geoworkbench.domain.models import CuttingsSample, Dataset
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.gas_ratio_interpretation import (
    PixlerAssessment,
    classify_gas_ratio,
    classify_pixler_ratios,
)
from geoworkbench.services.las_parameter_resolver import (
    DatasetParameterResolution,
    LasParameterResolver,
    ParameterResolutionError,
    resolve_gas_ratio_inputs,
)
from geoworkbench.services.lba_standard import (
    LbaStandardAssessment,
    assess_lba_standard,
    describe_lba_assessment,
)
from geoworkbench.services.localization import AppLanguage


@dataclass(frozen=True, slots=True)
class InterpretationMethodStatus:
    method: str
    curve_mnemonics: tuple[str, ...]
    available_mnemonics: tuple[str, ...]
    source: str
    calculation: str = ""

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
    interval_balance: float | None
    interval_character: float | None
    pixler_assessment: PixlerAssessment | None
    lba_assessments: tuple[LbaStandardAssessment, ...]
    gas_lba_correlation: str
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
class OpusGasomerIndicatorReport:
    mnemonic: str
    formula: str
    median_value: float | None
    class_code: int
    class_label: str
    vote_support: float
    available_rows: int
    total_rows: int
    vote_counts: tuple[tuple[int, int], ...]
    state_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class OpusGasomerIntervalReport:
    top_depth: float
    bottom_depth: float
    class_code: int
    class_label: str
    support_fraction: float
    valid_rows: int
    total_rows: int
    background_median: float | None
    peak_total_gas: float | None
    delta_peak: float | None
    max_robust_z: float | None
    max_contrast: float | None
    indicators: tuple[OpusGasomerIndicatorReport, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OpusGasomerReportSection:
    profile_id: str
    profile_version: str
    profile_status: str
    calculation_mode: str
    interval_source: str
    working_unit: str
    total_gas_lod: float | None
    input_curves: tuple[tuple[str, str], ...]
    input_units: tuple[tuple[str, str], ...]
    formulas: tuple[tuple[str, str], ...]
    class_labels: tuple[tuple[int, str], ...]
    source_workbook_sha256: str
    provenance: tuple[str, ...]
    errata: tuple[str, ...]
    intervals: tuple[OpusGasomerIntervalReport, ...]
    warnings: tuple[str, ...]


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
    report_profile: str = "standard"
    opus_gasomer: OpusGasomerReportSection | None = None


@dataclass(frozen=True, slots=True)
class _FluidInterpretationContext:
    wetness: np.ndarray | None
    c1: np.ndarray | None
    c2: np.ndarray | None
    c3: np.ndarray | None
    c4: np.ndarray | None
    c5: np.ndarray | None
    heavier: np.ndarray | None
    total: np.ndarray | None
    background_median: float | None
    background_scale: float | None


_METHODS: tuple[tuple[str, tuple[str, ...], str, str], ...] = (
    (
        "Haworth wetness/balance/character",
        ("WH", "BH", "CH"),
        "Haworth, Sellens & Whittaker (1985), AAPG Bulletin 69(8), 1305–1310.",
        (
            "Wh=100×(C2+C3+ΣC4+ΣC5)/(C1+C2+C3+ΣC4+ΣC5); "
            "Bh=(C1+C2)/(C3+ΣC4+ΣC5); Ch=(ΣC4+ΣC5)/C3. "
            "The fluid label is a preliminary palette-based interpretation."
        ),
    ),
    (
        "Pixler hydrocarbon ratios",
        ("C1_C2", "C1_C3", "C1_C4", "C1_C5"),
        "Pixler (1969), Journal of Petroleum Technology. DOI 10.2118/2254-PA.",
        "C1/C2, C1/C3, C1/ΣC4 and C1/ΣC5; profile shape is supporting evidence, not a standalone productivity proof.",
    ),
    (
        "Drilling-normalized C1–C5 / total gas",
        (
            "C1_NORM",
            "C1_NORM_REF",
            "C2_NORM",
            "C3_NORM",
            "IC4_NORM",
            "NC4_NORM",
            "IC5_NORM",
            "NC5_NORM",
            "TG_NORM",
        ),
        "US20140379265A1, Equation 2; US20150060054A1 reference normalization.",
        "Each component is normalized to explicit reference drilling conditions; source and calculated normalized curves remain separate.",
    ),
    (
        "Jorden–Shirley / Rehm–McClendon d-exponent",
        ("DEXP", "DEXPC", "NCT", "DEXPC_NCT"),
        "Jorden & Shirley (1966), SPE 1407; Rehm & McClendon (1971), SPE 3601.",
        "DEXP is calculated from ROP, RPM, WOB and bit diameter; DEXPC additionally applies the explicitly supplied normal mud density.",
    ),
)

_PRIMARY_GAS_ORDER = (
    "TG_NORM",
    "C1_NORM_REF",
    "C1_NORM",
    "TG_CALC",
    "TG",
    "TGAS",
    "TOTALGAS",
    "TOTAL_GAS",
)
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

    semantic_targets = tuple(
        dict.fromkeys(mnemonic for _, mnemonics, _, _ in _METHODS for mnemonic in mnemonics)
    )
    semantic = LasParameterResolver().resolve_dataset(
        dataset,
        targets=(*semantic_targets, *_PRIMARY_GAS_ORDER),
    )
    methods = tuple(_method_status(dataset, semantic, *spec) for spec in _METHODS)
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

    available_primary_curve_list = []
    seen_primary_curve_ids: set[str] = set()
    for mnemonic in _PRIMARY_GAS_ORDER:
        curve = dataset.curve_by_mnemonic(mnemonic)
        if curve is None and (match := semantic.get(mnemonic)) is not None:
            curve = match.curve
        if curve is None or curve.metadata.curve_id in seen_primary_curve_ids:
            continue
        seen_primary_curve_ids.add(curve.metadata.curve_id)
        available_primary_curve_list.append(curve)
    available_primary_curves = tuple(available_primary_curve_list)
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
            "текущей скважины и применяет стандартную палетку Wh/Bh/Ch "
            "Haworth/DATALOG. ЛБА перекрывающихся проб приводится как отдельное "
            "подтверждение. Категория «вода» по mud-gas не назначается автоматически."
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
    if not methods[2].available:
        warnings.append(
            "Нормализованный газ не рассчитан. Нажмите «Рассчитать стандартные методы» "
            "и проверьте однозначное сопоставление C1–C5, ROP, BIT и FLOW с единицами."
        )
    elif primary is not None and (
        primary.metadata.original_mnemonic in methods[2].available_mnemonics
        and not primary.metadata.provenance.startswith("calculation:")
    ):
        warnings.append(
            f"Нормализованная кривая {primary.metadata.original_mnemonic} получена "
            "из файла/сервера и используется без перезаписи. Проверьте настройки "
            "оператора, формулу, эталонные условия и единицы поставщика."
        )
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
        ) = _detect_candidates(
            dataset,
            primary_name,
            threshold,
            lba_samples=tuple(well.cuttings),
        )
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
    semantic: DatasetParameterResolution,
    method: str,
    mnemonics: tuple[str, ...],
    source: str,
    calculation: str,
) -> InterpretationMethodStatus:
    available: list[str] = []
    seen: set[str] = set()
    for mnemonic in mnemonics:
        curve = dataset.curve_by_mnemonic(mnemonic)
        if curve is None and (match := semantic.get(mnemonic)) is not None:
            curve = match.curve
        if curve is None or curve.metadata.curve_id in seen:
            continue
        seen.add(curve.metadata.curve_id)
        available.append(curve.metadata.original_mnemonic)
    return InterpretationMethodStatus(method, mnemonics, tuple(available), source, calculation)


def _detect_candidates(
    dataset: Dataset,
    primary_mnemonic: str,
    threshold: float,
    *,
    lba_samples: tuple[CuttingsSample, ...] = (),
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
        return (
            (),
            median,
            None,
            "Газовая кривая не имеет достаточного разброса для поиска аномалий.",
        )

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
            interval_balance,
            interval_character,
            pixler_assessment,
        ) = _preliminary_fluid_hypothesis(
            context_mask,
            fluid_context,
        )
        lba_assessments = _overlapping_lba_assessments(lba_samples, top, bottom)
        gas_lba_correlation = _gas_lba_correlation(
            fluid_hypothesis,
            lba_assessments,
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
        ]
        if metrics:
            evidence_parts.append(
                "context means: " + ", ".join(f"{name}={value:.6g}" for name, value in metrics)
            )
        for assessment in lba_assessments:
            evidence_parts.append(
                "LBA standard: "
                f"group {assessment.standard.group}, {assessment.standard.code}"
                + (
                    f", intensity {assessment.intensity}"
                    if assessment.intensity is not None
                    else ""
                )
                + (f", colour {assessment.color_code}" if assessment.color_code else "")
            )
        if pixler_assessment is not None:
            evidence_parts.append(
                "Pixler standard: "
                f"{pixler_assessment.code}, "
                f"C1/C2={pixler_assessment.c1_c2:.5f}, "
                f"profile={pixler_assessment.profile_shape or 'insufficient'}"
                + (
                    ", possible water association"
                    if pixler_assessment.water_association_possible
                    else ""
                )
            )
        evidence_parts.append(f"gas/LBA correlation = {gas_lba_correlation}")
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
                interval_balance,
                interval_character,
                pixler_assessment,
                lba_assessments,
                gas_lba_correlation,
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
) -> _FluidInterpretationContext:
    try:
        gases = resolve_gas_ratio_inputs(dataset)
    except (ParameterResolutionError, ValueError):
        return _FluidInterpretationContext(
            None, None, None, None, None, None, None, None, None, None
        )
    c1 = gases["C1"]
    arrays = tuple(gases.values())
    if any(values.shape != c1.shape for values in arrays) or c1.shape != background_mask.shape:
        return _FluidInterpretationContext(
            None, None, None, None, None, None, None, None, None, None
        )

    c4 = _summed_component(gases, "C4", "IC4", "NC4", c1)
    c5 = _summed_component(gases, "C5", "IC5", "NC5", c1)
    heavier = gases["C2"] + gases["C3"] + c4 + c5
    total = c1 + heavier
    wetness = np.full(c1.shape, np.nan, dtype=np.float64)
    valid = np.isfinite(c1) & np.isfinite(heavier) & np.isfinite(total) & (total > 0.0)
    wetness[valid] = 100.0 * heavier[valid] / total[valid]

    background_values = wetness[background_mask & valid]
    if background_values.size < 20:
        return _FluidInterpretationContext(
            wetness,
            c1,
            gases["C2"],
            gases["C3"],
            c4,
            c5,
            heavier,
            total,
            None,
            None,
        )
    background_median, background_scale = _robust_center_scale(background_values)
    return _FluidInterpretationContext(
        wetness,
        c1,
        gases["C2"],
        gases["C3"],
        c4,
        c5,
        heavier,
        total,
        background_median,
        background_scale,
    )


def _preliminary_fluid_hypothesis(
    interval_mask: np.ndarray,
    context: _FluidInterpretationContext,
) -> tuple[
    str,
    float | None,
    float | None,
    float | None,
    float | None,
    float | None,
    PixlerAssessment | None,
]:
    if (
        context.wetness is None
        or context.c1 is None
        or context.c2 is None
        or context.c3 is None
        or context.c4 is None
        or context.c5 is None
        or context.heavier is None
        or context.total is None
    ):
        return "insufficient_data", None, None, None, None, None, None
    valid_interval = (
        interval_mask
        & np.isfinite(context.heavier)
        & np.isfinite(context.total)
        & (context.total > 0.0)
    )
    if not np.any(valid_interval):
        return "insufficient_data", None, None, None, None, None, None
    # Composition is integrated over the candidate interval. A pointwise median
    # incorrectly returned exactly zero when C2-C5 were sparse but non-zero.
    interval_total = float(np.sum(context.total[valid_interval]))
    interval_heavier = float(np.sum(context.heavier[valid_interval]))
    if interval_total <= np.finfo(np.float64).eps:
        return "insufficient_data", None, None, None, None, None, None
    interval_wetness = 100.0 * interval_heavier / interval_total
    c1_sum = float(np.sum(context.c1[valid_interval]))
    c2_sum = float(np.sum(context.c2[valid_interval]))
    c3_sum = float(np.sum(context.c3[valid_interval]))
    c4_sum = float(np.sum(context.c4[valid_interval]))
    c5_sum = float(np.sum(context.c5[valid_interval]))
    balance_denominator = c3_sum + c4_sum + c5_sum
    interval_balance = (
        (c1_sum + c2_sum) / balance_denominator
        if balance_denominator > np.finfo(np.float64).eps
        else None
    )
    interval_character = (c4_sum + c5_sum) / c3_sum if c3_sum > np.finfo(np.float64).eps else None
    pixler_assessment = None
    c1_c2 = c1_sum / c2_sum if c2_sum > np.finfo(np.float64).eps else None
    if c1_c2 is not None:
        pixler_assessment = classify_pixler_ratios(
            c1_c2=c1_c2,
            c1_c3=(c1_sum / c3_sum if c3_sum > np.finfo(np.float64).eps else None),
            c1_c4=(c1_sum / c4_sum if c4_sum > np.finfo(np.float64).eps else None),
            c1_c5=(c1_sum / c5_sum if c5_sum > np.finfo(np.float64).eps else None),
        )
    assessment = classify_gas_ratio(
        wetness=interval_wetness,
        balance=interval_balance,
        character=interval_character,
    )
    if context.background_median is None:
        return (
            assessment.code,
            interval_wetness,
            None,
            None,
            interval_balance,
            interval_character,
            pixler_assessment,
        )
    if context.background_scale is None:
        return (
            assessment.code,
            interval_wetness,
            context.background_median,
            None,
            interval_balance,
            interval_character,
            pixler_assessment,
        )
    relative_z = (interval_wetness - context.background_median) / context.background_scale
    return (
        assessment.code,
        interval_wetness,
        context.background_median,
        float(relative_z),
        interval_balance,
        interval_character,
        pixler_assessment,
    )


def _overlapping_lba_assessments(
    samples: tuple[CuttingsSample, ...],
    top: float,
    bottom: float,
) -> tuple[LbaStandardAssessment, ...]:
    assessments: list[LbaStandardAssessment] = []
    seen: set[tuple[int, int | None, str | None]] = set()
    for sample in samples:
        if sample.top_depth >= bottom or sample.bottom_depth <= top:
            continue
        assessment = assess_lba_standard(
            group=sample.lba_group,
            type_id=sample.lba_type_id,
            color=sample.lba_color,
            intensity=sample.lba_intensity,
        )
        if assessment is None:
            continue
        key = (
            assessment.standard.group,
            assessment.intensity,
            assessment.color_code,
        )
        if key not in seen:
            seen.add(key)
            assessments.append(assessment)
    return tuple(assessments)


def _gas_lba_correlation(
    gas_code: str,
    assessments: tuple[LbaStandardAssessment, ...],
) -> str:
    if not assessments:
        return "gas_only"
    gas_family = (
        "dry_gas"
        if gas_code
        in {
            "very_light_dry_gas",
            "light_dry_gas",
            "productive_gas_increasing_wetness",
            "gas_increasing_wetness",
        }
        else "transition"
        if gas_code
        in {
            "wet_gas_or_gas_condensate",
            "gas_condensate_or_high_api_oil",
            "light_oil_high_gor",
        }
        else "oil"
        if gas_code
        in {
            "productive_oil_decreasing_gravity",
            "poor_low_gravity_oil",
        }
        else "heavy_oil"
        if gas_code == "heavy_or_residual_oil"
        else "unknown"
    )
    group_results: list[str] = []
    for assessment in assessments:
        group = assessment.standard.group
        if gas_family == "dry_gas":
            result = "partial" if group <= 2 else "divergent"
        elif gas_family == "transition":
            result = "concordant" if group <= 3 else "divergent"
        elif gas_family == "oil":
            result = "concordant" if 2 <= group <= 4 else "partial"
        elif gas_family == "heavy_oil":
            result = "concordant" if group >= 4 else "partial" if group == 3 else "divergent"
        else:
            result = "indeterminate"
        group_results.append(result)
    unique = set(group_results)
    if "concordant" in unique and "divergent" in unique:
        return "mixed"
    if "concordant" in unique:
        return "concordant"
    if "divergent" in unique and "partial" in unique:
        return "mixed"
    if "divergent" in unique:
        return "divergent"
    if "partial" in unique:
        return "partial"
    return "indeterminate"


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
            metrics.append((mnemonic, float(np.mean(values[finite]))))
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
        "curves": "Использованные данные",
        "source": "Источник",
        "calculation": "Расчёт и правило интерпретации",
        "candidates": "Кандидатные интервалы УВ-проявлений",
        "interval": "Интервал",
        "strength": "Относительная сила аномалии",
        "absolute_gas": "Абсолютный газ: мин / среднее / макс",
        "evidence": "Основание",
        "hypothesis": "Предварительная интерпретация",
        "details": "Интерпретация по интервалам",
        "manual": "Интервалы, подтверждённые геологом",
        "interpretation": "Интерпретация",
        "type": "Тип",
        "label": "Подпись",
        "comment": "Комментарий",
        "warnings": "Ограничения методики",
        "empty": "Кандидатные интервалы по выбранному порогу не найдены.",
        "no_manual": "Подтверждённые геологом интервалы пока не заполнены.",
        "hypothesis_probable_gas": "вероятный газ",
        "hypothesis_probable_liquid_hydrocarbons": ("вероятные жидкие УВ (нефть/конденсат)"),
        "hypothesis_indeterminate": "УВ-проявление смешанного/неопределённого типа",
        "hypothesis_insufficient_data": (
            "газовое УВ-проявление; C1–C5 недостаточно для определения типа"
        ),
        "hypothesis_very_light_dry_gas": ("очень лёгкий сухой газ; возможно непродуктивный"),
        "hypothesis_light_dry_gas": "возможный лёгкий сухой газ",
        "hypothesis_productive_gas_increasing_wetness": (
            "газовая залежь с увеличением содержания тяжёлых УВ"
        ),
        "hypothesis_gas_increasing_wetness": ("газ с увеличением содержания тяжёлых УВ"),
        "hypothesis_wet_gas_or_gas_condensate": (
            "продуктивная газовая фаза: влажный газ или газоконденсат"
        ),
        "hypothesis_light_oil_high_gor": ("лёгкая нефть с высоким газовым фактором"),
        "hypothesis_gas_condensate_or_high_api_oil": (
            "газоконденсат или лёгкая нефть с высоким API/GOR"
        ),
        "hypothesis_productive_oil_decreasing_gravity": (
            "нефтяная залежь с увеличением плотности нефти"
        ),
        "hypothesis_poor_low_gravity_oil": ("бедная тяжёлая нефть с низким газосодержанием"),
        "hypothesis_heavy_or_residual_oil": (
            "тяжёлая или остаточная нефть; возможна непродуктивная зона"
        ),
        "hypothesis_opus_oxidized_residual_oil": (
            "УВ-газопроявление; ОПУС предварительно: окисленная (остаточная) нефть"
        ),
        "hypothesis_opus_oil": "УВ-газопроявление; ОПУС предварительно: нефть",
        "hypothesis_opus_combustible_gas": (
            "УВ-газопроявление; ОПУС предварительно: горючий газ"
        ),
        "hypothesis_opus_water_dissolved_gas": (
            "УВ-газопроявление; ОПУС предварительно: газ в воде/у контакта"
        ),
        "hypothesis_opus_gas_condensate": "ОПУС: газоконденсат",
        "hypothesis_opus_gassy_oil": "ОПУС: газированная нефть",
        "hypothesis_opus_gas_condensate_or_gassy_oil": (
            "УВ-газопроявление; ОПУС предварительно: газоконденсатная или "
            "газонефтяная залежь"
        ),
        "hypothesis_opus_no_consensus": (
            "УВ-газопроявление; ОПУС: тип флюида не определён по опубликованным диапазонам"
        ),
        "hypothesis_opus_gasomer_oxidized_residual_oil": (
            "УВ-проявление; ОПУС Газомер: класс 1 — окисленная (остаточная) нефть"
        ),
        "hypothesis_opus_gasomer_oil": (
            "УВ-проявление; ОПУС Газомер: класс 2 — нефть"
        ),
        "hypothesis_opus_gasomer_combustible_gas": (
            "УВ-проявление; ОПУС Газомер: класс 3 — горючий газ"
        ),
        "hypothesis_opus_gasomer_water_dissolved_gas": (
            "УВ-проявление; ОПУС Газомер: класс 4 — водорастворённый газ"
        ),
        "hypothesis_opus_gasomer_gas_condensate": (
            "УВ-проявление; ОПУС Газомер: класс 5 — газоконденсат"
        ),
        "hypothesis_opus_gasomer_gassy_oil": (
            "УВ-проявление; ОПУС Газомер: класс 6 — газированная нефть"
        ),
        "hypothesis_opus_gasomer_undefined": (
            "УВ-проявление; ОПУС Газомер: класс 7 — расчётный тип не определён; "
            "точная причина указана в доказательствах"
        ),
        "opus_fallback_prefix": (
            "УВ-проявление; резерв Haworth/Pixler: {label} (ОПУС неоднозначен)"
        ),
        "wetness_basis": (
            "Средняя относительная доля C2–C5 в интервале {interval:.5f}%; "
            "относительное отклонение robust z={robust_z:.5f}."
        ),
        "wetness_no_scale": (
            "Средняя относительная доля C2–C5 в интервале {interval:.5f}%; "
            "устойчивость сравнения вне интервала недостаточна."
        ),
        "wetness_insufficient": (
            "Для интерпретации нужны согласованные C1–C5 и достаточное число корректных отсчётов вне интервала."
        ),
        "ratio_basis": "Палетка Haworth/DATALOG: Wh={wh}, Bh={bh}, Ch={ch}.",
        "phase_productive_gas_phase": "Ch подтверждает продуктивную газовую фазу.",
        "phase_productive_liquid_phase": ("Ch подтверждает жидкую фазу или лёгкую нефть."),
        "phase_phase_boundary": "Ch находится на границе 0,5.",
        "pixler_basis": ("Pixler: {label}; C1/C2={c1_c2}, профиль {shape}{water}."),
        "pixler_nonproductive_residual_or_very_heavy_oil": (
            "остаточная или очень тяжёлая непродуктивная нефть"
        ),
        "pixler_low_api_oil": "тяжёлая нефть с низким API",
        "pixler_medium_api_oil": "нефть средней плотности",
        "pixler_high_api_light_oil": "лёгкая нефть с высоким API",
        "pixler_light_oil_or_gas_condensate": ("переходная зона: лёгкая нефть или газоконденсат"),
        "pixler_gas_or_gas_condensate": "газ или газоконденсат",
        "pixler_gas": "газ",
        "pixler_very_light_methane_rich_gas": (
            "очень лёгкий метановый газ; возможна непродуктивность"
        ),
        "shape_positive": "положительный",
        "shape_negative": "отрицательный",
        "shape_mixed": "смешанный",
        "shape_insufficient": "недостаточно точек",
        "possible_water": "; возможно влияние пластовой воды",
        "lba_basis": "ЛБА: {description}.",
        "correlation_gas_only": "Сопоставление: имеются только газовые данные.",
        "correlation_concordant": ("Сопоставление газа и ЛБА: признаки согласуются."),
        "correlation_partial": (
            "Сопоставление газа и ЛБА: частичное согласие, нужна проверка геологом."
        ),
        "correlation_divergent": ("Сопоставление газа и ЛБА: признаки расходятся."),
        "correlation_mixed": (
            "Сопоставление газа и ЛБА: одновременно согласующиеся и расходящиеся признаки."
        ),
        "correlation_indeterminate": (
            "Сопоставление газа и ЛБА: данных недостаточно для оценки согласованности."
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
        "curves": "Пайдаланылған деректер",
        "source": "Дереккөз",
        "calculation": "Есептеу және интерпретация ережесі",
        "candidates": "Көмірсутек көріністерінің кандидат аралықтары",
        "interval": "Аралық",
        "strength": "Аномалияның салыстырмалы күші",
        "absolute_gas": "Абсолюттік газ: ең аз / орташа / ең көп",
        "evidence": "Негіз",
        "hypothesis": "Алдын ала интерпретация",
        "details": "Аралықтар бойынша интерпретация",
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
        "hypothesis_very_light_dry_gas": ("өте жеңіл құрғақ газ; өнімсіз болуы мүмкін"),
        "hypothesis_light_dry_gas": "ықтимал жеңіл құрғақ газ",
        "hypothesis_productive_gas_increasing_wetness": (
            "ауыр көмірсутектер мөлшері артатын газ шоғыры"
        ),
        "hypothesis_gas_increasing_wetness": ("ауыр көмірсутектер мөлшері артатын газ"),
        "hypothesis_wet_gas_or_gas_condensate": (
            "өнімді газ фазасы: ылғалды газ немесе газ конденсаты"
        ),
        "hypothesis_light_oil_high_gor": "газ факторы жоғары жеңіл мұнай",
        "hypothesis_gas_condensate_or_high_api_oil": (
            "газ конденсаты немесе API/GOR жоғары жеңіл мұнай"
        ),
        "hypothesis_productive_oil_decreasing_gravity": ("мұнай тығыздығы артатын мұнай шоғыры"),
        "hypothesis_poor_low_gravity_oil": ("газ мөлшері аз ауыр мұнай шоғыры"),
        "hypothesis_heavy_or_residual_oil": (
            "ауыр немесе қалдық мұнай; өнімсіз аймақ болуы мүмкін"
        ),
        "hypothesis_opus_oxidized_residual_oil": (
            "КС газ көрінісі; ОПУС алдын ала: тотыққан (қалдық) мұнай"
        ),
        "hypothesis_opus_oil": "КС газ көрінісі; ОПУС алдын ала: мұнай",
        "hypothesis_opus_combustible_gas": (
            "КС газ көрінісі; ОПУС алдын ала: жанғыш газ"
        ),
        "hypothesis_opus_water_dissolved_gas": (
            "КС газ көрінісі; ОПУС алдын ала: судағы/жанасудағы газ"
        ),
        "hypothesis_opus_gas_condensate": "ОПУС: газ конденсаты",
        "hypothesis_opus_gassy_oil": "ОПУС: газдалған мұнай",
        "hypothesis_opus_gas_condensate_or_gassy_oil": (
            "КС газ көрінісі; ОПУС алдын ала: газ-конденсатты немесе "
            "газ-мұнайлы шоғыр"
        ),
        "hypothesis_opus_no_consensus": (
            "КС газ көрінісі; ОПУС: флюид түрі жарияланған диапазондар бойынша анықталмады"
        ),
        "hypothesis_opus_gasomer_oxidized_residual_oil": (
            "КС көрінісі; ОПУС Газомер: 1-класс — тотыққан (қалдық) мұнай"
        ),
        "hypothesis_opus_gasomer_oil": "КС көрінісі; ОПУС Газомер: 2-класс — мұнай",
        "hypothesis_opus_gasomer_combustible_gas": (
            "КС көрінісі; ОПУС Газомер: 3-класс — жанғыш газ"
        ),
        "hypothesis_opus_gasomer_water_dissolved_gas": (
            "КС көрінісі; ОПУС Газомер: 4-класс — суда еріген газ"
        ),
        "hypothesis_opus_gasomer_gas_condensate": (
            "КС көрінісі; ОПУС Газомер: 5-класс — газ конденсаты"
        ),
        "hypothesis_opus_gasomer_gassy_oil": (
            "КС көрінісі; ОПУС Газомер: 6-класс — газдалған мұнай"
        ),
        "hypothesis_opus_gasomer_undefined": (
            "КС көрінісі; ОПУС Газомер: 7-класс — есептік түр анықталмады; "
            "нақты себеп дәлелдерде көрсетілген"
        ),
        "opus_fallback_prefix": (
            "КС көрінісі; Haworth/Pixler резерві: {label} (ОПУС бірмәнді емес)"
        ),
        "wetness_basis": (
            "Аралықтағы C2–C5 орташа салыстырмалы үлесі {interval:.5f}%; "
            "салыстырмалы ауытқу robust z={robust_z:.5f}."
        ),
        "wetness_no_scale": (
            "Аралықтағы C2–C5 орташа салыстырмалы үлесі {interval:.5f}%; "
            "аралықтан тыс салыстыру тұрақтылығы жеткіліксіз."
        ),
        "wetness_insufficient": (
            "Интерпретация үшін үйлесімді C1–C5 және аралықтан тыс жеткілікті дұрыс есеп қажет."
        ),
        "ratio_basis": "Haworth/DATALOG палеткасы: Wh={wh}, Bh={bh}, Ch={ch}.",
        "phase_productive_gas_phase": "Ch өнімді газ фазасын растайды.",
        "phase_productive_liquid_phase": ("Ch сұйық фазаны немесе жеңіл мұнайды растайды."),
        "phase_phase_boundary": "Ch 0,5 шекарасында.",
        "pixler_basis": ("Pixler: {label}; C1/C2={c1_c2}, профиль {shape}{water}."),
        "pixler_nonproductive_residual_or_very_heavy_oil": ("қалдық немесе өте ауыр өнімсіз мұнай"),
        "pixler_low_api_oil": "API төмен ауыр мұнай",
        "pixler_medium_api_oil": "орташа тығыздықтағы мұнай",
        "pixler_high_api_light_oil": "API жоғары жеңіл мұнай",
        "pixler_light_oil_or_gas_condensate": ("өтпелі аймақ: жеңіл мұнай немесе газ конденсаты"),
        "pixler_gas_or_gas_condensate": "газ немесе газ конденсаты",
        "pixler_gas": "газ",
        "pixler_very_light_methane_rich_gas": ("өте жеңіл метанды газ; өнімсіз болуы мүмкін"),
        "shape_positive": "оң",
        "shape_negative": "теріс",
        "shape_mixed": "аралас",
        "shape_insufficient": "нүктелер жеткіліксіз",
        "possible_water": "; қабат суының ықпалы болуы мүмкін",
        "lba_basis": "ЛБА: {description}.",
        "correlation_gas_only": "Салыстыру: тек газ деректері бар.",
        "correlation_concordant": "Газ және ЛБА белгілері сәйкес келеді.",
        "correlation_partial": ("Газ және ЛБА белгілері ішінара сәйкес; геолог тексеруі қажет."),
        "correlation_divergent": "Газ және ЛБА белгілері сәйкес емес.",
        "correlation_mixed": ("Газ және ЛБА салыстыруында сәйкес те, қайшы да белгілер бар."),
        "correlation_indeterminate": ("Газ және ЛБА сәйкестігін бағалау үшін дерек жеткіліксіз."),
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
        "curves": "Data used",
        "source": "Source",
        "calculation": "Calculation and interpretation rule",
        "candidates": "Candidate hydrocarbon-show intervals",
        "interval": "Interval",
        "strength": "Relative anomaly strength",
        "absolute_gas": "Absolute gas: min / mean / max",
        "evidence": "Evidence",
        "hypothesis": "Preliminary interpretation",
        "details": "Interpretation by interval",
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
        "hypothesis_very_light_dry_gas": ("very light dry gas; possibly non-productive"),
        "hypothesis_light_dry_gas": "possible light dry gas",
        "hypothesis_productive_gas_increasing_wetness": (
            "gas accumulation with increasing heavy-hydrocarbon content"
        ),
        "hypothesis_gas_increasing_wetness": ("gas with increasing heavy-hydrocarbon content"),
        "hypothesis_wet_gas_or_gas_condensate": ("productive gas phase: wet gas or gas condensate"),
        "hypothesis_light_oil_high_gor": "light oil with high GOR",
        "hypothesis_gas_condensate_or_high_api_oil": (
            "gas condensate or high-API/high-GOR light oil"
        ),
        "hypothesis_productive_oil_decreasing_gravity": (
            "oil accumulation with increasing oil density"
        ),
        "hypothesis_poor_low_gravity_oil": ("poor low-gravity oil with low gas content"),
        "hypothesis_heavy_or_residual_oil": ("heavy or residual oil; possibly non-productive"),
        "hypothesis_opus_oxidized_residual_oil": (
            "HC gas show; preliminary OPUS: oxidized (residual) oil"
        ),
        "hypothesis_opus_oil": "HC gas show; preliminary OPUS: oil",
        "hypothesis_opus_combustible_gas": (
            "HC gas show; preliminary OPUS: combustible gas"
        ),
        "hypothesis_opus_water_dissolved_gas": (
            "HC gas show; preliminary OPUS: gas in/contacting water"
        ),
        "hypothesis_opus_gas_condensate": "OPUS: gas condensate",
        "hypothesis_opus_gassy_oil": "OPUS: gassy oil",
        "hypothesis_opus_gas_condensate_or_gassy_oil": (
            "HC gas show; preliminary OPUS: gas-condensate or gas-oil "
            "accumulation"
        ),
        "hypothesis_opus_no_consensus": (
            "HC gas show; OPUS fluid type is indeterminate from the published ranges"
        ),
        "hypothesis_opus_gasomer_oxidized_residual_oil": (
            "HC show; OPUS Gasomer: class 1 — oxidized (residual) oil"
        ),
        "hypothesis_opus_gasomer_oil": "HC show; OPUS Gasomer: class 2 — oil",
        "hypothesis_opus_gasomer_combustible_gas": (
            "HC show; OPUS Gasomer: class 3 — combustible gas"
        ),
        "hypothesis_opus_gasomer_water_dissolved_gas": (
            "HC show; OPUS Gasomer: class 4 — water-dissolved gas"
        ),
        "hypothesis_opus_gasomer_gas_condensate": (
            "HC show; OPUS Gasomer: class 5 — gas condensate"
        ),
        "hypothesis_opus_gasomer_gassy_oil": (
            "HC show; OPUS Gasomer: class 6 — gassy oil"
        ),
        "hypothesis_opus_gasomer_undefined": (
            "HC show; OPUS Gasomer: class 7 — calculated type undefined; "
            "the exact reason is listed in evidence"
        ),
        "opus_fallback_prefix": (
            "HC show; Haworth/Pixler fallback: {label} (OPUS ambiguous)"
        ),
        "wetness_basis": (
            "Mean relative C2–C5 share in the interval is {interval:.5f}%; "
            "relative deviation robust z={robust_z:.5f}."
        ),
        "wetness_no_scale": (
            "Mean relative C2–C5 share in the interval is {interval:.5f}%; "
            "comparison outside the interval is not robust enough."
        ),
        "wetness_insufficient": (
            "Interpretation requires consistent C1–C5 and enough valid samples outside the interval."
        ),
        "ratio_basis": "Haworth/DATALOG palette: Wh={wh}, Bh={bh}, Ch={ch}.",
        "phase_productive_gas_phase": "Ch supports a productive gas phase.",
        "phase_productive_liquid_phase": ("Ch supports a liquid phase or light oil."),
        "phase_phase_boundary": "Ch is on the 0.5 boundary.",
        "pixler_basis": ("Pixler: {label}; C1/C2={c1_c2}, {shape} profile{water}."),
        "pixler_nonproductive_residual_or_very_heavy_oil": (
            "residual or very heavy non-productive oil"
        ),
        "pixler_low_api_oil": "low-API heavy oil",
        "pixler_medium_api_oil": "medium-density oil",
        "pixler_high_api_light_oil": "high-API light oil",
        "pixler_light_oil_or_gas_condensate": ("transition: light oil or gas condensate"),
        "pixler_gas_or_gas_condensate": "gas or gas condensate",
        "pixler_gas": "gas",
        "pixler_very_light_methane_rich_gas": (
            "very light methane-rich gas; possibly non-productive"
        ),
        "shape_positive": "positive",
        "shape_negative": "negative",
        "shape_mixed": "mixed",
        "shape_insufficient": "insufficient-point",
        "possible_water": "; possible formation-water influence",
        "lba_basis": "LBA: {description}.",
        "correlation_gas_only": "Correlation: gas data only.",
        "correlation_concordant": "Gas and LBA evidence is concordant.",
        "correlation_partial": (
            "Gas and LBA evidence is partly concordant; geologist review is required."
        ),
        "correlation_divergent": "Gas and LBA evidence is divergent.",
        "correlation_mixed": (
            "Gas and LBA comparison contains both concordant and divergent evidence."
        ),
        "correlation_indeterminate": (
            "Gas/LBA concordance cannot be assessed from the available data."
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
        f"<td>{escape(method.calculation or '—')}</td>"
        f"<td>{escape(method.source)}</td>"
        "</tr>"
        for method in report.methods
    )
    candidate_rows = "".join(
        "<tr>"
        f"<td>{candidate.top_depth:.2f}-{candidate.bottom_depth:.2f} "
        f"{escape(report.depth_unit)}</td>"
        f"<td>{escape(labels[candidate.anomaly_strength])}</td>"
        f"<td>{escape(fluid_hypothesis_label(candidate, language))}</td>"
        f"<td data-absolute-gas='{index}'>—</td>"
        f"<td>{escape(candidate_evidence_summary(candidate))}</td>"
        "</tr>"
        for index, candidate in enumerate(report.candidates)
    )
    if not candidate_rows:
        candidate_rows = f"<tr><td colspan='5'>{escape(labels['empty'])}</td></tr>"
    if report.report_profile == "opus":
        candidate_details = "".join(
            "<div class='candidate-detail-heading'>"
            f"<b>{candidate.top_depth:.2f}-{candidate.bottom_depth:.2f} "
            f"{escape(report.depth_unit)} - "
            f"{escape(fluid_hypothesis_label(candidate, language))}</b>"
            "</div>"
            "<div class='candidate-detail-basis'>"
            f"<p>{escape(fluid_hypothesis_basis(candidate, language))}</p>"
            "</div>"
            for candidate in report.candidates
        )
    else:
        candidate_details = "".join(
            "<div class='candidate-detail'>"
            f"<b>{candidate.top_depth:.2f}-{candidate.bottom_depth:.2f} "
            f"{escape(report.depth_unit)} - "
            f"{escape(fluid_hypothesis_label(candidate, language))}</b>"
            f"<p>{escape(fluid_hypothesis_basis(candidate, language))}</p>"
            "</div>"
            for candidate in report.candidates
        )
    manual_rows = "".join(
        "<tr>"
        f"<td>{escape(interval.interpretation_name)}</td>"
        f"<td>{interval.top_depth:.2f}-{interval.bottom_depth:.2f} "
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
body {{ font-size: 10pt; }}
h1 {{ font-size: 18pt; }} h2 {{ margin-top: 18px; font-size: 13pt; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ border: 1px solid #8290a3; padding: 5px; vertical-align: top;
          color: #172033; }}
tr {{ page-break-inside: avoid; break-inside: avoid; }}
th {{ background: #dce8f4; color: #10243a; }}
td {{ background: #ffffff; }}
small {{ color: #44566c; }}
.candidate-detail {{ border: 1px solid #8290a3; border-left: 4px solid #315a7d;
                     padding: 7px 10px; margin: 7px 0; page-break-inside: avoid;
                     font-size: 9pt; }}
.candidate-detail p {{ color: #44566c; margin: 4px 0 0 0; }}
.candidate-detail-heading {{ border-left: 4px solid #315a7d; padding: 5px 10px 2px 10px;
                             margin: 7px 0 0 0; page-break-inside: avoid; }}
.candidate-detail-basis {{ border-left: 4px solid #315a7d; padding: 0 10px 6px 10px;
                           margin: 0 0 7px 0; page-break-inside: avoid; }}
.candidate-detail-basis p {{ color: #44566c; margin: 0; }}
.notice {{ color: #3d3300; background: #fff7d6;
           border-left: 4px solid #d59b00; padding: 8px 12px; }}
.interpretation-curves {{ width: 100%; text-align: center; margin: 0 auto 14px auto; }}
.interpretation-curves img {{ display: block; max-width: 100%; height: auto; margin: 0 auto; }}
</style></head><body>
<h1>{escape(labels["title"])}</h1>
<p><b>{escape(labels["project"])}:</b> {escape(report.project_name)}<br>
<b>{escape(labels["well"])}:</b> {escape(report.well_name)}<br>
<b>{escape(labels["dataset"])}:</b> {escape(report.dataset_name)}<br>
<b>{escape(labels["created"])}:</b> {escape(report.generated_at)}<br>
<b>{escape(labels["primary"])}:</b> {escape(report.primary_mnemonic or "—")}<br>
<b>{escape(labels["threshold"])}:</b> {report.threshold:.2f}</p>
<h2>{escape(labels["methods"])}</h2>
<table><thead><tr><th>{escape(labels["method"])}</th><th>{escape(labels["curves"])}</th>
<th>{escape(labels["calculation"])}</th><th>{escape(labels["source"])}</th></tr></thead>
<tbody>{method_rows}</tbody></table>
<h2>{escape(labels["candidates"])}</h2>
<table><colgroup><col style="width:14%"><col style="width:13%">
<col style="width:36%"><col style="width:10%"><col style="width:27%"></colgroup>
<thead><tr><th>{escape(labels["interval"])}</th><th>{escape(labels["strength"])}</th>
<th>{escape(labels["hypothesis"])}</th><th>{escape(labels["absolute_gas"])}</th>
<th>{escape(labels["evidence"])}</th></tr></thead>
<tbody>{candidate_rows}</tbody></table>
<h2>{escape(labels["details"])}</h2>
{candidate_details or f"<p>{escape(labels['empty'])}</p>"}
<h2>{escape(labels["manual"])}</h2>
<table><thead><tr><th>{escape(labels["interpretation"])}</th>
<th>{escape(labels["interval"])}</th><th>{escape(labels["type"])}</th>
<th>{escape(labels["label"])}</th><th>{escape(labels["comment"])}</th></tr></thead>
<tbody>{manual_rows}</tbody></table>
<div class="notice"><h2>{escape(labels["warnings"])}</h2><ul>{warnings}</ul></div>
</body></html>"""


def fluid_hypothesis_label(
    candidate: HydrocarbonCandidateInterval,
    language: AppLanguage = AppLanguage.RU,
) -> str:
    labels = _HTML_LABELS[language]
    fallback_prefix = "opus_fallback__"
    if candidate.fluid_hypothesis.startswith(fallback_prefix):
        fallback_key = candidate.fluid_hypothesis[len(fallback_prefix) :]
        fallback_label = labels.get(
            f"hypothesis_{fallback_key}",
            labels["hypothesis_indeterminate"],
        )
        return labels["opus_fallback_prefix"].format(label=fallback_label)
    return labels.get(
        f"hypothesis_{candidate.fluid_hypothesis}",
        labels["hypothesis_indeterminate"],
    )


def fluid_hypothesis_basis(
    candidate: HydrocarbonCandidateInterval,
    language: AppLanguage = AppLanguage.RU,
) -> str:
    labels = _HTML_LABELS[language]
    parts: list[str] = []
    if candidate.interval_wetness is None or candidate.background_wetness is None:
        parts.append(labels["wetness_insufficient"])
    elif candidate.wetness_robust_z is None:
        parts.append(
            labels["wetness_no_scale"].format(
                interval=candidate.interval_wetness,
            )
        )
    else:
        parts.append(
            labels["wetness_basis"].format(
                interval=candidate.interval_wetness,
                robust_z=candidate.wetness_robust_z,
            )
        )
    if candidate.interval_wetness is not None:
        parts.append(
            labels["ratio_basis"].format(
                wh=_format_optional(candidate.interval_wetness),
                bh=_format_optional(candidate.interval_balance),
                ch=_format_optional(candidate.interval_character),
            )
        )
    if candidate.interval_character is not None:
        phase_code = (
            "productive_gas_phase"
            if candidate.interval_character < 0.5
            else "productive_liquid_phase"
            if candidate.interval_character > 0.5
            else "phase_boundary"
        )
        parts.append(labels[f"phase_{phase_code}"])
    if candidate.pixler_assessment is not None:
        pixler = candidate.pixler_assessment
        shape = pixler.profile_shape or "insufficient"
        parts.append(
            labels["pixler_basis"].format(
                label=labels[f"pixler_{pixler.code}"],
                c1_c2=_format_optional(pixler.c1_c2),
                shape=labels[f"shape_{shape}"],
                water=labels["possible_water"] if pixler.water_association_possible else "",
            )
        )
    parts.extend(
        labels["lba_basis"].format(description=describe_lba_assessment(assessment, language))
        for assessment in candidate.lba_assessments
    )
    parts.append(labels[f"correlation_{candidate.gas_lba_correlation}"])
    return " ".join(parts)


def candidate_evidence_summary(candidate: HydrocarbonCandidateInterval) -> str:
    """Keep the printable evidence column compact; detailed evidence stays in XLSX."""

    return "; ".join(
        item
        for item in candidate.evidence
        if not item.startswith(
            ("LBA standard:", "Pixler standard:", "gas/LBA correlation", "flagged samples =")
        )
    )


def _format_optional(value: float | None) -> str:
    return "—" if value is None else f"{value:.5f}"
