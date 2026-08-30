from __future__ import annotations

from dataclasses import replace
from math import isfinite

import numpy as np

from geoworkbench.calculations.gas_ratio import sum_components
from geoworkbench.calculations.opus_gasomer import (
    OPUS_GASOMER_INDICATORS,
    OPUS_GASOMER_PROFILE_ID,
    OPUS_GASOMER_PROFILE_VERSION,
    aggregate_opus_gasomer_interval,
    calculate_opus_gasomer_batch,
    detect_opus_gasomer_intervals,
    load_opus_gasomer_profile,
)
from geoworkbench.domain.models import Dataset
from geoworkbench.project.session import ProjectSession
from geoworkbench.services import hydrocarbon_interpretation_legacy as legacy
from geoworkbench.services.hydrocarbon_interpretation_legacy import (
    HydrocarbonCandidateInterval,
    HydrocarbonInterpretationReport,
    InterpretationMethodStatus,
    OpusGasomerIndicatorReport,
    OpusGasomerIntervalReport,
    OpusGasomerReportSection,
)
from geoworkbench.services.las_parameter_resolver import (
    LasParameterResolver,
    ParameterResolutionError,
    concentration_scale_to_percent,
    resolve_gas_ratio_inputs,
)


OPUS_CURVES = ("OPUS3", "OPUS4", "OPUS_K1_3", "OPUS_1_5")
OPUS_WORKING_CURVES = (
    "OPUS_TG_PCT",
    "OPUS_C1_PCT",
    "OPUS_C2_PCT",
    "OPUS_C3_PCT",
    "OPUS_C4_PCT",
    "OPUS_C5_PCT",
    "OPUS_P1",
    "OPUS_P2",
    "OPUS_P3",
    "OPUS_P4",
    "OPUS_P5",
)

_OPUS_CLASS_KEYS = {
    0: "opus_no_consensus",
    1: "opus_oxidized_residual_oil",
    2: "opus_oil",
    3: "opus_combustible_gas",
    4: "opus_water_dissolved_gas",
    5: "opus_gas_condensate_or_gassy_oil",
}

# Published ranges overlap.  A label is emitted only when the intersection of
# all available indicator ranges contains one fluid family.
_OPUS_PUBLISHED_BANDS: dict[str, tuple[tuple[float, float, int], ...]] = {
    "OPUS3": (
        (-np.inf, 0.25, 1),
        (0.5, 5.0, 2),
        (7.0, 300.0, 3),
        (2.0, 25.0, 4),
        (2.0, 10.0, 5),
    ),
    "OPUS4": (
        (-np.inf, 0.05, 1),
        (0.08, 0.95, 2),
        (2.0, 30.0, 3),
        (0.9, 6.0, 4),
        (0.7, 2.0, 5),
    ),
    "OPUS_K1_3": (
        (9000.0, np.inf, 1),
        (500.0, 9000.0, 2),
        (0.1, 180.0, 3),
        (100.0, 200.0, 4),
        (160.0, 760.0, 5),
    ),
    "OPUS_1_5": (
        (250000.0, np.inf, 1),
        (700.0, 250000.0, 2),
        (0.0002, 100.0, 3),
        (1.0, 25.0, 4),
        (100.0, 1100.0, 5),
    ),
}


def build_opus_interpretation_report(
    session: ProjectSession,
    *,
    threshold: float = 3.0,
    total_gas_lod: float | None = None,
) -> HydrocarbonInterpretationReport:
    """Build the additional OPUS report without changing the standard report path."""

    base = legacy.build_hydrocarbon_interpretation_report(session, threshold=threshold)
    dataset = session.current_dataset
    well = session.current_well
    if dataset is None or well is None:
        return replace(base, report_profile="opus")

    available = tuple(
        mnemonic
        for mnemonic in (*OPUS_WORKING_CURVES, *OPUS_CURVES)
        if dataset.curve_by_mnemonic(mnemonic) is not None
    )
    methods = (
        InterpretationMethodStatus(
            "OPUS C1-C5 historical screening indicators",
            (*OPUS_WORKING_CURVES, *OPUS_CURVES),
            available,
            (
                "OPUS3/OPUS4: Alekseev (2024), slide 6, open formula cross-check. "
                "OPUS_K1_3/OPUS_1_5 and published bands: Shefer (2023), TPU, "
                "secondary cross-check with bibliography to Lukyanov (1987) and "
                "Lukyanov & Strelchenko (1997). Lukyanov & Zhuzhulin (2022) documents "
                "applicability conditions but does not publish the complete modern formula/bands."
            ),
            (
                "pi=100×Ci/Σ(C1…C5); OPUS3=p1×p2/(p2+p3)²; "
                "OPUS4=p1×p2×p3/(p2+p3+p4)³; OPUS_K1_3=p1×p2×p3/3; "
                "OPUS_1_5=p1×p2×p3×p4×p5/5. Input is converted to vol%; "
                "1 vol%=10,000 ppm."
            ),
        ),
        InterpretationMethodStatus(
            "OPUS Gasomer five-indicator workbook profile",
            ("TG", "C1", "C2", "C3", "C4", "C5", *OPUS_GASOMER_INDICATORS),
            tuple(
                mnemonic
                for mnemonic in ("TG", "C1", "C2", "C3", "C4", "C5")
                if dataset.curve_by_mnemonic(mnemonic) is not None
            ),
            (
                "Газомер.xls, sheet 'отчет по газу', SHA-256 recorded in profile "
                f"{OPUS_GASOMER_PROFILE_ID} v{OPUS_GASOMER_PROFILE_VERSION}. "
                "GM_1/GM_2 have an open industry formula cross-check; GM_3/GM_4 have "
                "a secondary academic cross-check; GM_5, palettes and five-vote MODE "
                "remain workbook-derived pending field validation."
            ),
            (
                "pi=100×Ci/TotalGas; GM_1=p1×p2/(p2+p3)²; "
                "GM_2=p1×p2×p3/(p2+p3+p4)³; GM_3=p1×p2×p3/3; "
                "GM_4=p1×p2×p3×p4×p5/5; "
                "GM_5=(p2×p3×p4×p5/p1)×(p2+p3+p4+p5)×100. "
                "Each valid synchronous row casts five palette votes; only a unique "
                "mode is accepted, otherwise class 7 is reported."
            ),
        ),
        InterpretationMethodStatus(
            "Haworth/Pixler fluid hypothesis (independent supporting evidence)",
            ("WH", "BH", "CH", "C1_C2", "C1_C3", "C1_C4", "C1_C5"),
            tuple(
                mnemonic
                for mnemonic in ("WH", "BH", "CH", "C1_C2", "C1_C3", "C1_C4", "C1_C5")
                if dataset.curve_by_mnemonic(mnemonic) is not None
            ),
            "Haworth et al. (1985); Pixler (1969). Not an OPUS classification.",
            (
                "Independent fallback only when the published OPUS-band intersection is "
                "empty or non-unique; Wh/Bh/Ch and C1/C2…C1/C5 are evaluated separately."
            ),
        ),
        InterpretationMethodStatus(
            "Whole-well show detection and automatic decision cascade",
            ("OPUS_TG_PCT", *OPUS_CURVES),
            tuple(
                mnemonic
                for mnemonic in ("OPUS_TG_PCT", *OPUS_CURVES)
                if dataset.curve_by_mnemonic(mnemonic) is not None
            ),
            (
                "Application screening profile opus-lukyanov-c1-c5-relative-1987-1997 v1.0; "
                "background/contrast conditions from Lukyanov & Zhuzhulin (2022). "
                "This is a documented application algorithm, not a GOST/ISO fluid standard."
            ),
            (
                "Detect OPUS_TG_PCT anomalies by log1p robust-z; classify on threshold-exceeding "
                "rows only; intersect all available published bands; use the unique OPUS class, "
                "otherwise an explicitly labelled Haworth/Pixler fallback, otherwise indeterminate."
            ),
        ),
    )
    warnings = [
        "Это отдельный дополнительный отчёт ОПУС; стандартный расчёт и стандартный отчёт не изменены.",
        (
            "Исходные C1-C5 сохраняются в единицах LAS. Для ОПУС совместимые ppm, ppb, "
            "доли и проценты приводятся к % об.; 1 % об. = 10 000 ppm. Кривые OPUS_P1-P5 "
            "являются относительными процентами от суммы C1-C5, а не показаниями прибора."
        ),
        (
            "Опубликованные диапазоны четырёх показателей ОПУС перекрываются. Подпись "
            "флюида даётся только при единственном пересечении диапазонов всех доступных "
            "показателей; при неоднозначности отчёт автоматически показывает независимую "
            "рабочую гипотезу Haworth/Pixler как резерв и явно отмечает её основу."
        ),
        (
            "ОПУС5 из переданного Integration Kit не участвует в расчёте и классификации: "
            "профиль требует отдельный TotalGas и доменную валидацию, а открытый первичный "
            "источник формулы и порогов не найден."
        ),
        (
            "Промышленная продуктивность, вода и окончательный тип флюида не доказываются "
            "только поверхностным газовым каротажем; нужны ГИС, испытания, лаг, режим "
            "дегазатора, фон и локальная калибровка."
        ),
        (
            "ОПУС в этом отчёте является документированным скрининговым профилем, а не "
            "ГОСТ/ISO-методом определения типа пластового флюида. Степень подтверждения "
            "каждой формулы и библиографическая цепочка приведены в таблице методики."
        ),
    ]
    total = dataset.curve_by_mnemonic("OPUS_TG_PCT")
    if total is None or not all(
        dataset.curve_by_mnemonic(name) is not None for name in OPUS_CURVES
    ):
        warnings.append(
            "Кривые ОПУС ещё не рассчитаны. Выберите отчёт ОПУС и нажмите «Рассчитать ОПУС»."
        )
        gasomer = _build_gasomer_section(
            dataset,
            (),
            total_gas_lod=total_gas_lod,
        )
        return replace(
            base,
            primary_mnemonic=None,
            baseline_median=None,
            robust_scale=None,
            methods=methods,
            candidates=(),
            warnings=tuple(warnings),
            report_profile="opus",
            opus_gasomer=gasomer,
        )

    candidates, detection_median, scale, detection_warning = legacy._detect_candidates(
        dataset,
        "OPUS_TG_PCT",
        threshold,
        lba_samples=tuple(well.cuttings),
    )
    if detection_warning:
        warnings.append(detection_warning)

    raw_background = _raw_background(total.values)
    if raw_background is None:
        warnings.append(
            "Не удалось оценить фон C1-C5 в % об.; интервалы оставлены как кандидаты "
            "газопроявлений без заключения о применимости ОПУС."
        )
    elif raw_background < 0.1:
        warnings.append(
            "Медианный фон C1-C5 по всей скважине ниже 0,1 % об.; условие применимости "
            "классификации ОПУС не выполнено. Найденные газовые аномалии сохранены в "
            "отчёте как перспективные интервалы и не удаляются этим ограничением."
        )
    candidates = tuple(
        _with_opus_evidence(
            dataset,
            candidate,
            raw_background,
            detection_median=detection_median,
            detection_scale=scale,
            detection_threshold=threshold,
        )
        for candidate in candidates
    )

    gasomer = _build_gasomer_section(
        dataset,
        candidates,
        total_gas_lod=total_gas_lod,
    )
    return replace(
        base,
        primary_mnemonic="OPUS_TG_PCT",
        baseline_median=raw_background,
        robust_scale=scale,
        methods=methods,
        candidates=candidates,
        warnings=tuple(dict.fromkeys(warnings)),
        report_profile="opus",
        opus_gasomer=gasomer,
    )


def _with_opus_evidence(
    dataset,
    candidate: HydrocarbonCandidateInterval,
    background: float | None,
    *,
    detection_median: float | None,
    detection_scale: float | None,
    detection_threshold: float,
) -> HydrocarbonCandidateInterval:
    depth = np.asarray(dataset.depth, dtype=np.float64)
    mask = np.isfinite(depth) & (depth >= candidate.top_depth) & (depth <= candidate.bottom_depth)
    classification_mask = mask.copy()
    total_curve = dataset.curve_by_mnemonic("OPUS_TG_PCT")
    if (
        total_curve is not None
        and detection_median is not None
        and detection_scale is not None
        and detection_scale > np.finfo(np.float64).eps
    ):
        total_values = np.asarray(total_curve.values, dtype=np.float64)
        valid_total = np.isfinite(total_values) & (total_values >= 0.0)
        robust_z = np.full(total_values.shape, np.nan, dtype=np.float64)
        robust_z[valid_total] = (
            np.log1p(total_values[valid_total]) - detection_median
        ) / detection_scale
        flagged = mask & valid_total & (robust_z >= detection_threshold)
        if np.any(flagged):
            classification_mask = flagged
    means: list[tuple[str, float]] = []
    medians: dict[str, float] = {}
    for mnemonic in OPUS_CURVES:
        curve = dataset.curve_by_mnemonic(mnemonic)
        if curve is None:
            continue
        values = np.asarray(curve.values, dtype=np.float64)
        valid = classification_mask & np.isfinite(values)
        if np.any(valid):
            means.append((mnemonic, float(np.mean(values[valid]))))
            medians[mnemonic] = float(np.median(values[valid]))
    summary = ", ".join(f"{name}={value:.6g}" for name, value in means)
    median_summary = ", ".join(f"{name}={value:.6g}" for name, value in medians.items())
    evidence = [*candidate.evidence]
    evidence.append(
        "OPUS composition sample: anomaly-threshold rows within the detected interval"
    )
    opus_class, agreement, compatible = _classify_opus_interval(medians)
    band_summary = ", ".join(
        f"{name}->{'/'.join(str(code) for code in codes) or 'outside'}"
        for name, codes in compatible
    )
    evidence.append(
        f"OPUS published-band intersection: class={opus_class}; "
        f"agreement={agreement:.3f}; {band_summary or 'insufficient indicators'}"
    )
    evidence.append(f"independent Haworth/Pixler hypothesis={candidate.fluid_hypothesis}")
    contrast: float | None = None
    if background is None:
        evidence.append("OPUS applicability: background unavailable")
    elif background > np.finfo(np.float64).eps:
        contrast = candidate.max_primary_value / background
        evidence.append(
            f"OPUS whole-well background={background:.6g} %vol; anomaly/background={contrast:.4g}"
        )
    else:
        evidence.append(
            "OPUS whole-well background=0 %vol; finite anomaly/background ratio is undefined"
        )
    applicable = (
        background is not None
        and background >= 0.1
        and contrast is not None
        and np.isfinite(contrast)
        and contrast >= 3.0
    )
    evidence.append(
        "OPUS applicability gates: met"
        if applicable
        else "OPUS applicability gates: not met; gas-show candidate retained"
    )
    if summary:
        evidence.append(f"OPUS interval means: {summary}")
    if median_summary:
        evidence.append(f"OPUS interval medians used for published bands: {median_summary}")
    if opus_class:
        final_hypothesis = _OPUS_CLASS_KEYS[opus_class]
        evidence.append("final automatic interpretation basis=OPUS published-band agreement")
    elif candidate.fluid_hypothesis not in {"indeterminate", "insufficient_data"}:
        final_hypothesis = f"opus_fallback__{candidate.fluid_hypothesis}"
        evidence.append(
            "final automatic interpretation basis=Haworth/Pixler fallback; OPUS ambiguous"
        )
    else:
        final_hypothesis = _OPUS_CLASS_KEYS[0]
        evidence.append("final automatic interpretation basis=insufficient for fluid typing")
    return replace(
        candidate,
        fluid_hypothesis=final_hypothesis,
        metrics=tuple((*candidate.metrics, *means)),
        evidence=tuple(evidence),
    )


def _raw_background(values: np.ndarray) -> float | None:
    samples = np.asarray(values, dtype=np.float64)
    valid = samples[np.isfinite(samples) & (samples >= 0.0)]
    if valid.size == 0:
        return None
    return float(np.median(valid))


def _classify_opus_interval(
    medians: dict[str, float],
) -> tuple[int, float, tuple[tuple[str, tuple[int, ...]], ...]]:
    compatible = tuple(
        (mnemonic, _compatible_opus_classes(mnemonic, value))
        for mnemonic, value in medians.items()
        if np.isfinite(value)
    )
    if len(compatible) < 2:
        return 0, 0.0, compatible
    compatible_sets = [set(codes) for _, codes in compatible]
    intersection = set.intersection(*compatible_sets)
    agreement = sum(bool(codes) for _, codes in compatible) / len(OPUS_CURVES)
    if len(intersection) != 1:
        return 0, agreement, compatible
    return next(iter(intersection)), agreement, compatible


def _compatible_opus_classes(mnemonic: str, value: float) -> tuple[int, ...]:
    bands = _OPUS_PUBLISHED_BANDS.get(mnemonic, ())
    return tuple(sorted(code for lower, upper, code in bands if lower <= value <= upper))


def _build_gasomer_section(
    dataset: Dataset,
    fallback_candidates: tuple[HydrocarbonCandidateInterval, ...],
    *,
    total_gas_lod: float | None,
) -> OpusGasomerReportSection:
    profile = load_opus_gasomer_profile()
    formulas = tuple(
        (name, str(profile["formulas"][name])) for name in OPUS_GASOMER_INDICATORS
    )
    class_labels = tuple(
        (int(code), str(label))
        for code, label in sorted(
            profile["class_labels_ru"].items(),
            key=lambda item: int(item[0]),
        )
    )
    source = profile["source"]
    evidence = profile["source_evidence"]
    provenance = [
        f"Газомер.xls / {source['sheet']}; workbook-derived applied profile",
        str(evidence["historical_primary_reference"]["citation"]),
    ]
    provenance.extend(
        f"{item['title']}: {item['url']}"
        for item in evidence["open_formula_cross_checks"]
    )
    errata = tuple(
        f"{item['id']} ({item['cell']}): {item['source_expression']} → "
        f"{item['corrected_expression']}. {item['reason']}"
        for item in profile["errata"]
    )
    warnings: list[str] = []
    input_curves: tuple[tuple[str, str], ...] = ()
    input_units: tuple[tuple[str, str], ...] = ()
    intervals: tuple[OpusGasomerIntervalReport, ...] = ()
    interval_source = "none"
    calculation_mode = "synchronous-rows"
    lod_percent: float | None = None

    if total_gas_lod is not None and (
        not isfinite(float(total_gas_lod)) or float(total_gas_lod) <= 0.0
    ):
        raise ValueError("LOD TotalGas должен быть конечным положительным числом")

    try:
        (
            inputs_percent,
            input_curves,
            input_units,
            total_source_unit,
        ) = _resolve_gasomer_inputs(dataset)
        total_scale = concentration_scale_to_percent(total_source_unit)
        if total_scale is None:
            raise ValueError(
                "Для независимого TotalGas не указана поддерживаемая единица концентрации"
            )
        if total_gas_lod is not None:
            lod_percent = float(total_gas_lod) * total_scale
        lod: dict[str, float | None] = {
            name: None for name in ("C1", "C2", "C3", "C4", "C5")
        }
        lod["TOTAL_GAS"] = lod_percent
        batch = calculate_opus_gasomer_batch(
            inputs_percent,
            units="%vol",
            lod=lod,
        )
        warnings.extend(batch.warnings)

        detected_by_bounds: dict[
            tuple[float, float],
            tuple[float, float, float, float, float, tuple[str, ...]],
        ] = {}
        if lod_percent is not None:
            detection = detect_opus_gasomer_intervals(
                np.asarray(dataset.depth, dtype=np.float64),
                inputs_percent["TOTAL_GAS"],
                unit="%vol",
                total_gas_lod=lod_percent,
            )
            bounds = tuple(
                (item.top_depth, item.bottom_depth) for item in detection.intervals
            )
            interval_source = "opus-gasomer-local-detector"
            warnings.extend(detection.warnings)
            detected_by_bounds = {
                (item.top_depth, item.bottom_depth): (
                    item.background_median,
                    item.peak_total_gas,
                    item.delta_peak,
                    item.max_robust_z,
                    item.max_contrast,
                    item.warnings,
                )
                for item in detection.intervals
            }
        else:
            bounds = tuple(
                (item.top_depth, item.bottom_depth) for item in fallback_candidates
            )
            interval_source = "existing-opus-report-candidates"
            warnings.append(
                "LOD TotalGas не задан: локальный детектор ОПУС Газомер не запускался; "
                "если в отчёте есть интервалы, пять голосов агрегированы внутри границ "
                "существующего исторического ОПУС."
            )

        interval_reports: list[OpusGasomerIntervalReport] = []
        labels = dict(class_labels)
        for top_depth, bottom_depth in bounds:
            aggregate = aggregate_opus_gasomer_interval(
                np.asarray(dataset.depth, dtype=np.float64),
                batch,
                top_depth=top_depth,
                bottom_depth=bottom_depth,
            )
            detector_values = detected_by_bounds.get((top_depth, bottom_depth))
            indicator_reports = tuple(
                OpusGasomerIndicatorReport(
                    mnemonic=name,
                    formula=dict(formulas)[name],
                    median_value=aggregate.indicator_median_values[name],
                    class_code=aggregate.indicator_class_codes[name],
                    class_label=labels[aggregate.indicator_class_codes[name]],
                    vote_support=aggregate.indicator_vote_support[name],
                    available_rows=aggregate.indicator_available_counts[name],
                    total_rows=aggregate.total_rows,
                    vote_counts=tuple(sorted(aggregate.indicator_vote_counts[name].items())),
                    state_counts=tuple(sorted(aggregate.indicator_state_counts[name].items())),
                )
                for name in OPUS_GASOMER_INDICATORS
            )
            detector_warnings = detector_values[5] if detector_values is not None else ()
            interval_reports.append(
                OpusGasomerIntervalReport(
                    top_depth=aggregate.sample_top_depth,
                    bottom_depth=aggregate.sample_bottom_depth,
                    class_code=aggregate.class_code,
                    class_label=labels[aggregate.class_code],
                    support_fraction=aggregate.support_fraction,
                    valid_rows=aggregate.valid_rows,
                    total_rows=aggregate.total_rows,
                    background_median=(detector_values[0] if detector_values else None),
                    peak_total_gas=(detector_values[1] if detector_values else None),
                    delta_peak=(detector_values[2] if detector_values else None),
                    max_robust_z=(detector_values[3] if detector_values else None),
                    max_contrast=(detector_values[4] if detector_values else None),
                    indicators=indicator_reports,
                    warnings=tuple(dict.fromkeys((*aggregate.warnings, *detector_warnings))),
                )
            )
        intervals = tuple(interval_reports)
    except (KeyError, ParameterResolutionError, ValueError) as exc:
        warnings.append(f"ОПУС Газомер не рассчитан: {exc}")

    warnings.append(
        "Код 4 «Водорастворенный газ» требует независимого подтверждения признаков воды."
    )
    warnings.append(
        "Классы ОПУС Газомер являются предварительным скринингом и не доказывают "
        "промышленную продуктивность или фазовый состав пласта."
    )
    return OpusGasomerReportSection(
        profile_id=OPUS_GASOMER_PROFILE_ID,
        profile_version=OPUS_GASOMER_PROFILE_VERSION,
        profile_status=str(profile["status"]),
        calculation_mode=calculation_mode,
        interval_source=interval_source,
        working_unit=str(profile["input_basis"]["working_unit"]),
        total_gas_lod=lod_percent,
        input_curves=input_curves,
        input_units=input_units,
        formulas=formulas,
        class_labels=class_labels,
        source_workbook_sha256=str(source["sha256"]),
        provenance=tuple(provenance),
        errata=errata,
        intervals=intervals,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _resolve_gasomer_inputs(
    dataset: Dataset,
) -> tuple[
    dict[str, np.ndarray],
    tuple[tuple[str, str], ...],
    tuple[tuple[str, str], ...],
    str,
]:
    resolver = LasParameterResolver()
    components = resolve_gas_ratio_inputs(dataset, resolver=resolver)
    resolution = resolver.resolve_dataset(
        dataset,
        targets=("C1", "C2", "C3", "C4", "IC4", "NC4", "C5", "IC5", "NC5", "TG"),
    )
    total_match = resolution.require("TG")
    total_scale = concentration_scale_to_percent(total_match.unit)
    if total_scale is None:
        raise ValueError(
            f"Неподдерживаемая единица TotalGas: {total_match.unit or 'не указана'}"
        )
    c4_values, c4_names, c4_units = _resolve_family(
        components,
        resolution,
        aggregate="C4",
        first_isomer="IC4",
        normal_isomer="NC4",
    )
    c5_values, c5_names, c5_units = _resolve_family(
        components,
        resolution,
        aggregate="C5",
        first_isomer="IC5",
        normal_isomer="NC5",
    )
    component_names = ("C1", "C2", "C3")
    matches = tuple(resolution.require(name) for name in component_names)
    source_ids = {match.curve_id for match in matches}
    source_ids.update(
        match.curve_id
        for name in (*c4_names, *c5_names)
        if (match := resolution.get(name)) is not None
    )
    if total_match.curve_id in source_ids:
        raise ValueError("TotalGas должен быть отдельным синхронным каналом, а не C1-C5")
    inputs = {
        "C1": np.asarray(components["C1"], dtype=np.float64),
        "C2": np.asarray(components["C2"], dtype=np.float64),
        "C3": np.asarray(components["C3"], dtype=np.float64),
        "C4": c4_values,
        "C5": c5_values,
        "TOTAL_GAS": np.asarray(total_match.curve.values, dtype=np.float64) * total_scale,
    }
    input_curves = (
        *((name, resolution.require(name).curve.metadata.original_mnemonic) for name in component_names),
        ("C4", "+".join(c4_names)),
        ("C5", "+".join(c5_names)),
        ("TOTAL_GAS", total_match.curve.metadata.original_mnemonic),
    )
    input_units = (
        *((name, resolution.require(name).unit or "") for name in component_names),
        ("C4", "+".join(c4_units)),
        ("C5", "+".join(c5_units)),
        ("TOTAL_GAS", total_match.unit or ""),
    )
    return inputs, tuple(input_curves), tuple(input_units), total_match.unit or ""


def _resolve_family(
    components: dict[str, np.ndarray],
    resolution,
    *,
    aggregate: str,
    first_isomer: str,
    normal_isomer: str,
) -> tuple[np.ndarray, tuple[str, ...], tuple[str, ...]]:
    names: tuple[str, ...]
    if first_isomer in components and normal_isomer in components:
        names = (first_isomer, normal_isomer)
    elif aggregate in components:
        names = (aggregate,)
    else:
        names = tuple(
            name for name in (first_isomer, normal_isomer) if name in components
        )
    if not names:
        raise ValueError(f"Для ОПУС Газомер отсутствует {aggregate} или его изомеры")
    values = sum_components({name: components[name] for name in names})
    units = tuple(
        (match.unit or "")
        for name in names
        if (match := resolution.get(name)) is not None
    )
    return values, names, units


__all__ = ["OPUS_CURVES", "OPUS_WORKING_CURVES", "build_opus_interpretation_report"]
