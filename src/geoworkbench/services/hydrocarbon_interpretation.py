from __future__ import annotations

from collections import OrderedDict
from dataclasses import replace
from html import escape

import numpy as np

from geoworkbench.domain.models import Dataset
from geoworkbench.project.interpretation_calculation_controller import (
    NormalizedGasCalculationMode,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services import hydrocarbon_interpretation_legacy as _legacy
from geoworkbench.services import hydrocarbon_interpretation_modes as _modes
from geoworkbench.services.hydrocarbon_interpretation_modes import (
    HydrocarbonCandidateInterval,
    HydrocarbonInterpretationReport,
    InterpretationMethodStatus,
    ManualInterpretationInterval,
    candidate_evidence_summary,
    fluid_hypothesis_basis,
    fluid_hypothesis_label,
)
from geoworkbench.services.interval_gas_statistics import (
    build_candidate_interval_statistics,
    enhanced_fluid_hypothesis_basis,
    interval_gas_table_html,
    manual_section_heading,
)
from geoworkbench.services.localization import AppLanguage


_SERVER_TOTAL_NAMES = (
    "TG_NORM",
    "NORMALIZED_TOTAL_GAS",
    "TOTAL_GAS_NORM",
    "NORM_TG",
    "TGNORM",
)
_LOCAL_TOTAL_NAMES = ("TG_NORM_CALC", "TG_NORM")
_SELECTED_MODES: dict[int, NormalizedGasCalculationMode] = {}
_REPORT_DATASETS: OrderedDict[tuple[str, str, str | None], Dataset] = OrderedDict()
_REPORT_DATASET_CACHE_LIMIT = 64


def set_normalized_gas_report_mode(
    session: ProjectSession,
    mode: NormalizedGasCalculationMode | str,
) -> None:
    """Persist the UI-selected report mode for the active session."""

    normalized = _coerce_mode(mode)
    _SELECTED_MODES[id(session)] = normalized
    _modes.set_normalized_gas_report_mode(session, normalized)


def build_hydrocarbon_interpretation_report(
    session: ProjectSession,
    *,
    threshold: float = 3.0,
    normalized_gas_mode: NormalizedGasCalculationMode | str | None = None,
) -> HydrocarbonInterpretationReport:
    """Build the report and retain its dataset for readable interval statistics."""

    session_id = id(session)
    dataset = session.current_dataset
    if normalized_gas_mode is None and session_id not in _SELECTED_MODES:
        report = _legacy.build_hydrocarbon_interpretation_report(
            session,
            threshold=threshold,
        )
        return _remember_report_dataset(report, dataset)

    requested_mode = _coerce_mode(
        normalized_gas_mode
        if normalized_gas_mode is not None
        else _SELECTED_MODES[session_id]
    )
    effective_mode = requested_mode
    waiting_for_local_total = False
    if (
        requested_mode is NormalizedGasCalculationMode.COMPARE
        and dataset is not None
        and _has_valid_normalized_curve(dataset, _SERVER_TOTAL_NAMES, local=False)
        and not _has_valid_normalized_curve(dataset, _LOCAL_TOTAL_NAMES, local=True)
    ):
        # Never compare a server total-gas curve with C1_NORM. Until the local
        # total exists, show the server analysis only and explain what is missing.
        effective_mode = NormalizedGasCalculationMode.SERVER
        waiting_for_local_total = True

    report = _modes.build_hydrocarbon_interpretation_report(
        session,
        threshold=threshold,
        normalized_gas_mode=effective_mode,
    )
    if waiting_for_local_total:
        report = replace(
            report,
            warnings=tuple(
                dict.fromkeys(
                    (
                        *report.warnings,
                        "Режим сравнения ожидает локальный итог TG_NORM_CALC. "
                        "C1_NORM не сопоставляется с серверным total normalized gas, "
                        "поскольку это другой показатель. Выполните локальный расчёт.",
                    )
                )
            ),
        )

    primary = report.primary_mnemonic
    if primary:
        names = tuple(_strip_source_prefix(part) for part in primary.split(" | "))
        cleaned = " | ".join(dict.fromkeys(name for name in names if name))
        if cleaned != primary:
            report = replace(report, primary_mnemonic=cleaned)
    return _remember_report_dataset(report, dataset)


def hydrocarbon_interpretation_html(
    report: HydrocarbonInterpretationReport,
    language: AppLanguage = AppLanguage.RU,
) -> str:
    """Render the standard report with explicit gas readings for every interval."""

    html = _modes.hydrocarbon_interpretation_html(report, language)
    dataset = _REPORT_DATASETS.get(_report_cache_key(report))
    if dataset is None or not report.candidates:
        return html

    statistics = tuple(
        build_candidate_interval_statistics(dataset, candidate)
        for candidate in report.candidates
    )
    for candidate, item in zip(report.candidates, statistics, strict=False):
        old_basis = fluid_hypothesis_basis(candidate, language)
        new_basis = enhanced_fluid_hypothesis_basis(
            old_basis,
            candidate,
            item,
            language,
        )
        html = html.replace(
            f"<p>{escape(old_basis)}</p>",
            f"<p>{escape(new_basis)}</p>",
            1,
        )

    gas_table = interval_gas_table_html(report, statistics, language)
    if gas_table:
        manual_marker = f"<h2>{escape(manual_section_heading(language))}</h2>"
        if manual_marker in html:
            html = html.replace(manual_marker, gas_table + manual_marker, 1)
        else:
            html = html.replace("</body>", gas_table + "</body>")
    return html


def _remember_report_dataset(
    report: HydrocarbonInterpretationReport,
    dataset: Dataset | None,
) -> HydrocarbonInterpretationReport:
    if dataset is None:
        return report
    key = _report_cache_key(report)
    _REPORT_DATASETS[key] = dataset
    _REPORT_DATASETS.move_to_end(key)
    while len(_REPORT_DATASETS) > _REPORT_DATASET_CACHE_LIMIT:
        _REPORT_DATASETS.popitem(last=False)
    return report


def _report_cache_key(
    report: HydrocarbonInterpretationReport,
) -> tuple[str, str, str | None]:
    return report.dataset_id, report.generated_at, report.primary_mnemonic


def _coerce_mode(
    mode: NormalizedGasCalculationMode | str,
) -> NormalizedGasCalculationMode:
    try:
        return NormalizedGasCalculationMode(str(mode))
    except ValueError as exc:
        raise ValueError(f"Неизвестный режим нормализованного газа: {mode}") from exc


def _has_valid_normalized_curve(
    dataset: Dataset,
    names: tuple[str, ...],
    *,
    local: bool,
) -> bool:
    seen: set[str] = set()
    for mnemonic in names:
        curve = dataset.curve_by_mnemonic(mnemonic)
        if curve is None or curve.metadata.curve_id in seen:
            continue
        seen.add(curve.metadata.curve_id)
        is_local = curve.metadata.provenance.startswith("calculation:")
        if is_local is not local:
            continue
        values = np.asarray(curve.values, dtype=np.float64)
        if values.shape == dataset.depth.shape and np.count_nonzero(np.isfinite(values)) >= 20:
            return True
    return False


def _strip_source_prefix(value: str) -> str:
    stripped = value.strip()
    for prefix in ("server: ", "local-calculation: "):
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].strip()
    return stripped


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
