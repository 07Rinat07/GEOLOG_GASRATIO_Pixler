from __future__ import annotations

from dataclasses import replace

from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.project.interpretation_calculation_controller import (
    NormalizedGasCalculationMode,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services import hydrocarbon_interpretation_legacy as _legacy
from geoworkbench.services.hydrocarbon_interpretation_legacy import (
    HydrocarbonCandidateInterval,
    HydrocarbonInterpretationReport,
    InterpretationMethodStatus,
    ManualInterpretationInterval,
    candidate_evidence_summary,
    fluid_hypothesis_basis,
    fluid_hypothesis_label,
    hydrocarbon_interpretation_html,
)


_SERVER_NORMALIZED_GAS_NAMES = (
    "TG_NORM",
    "NORMALIZED_TOTAL_GAS",
    "TOTAL_GAS_NORM",
    "NORM_TG",
    "TGNORM",
)
_LOCAL_NORMALIZED_GAS_NAMES = (
    "TG_NORM_CALC",
    "TG_NORM",
    "C1_NORM_REF",
    "C1_NORM",
)
_REPORT_MODES: dict[int, NormalizedGasCalculationMode] = {}


def set_normalized_gas_report_mode(
    session: ProjectSession,
    mode: NormalizedGasCalculationMode | str,
) -> None:
    _REPORT_MODES[id(session)] = _coerce_mode(mode)


def build_hydrocarbon_interpretation_report(
    session: ProjectSession,
    *,
    threshold: float = 3.0,
    normalized_gas_mode: NormalizedGasCalculationMode | str | None = None,
) -> HydrocarbonInterpretationReport:
    """Build one report while keeping server and local normalized gas independent."""

    base = _legacy.build_hydrocarbon_interpretation_report(session, threshold=threshold)
    dataset = session.current_dataset
    well = session.current_well
    if dataset is None or well is None:
        return base

    mode = _coerce_mode(
        normalized_gas_mode
        if normalized_gas_mode is not None
        else _REPORT_MODES.get(id(session), NormalizedGasCalculationMode.COMPARE)
    )
    server = _first_normalized_series(dataset, _SERVER_NORMALIZED_GAS_NAMES, local=False)
    local = _first_normalized_series(dataset, _LOCAL_NORMALIZED_GAS_NAMES, local=True)
    selected: list[tuple[str, CurveData]] = []
    if mode in {NormalizedGasCalculationMode.COMPARE, NormalizedGasCalculationMode.SERVER}:
        if server is not None:
            selected.append(("server", server))
    if mode in {NormalizedGasCalculationMode.COMPARE, NormalizedGasCalculationMode.LOCAL}:
        if local is not None:
            selected.append(("local-calculation", local))

    warnings = [
        warning
        for warning in base.warnings
        if not warning.startswith(
            (
                "Нормализованный газ не рассчитан.",
                "Нормализованная кривая ",
            )
        )
    ]
    if not selected:
        label = {
            NormalizedGasCalculationMode.COMPARE: "серверная и локальная",
            NormalizedGasCalculationMode.SERVER: "серверная/файловая",
            NormalizedGasCalculationMode.LOCAL: "локально рассчитанная",
        }[mode]
        warnings.append(
            f"Не найдена {label} кривая нормализованного газа с минимум 20 корректными отсчётами."
        )
        if mode is NormalizedGasCalculationMode.COMPARE:
            return replace(base, warnings=tuple(warnings))
        return replace(
            base,
            primary_mnemonic=None,
            baseline_median=None,
            robust_scale=None,
            candidates=(),
            warnings=tuple(warnings),
        )

    analyses: list[
        tuple[str, CurveData, tuple[HydrocarbonCandidateInterval, ...], float | None, float | None]
    ] = []
    for source_kind, curve in selected:
        candidates, median, scale, warning = _legacy._detect_candidates(
            dataset,
            curve.metadata.original_mnemonic,
            threshold,
            lba_samples=tuple(well.cuttings),
        )
        marker = (
            f"normalized-gas source={source_kind}; "
            f"curve={curve.metadata.original_mnemonic}"
        )
        candidates = tuple(
            replace(candidate, evidence=(marker, *candidate.evidence))
            for candidate in candidates
        )
        analyses.append((source_kind, curve, candidates, median, scale))
        if warning:
            warnings.append(
                f"{curve.metadata.original_mnemonic} ({source_kind}): {warning}"
            )

    if server is not None:
        warnings.append(
            f"Серверная/файловая кривая {server.metadata.original_mnemonic} сохранена без перезаписи."
        )
    if local is not None:
        warnings.append(
            f"Локальная кривая {local.metadata.original_mnemonic} рассчитана программой и хранится отдельно."
        )
    if mode is NormalizedGasCalculationMode.COMPARE and server is not None and local is not None:
        server_candidates = next(item[2] for item in analyses if item[0] == "server")
        local_candidates = next(
            item[2] for item in analyses if item[0] == "local-calculation"
        )
        matched, server_only, local_only = _interval_agreement(
            server_candidates,
            local_candidates,
        )
        warnings.append(
            "Сравнение серверного и локального нормализованного газа выполнено по "
            "собственному robust-фону каждой кривой: "
            f"совпадающих интервалов {matched}, только серверных {server_only}, "
            f"только локальных {local_only}. Каждый интервал отдельно сопоставлен с ЛБА."
        )

    all_candidates = tuple(
        sorted(
            (candidate for _, _, candidates, _, _ in analyses for candidate in candidates),
            key=lambda candidate: (
                candidate.top_depth,
                candidate.bottom_depth,
                candidate.primary_mnemonic.casefold(),
            ),
        )
    )
    primary_names = " | ".join(
        f"{source_kind}: {curve.metadata.original_mnemonic}"
        for source_kind, curve, _, _, _ in analyses
    )
    first_analysis = analyses[0]
    methods = _normalized_method_status(base.methods, analyses)
    return replace(
        base,
        primary_mnemonic=primary_names,
        baseline_median=first_analysis[3],
        robust_scale=first_analysis[4],
        methods=methods,
        candidates=all_candidates,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _coerce_mode(
    mode: NormalizedGasCalculationMode | str,
) -> NormalizedGasCalculationMode:
    try:
        return NormalizedGasCalculationMode(str(mode))
    except ValueError as exc:
        raise ValueError(f"Неизвестный режим нормализованного газа: {mode}") from exc


def _first_normalized_series(
    dataset: Dataset,
    names: tuple[str, ...],
    *,
    local: bool,
) -> CurveData | None:
    seen: set[str] = set()
    for mnemonic in names:
        curve = dataset.curve_by_mnemonic(mnemonic)
        if curve is None or curve.metadata.curve_id in seen:
            continue
        seen.add(curve.metadata.curve_id)
        is_local = curve.metadata.provenance.startswith("calculation:")
        if is_local is not local:
            continue
        if _legacy._valid_gas_sample_count(dataset, curve.values) >= 20:
            return curve
    return None


def _interval_agreement(
    server: tuple[HydrocarbonCandidateInterval, ...],
    local: tuple[HydrocarbonCandidateInterval, ...],
) -> tuple[int, int, int]:
    matched_server = {
        index
        for index, candidate in enumerate(server)
        if any(_overlaps(candidate, other) for other in local)
    }
    matched_local = {
        index
        for index, candidate in enumerate(local)
        if any(_overlaps(candidate, other) for other in server)
    }
    return (
        min(len(matched_server), len(matched_local)),
        len(server) - len(matched_server),
        len(local) - len(matched_local),
    )


def _overlaps(
    left: HydrocarbonCandidateInterval,
    right: HydrocarbonCandidateInterval,
) -> bool:
    return max(left.top_depth, right.top_depth) < min(
        left.bottom_depth,
        right.bottom_depth,
    )


def _normalized_method_status(
    methods: tuple[InterpretationMethodStatus, ...],
    analyses: list[
        tuple[str, CurveData, tuple[HydrocarbonCandidateInterval, ...], float | None, float | None]
    ],
) -> tuple[InterpretationMethodStatus, ...]:
    available = tuple(
        dict.fromkeys(curve.metadata.original_mnemonic for _, curve, _, _, _ in analyses)
    )
    result: list[InterpretationMethodStatus] = []
    for method in methods:
        if "normalized" in method.method.casefold():
            result.append(
                replace(
                    method,
                    curve_mnemonics=tuple(
                        dict.fromkeys((*method.curve_mnemonics, "TG_NORM_CALC"))
                    ),
                    available_mnemonics=available,
                )
            )
        else:
            result.append(method)
    return tuple(result)


__all__ = [
    "HydrocarbonCandidateInterval",
    "HydrocarbonInterpretationReport",
    "InterpretationMethodStatus",
    "ManualInterpretationInterval",
    "build_hydrocarbon_interpretation_report",
    "candidate_evidence_summary",
    "fluid_hypothesis_basis",
    "fluid_hypothesis_label",
    "hydrocarbon_interpretation_html",
    "set_normalized_gas_report_mode",
]
