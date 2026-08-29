from __future__ import annotations

from dataclasses import replace

import numpy as np

from geoworkbench.project.session import ProjectSession
from geoworkbench.services import hydrocarbon_interpretation_legacy as legacy
from geoworkbench.services.hydrocarbon_interpretation_legacy import (
    HydrocarbonCandidateInterval,
    HydrocarbonInterpretationReport,
    InterpretationMethodStatus,
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
        return replace(
            base,
            primary_mnemonic=None,
            baseline_median=None,
            robust_scale=None,
            methods=methods,
            candidates=(),
            warnings=tuple(warnings),
            report_profile="opus",
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

    return replace(
        base,
        primary_mnemonic="OPUS_TG_PCT",
        baseline_median=raw_background,
        robust_scale=scale,
        methods=methods,
        candidates=candidates,
        warnings=tuple(dict.fromkeys(warnings)),
        report_profile="opus",
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


__all__ = ["OPUS_CURVES", "OPUS_WORKING_CURVES", "build_opus_interpretation_report"]
