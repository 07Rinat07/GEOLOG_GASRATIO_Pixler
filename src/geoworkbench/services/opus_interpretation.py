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
            "OPUS C1-C5 (additional screening report)",
            (*OPUS_WORKING_CURVES, *OPUS_CURVES),
            available,
            (
                "Lukyanov (1987); Lukyanov & Strelchenko (1997); "
                "Lukyanov & Zhuzhulin (2022). Four source-backed indicators."
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
            "Опубликованные диапазоны четырёх показателей ОПУС перекрываются. Поэтому "
            "они приведены как проверяемые скрининговые признаки и не превращаются в "
            "единственный автоматический класс."
        ),
        (
            "Промышленная продуктивность, вода и окончательный тип флюида не доказываются "
            "только поверхностным газовым каротажем; нужны ГИС, испытания, лаг, режим "
            "дегазатора, фон и локальная калибровка."
        ),
    ]
    total = dataset.curve_by_mnemonic("OPUS_TG_PCT")
    if total is None or not all(dataset.curve_by_mnemonic(name) is not None for name in OPUS_CURVES):
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

    candidates, median, scale, detection_warning = legacy._detect_candidates(
        dataset,
        "OPUS_TG_PCT",
        threshold,
        lba_samples=tuple(well.cuttings),
    )
    if detection_warning:
        warnings.append(detection_warning)

    if median is None or median < 0.1:
        warnings.append(
            "Фоновая сумма C1-C5 ниже 0,1 % об.; опубликованное условие применимости ОПУС не выполнено."
        )
        candidates = ()
    elif candidates:
        accepted: list[HydrocarbonCandidateInterval] = []
        for candidate in candidates:
            contrast = candidate.max_primary_value / median if median > 0.0 else np.nan
            if not np.isfinite(contrast) or contrast < 3.0:
                continue
            accepted.append(_with_opus_evidence(dataset, candidate, contrast))
        candidates = tuple(accepted)
        warnings.append(
            "Интервалы дополнительно отфильтрованы по опубликованному условию контраста C1-C5 не менее 3 к фону."
        )

    return replace(
        base,
        primary_mnemonic="OPUS_TG_PCT",
        baseline_median=median,
        robust_scale=scale,
        methods=methods,
        candidates=candidates,
        warnings=tuple(dict.fromkeys(warnings)),
        report_profile="opus",
    )


def _with_opus_evidence(
    dataset,
    candidate: HydrocarbonCandidateInterval,
    contrast: float,
) -> HydrocarbonCandidateInterval:
    depth = np.asarray(dataset.depth, dtype=np.float64)
    mask = (
        np.isfinite(depth)
        & (depth >= candidate.top_depth)
        & (depth <= candidate.bottom_depth)
    )
    means: list[tuple[str, float]] = []
    for mnemonic in OPUS_CURVES:
        curve = dataset.curve_by_mnemonic(mnemonic)
        if curve is None:
            continue
        values = np.asarray(curve.values, dtype=np.float64)
        valid = mask & np.isfinite(values)
        if np.any(valid):
            means.append((mnemonic, float(np.mean(values[valid]))))
    summary = ", ".join(f"{name}={value:.6g}" for name, value in means)
    evidence = [*candidate.evidence, f"OPUS C1-C5 contrast/background={contrast:.4g}"]
    if summary:
        evidence.append(f"OPUS interval means: {summary}")
    return replace(
        candidate,
        metrics=tuple((*candidate.metrics, *means)),
        evidence=tuple(evidence),
    )


__all__ = ["OPUS_CURVES", "OPUS_WORKING_CURVES", "build_opus_interpretation_report"]
