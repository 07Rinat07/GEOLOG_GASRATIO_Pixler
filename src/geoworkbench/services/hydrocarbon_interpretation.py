from __future__ import annotations

from dataclasses import replace

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
    hydrocarbon_interpretation_html as _base_hydrocarbon_interpretation_html,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.opus_interpretation import build_opus_interpretation_report


_SERVER_TOTAL_NAMES = (
    "TG_NORM",
    "NORMALIZED_TOTAL_GAS",
    "TOTAL_GAS_NORM",
    "NORM_TG",
    "TGNORM",
)
_LOCAL_TOTAL_NAMES = ("TG_NORM_CALC", "TG_NORM")
_SELECTED_MODES: dict[int, NormalizedGasCalculationMode] = {}


_REPORT_TERMINOLOGY_REPLACEMENTS: dict[
    AppLanguage,
    tuple[tuple[str, str], ...],
] = {
    AppLanguage.RU: (
        (
            "Кандидатные интервалы УВ-проявлений",
            "Перспективные интервалы УВ-проявлений",
        ),
        (
            "Кандидатные интервалы по выбранному порогу не найдены.",
            "Перспективные интервалы по выбранному порогу не найдены.",
        ),
        (
            "Автоматически отмечаются только кандидаты по относительной газовой аномалии.",
            "Автоматически выделяются только перспективные интервалы по относительной газовой аномалии.",
        ),
    ),
    AppLanguage.KK: (
        (
            "Көмірсутек көріністерінің кандидат аралықтары",
            "Көмірсутек көріністерінің перспективалы аралықтары",
        ),
        (
            "Таңдалған шек бойынша кандидат аралықтар табылмады.",
            "Таңдалған шек бойынша перспективалы аралықтар табылмады.",
        ),
        (
            "Автоматически отмечаются только кандидаты по относительной газовой аномалии.",
            "Автоматически выделяются только перспективные интервалы по относительной газовой аномалии.",
        ),
    ),
    AppLanguage.EN: (
        (
            "Candidate hydrocarbon-show intervals",
            "Prospective hydrocarbon-show intervals",
        ),
        (
            "No candidate intervals were found at the selected threshold.",
            "No prospective intervals were found at the selected threshold.",
        ),
        (
            "Автоматически отмечаются только кандидаты по относительной газовой аномалии.",
            "Автоматически выделяются только перспективные интервалы по относительной газовой аномалии.",
        ),
    ),
}

_PROSPECTIVE_INTERVAL_HEADINGS = {
    AppLanguage.RU: "Перспективные интервалы УВ-проявлений",
    AppLanguage.KK: "Көмірсутек көріністерінің перспективалы аралықтары",
    AppLanguage.EN: "Prospective hydrocarbon-show intervals",
}


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
    """Build a report while preserving the legacy API when no mode was selected."""

    session_id = id(session)
    if normalized_gas_mode is None and session_id not in _SELECTED_MODES:
        return _legacy.build_hydrocarbon_interpretation_report(
            session,
            threshold=threshold,
        )

    requested_mode = _coerce_mode(
        normalized_gas_mode
        if normalized_gas_mode is not None
        else _SELECTED_MODES[session_id]
    )
    effective_mode = requested_mode
    waiting_for_local_total = False
    dataset = session.current_dataset
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
    if not primary:
        return report
    names = tuple(_strip_source_prefix(part) for part in primary.split(" | "))
    cleaned = " | ".join(dict.fromkeys(name for name in names if name))
    return report if cleaned == primary else replace(report, primary_mnemonic=cleaned)


def hydrocarbon_interpretation_html(
    report: HydrocarbonInterpretationReport,
    language: AppLanguage = AppLanguage.RU,
) -> str:
    """Render the report with user-facing prospective-interval terminology."""

    html = _base_hydrocarbon_interpretation_html(report, language)
    if report.report_profile == "opus":
        opus_title = {
            AppLanguage.RU: "Дополнительный отчёт ОПУС по C1-C5",
            AppLanguage.KK: "C1-C5 бойынша қосымша ОПУС есебі",
            AppLanguage.EN: "Additional OPUS C1-C5 report",
        }[language]
        title_start = html.find("<h1>")
        title_end = html.find("</h1>", title_start)
        if title_start >= 0 and title_end >= 0:
            html = (
                html[:title_start]
                + f"<h1>{opus_title}</h1>"
                + html[title_end + len("</h1>") :]
            )
    for old, new in _REPORT_TERMINOLOGY_REPLACEMENTS[language]:
        html = html.replace(old, new)

    heading = _PROSPECTIVE_INTERVAL_HEADINGS[language]
    html = html.replace(
        f"<h2>{heading}</h2>",
        f"<h2 class='prospective-intervals-heading'>{heading}</h2>",
        1,
    )
    pagination_css = """
.prospective-intervals-heading {
    page-break-before: always;
    break-before: page;
    margin-top: 0;
}
"""
    return html.replace("</style>", pagination_css + "</style>", 1)


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
    "build_opus_interpretation_report",
    "candidate_evidence_summary",
    "fluid_hypothesis_basis",
    "fluid_hypothesis_label",
    "hydrocarbon_interpretation_html",
    "set_normalized_gas_report_mode",
]
