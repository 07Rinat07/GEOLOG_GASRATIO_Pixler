from __future__ import annotations

from dataclasses import replace
from html import escape
import re

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
from geoworkbench.services.hydrocarbon_interpretation_legacy import (
    OpusGasomerIndicatorReport,
    OpusGasomerIntervalReport,
    OpusGasomerReportSection,
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
_CLIENT_LIMITATIONS_PATTERN = re.compile(
    r"<div\b[^>]*class=[\"'][^\"']*\bnotice\b[^\"']*[\"'][^>]*>.*?</div>",
    re.IGNORECASE | re.DOTALL,
)


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
    """Render a presentation-ready report while retaining QC in structured data."""

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
        if report.opus_gasomer is not None:
            gasomer_html = _opus_gasomer_html(report)
            marker = '<div class="notice"><h2>'
            position = html.find(marker)
            html = (
                html[:position] + gasomer_html + html[position:]
                if position >= 0
                else html.replace("</body>", gasomer_html + "</body>")
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
    html = html.replace("</style>", pagination_css + "</style>", 1)
    return _strip_client_limitations(html)


def _strip_client_limitations(html: str) -> str:
    """Remove methodology-limitations cards from customer-facing documents.

    Structured warnings remain on ``HydrocarbonInterpretationReport`` and in
    diagnostics/audit data.  Only presentation HTML is sanitized so PDF/DOCX
    exports stay concise without weakening internal validation.
    """

    return _CLIENT_LIMITATIONS_PATTERN.sub("", html)


def _opus_gasomer_html(report: HydrocarbonInterpretationReport) -> str:
    section = report.opus_gasomer
    if section is None:
        return ""
    curve_names = dict(section.input_curves)
    curve_units = dict(section.input_units)
    inputs = ", ".join(
        f"{escape(name)}={escape(curve_names.get(name, '—'))} "
        f"[{escape(curve_units.get(name, '—') or '—')}]"
        for name in ("TOTAL_GAS", "C1", "C2", "C3", "C4", "C5")
    ) or "—"
    formula_rows = "".join(
        "<tr>"
        f"<td>{escape(name)}</td><td><code>{escape(formula)}</code></td>"
        "</tr>"
        for name, formula in section.formulas
    )
    interval_blocks: list[str] = []
    for interval in section.intervals:
        indicator_rows = "".join(
            "<tr>"
            f"<td>{escape(item.mnemonic)}</td>"
            f"<td>{'—' if item.median_value is None else f'{item.median_value:.6g}'}</td>"
            f"<td>{item.class_code} — {escape(item.class_label)}</td>"
            f"<td>{item.vote_support * 100.0:.1f}%</td>"
            f"<td>{item.available_rows}/{item.total_rows}</td>"
            f"<td>{escape(_counts_text(item.vote_counts))}</td>"
            f"<td>{escape(_state_counts_text(item.state_counts))}</td>"
            "</tr>"
            for item in interval.indicators
        )
        detector = (
            "локальный фон —; пик —; ΔTG —; robust z —; контраст —"
            if interval.background_median is None
            else (
                f"локальный фон {interval.background_median:.6g} {section.working_unit}; "
                f"пик {interval.peak_total_gas:.6g}; ΔTG {interval.delta_peak:.6g}; "
                f"max robust z {interval.max_robust_z:.3f}; "
                f"max контраст {interval.max_contrast:.3f}"
            )
        )
        interval_blocks.append(
            f"<h3 class='opus-gasomer-interval'>{interval.top_depth:.2f}–"
            f"{interval.bottom_depth:.2f} "
            f"{escape(report.depth_unit)}: класс {interval.class_code} — "
            f"{escape(interval.class_label)}</h3>"
            f"<p>Поддержка класса: {interval.support_fraction * 100.0:.1f}%; "
            f"валидных синхронных строк: {interval.valid_rows}/{interval.total_rows}; "
            f"{escape(detector)}.</p>"
            "<table><thead><tr><th>Показатель</th><th>Медиана</th><th>Голос</th>"
            "<th>Поддержка голоса</th><th>Доступно</th><th>Голоса 1–7</th>"
            "<th>QC-состояния</th></tr></thead>"
            f"<tbody>{indicator_rows}</tbody></table>"
        )
    lod_text = (
        "не задан; detector не запускается без скрытого значения"
        if section.total_gas_lod is None
        else f"{section.total_gas_lod:.6g} {section.working_unit}"
    )
    provenance = "".join(f"<li>{escape(item)}</li>" for item in section.provenance)
    errata = "".join(f"<li>{escape(item)}</li>" for item in section.errata)
    intervals_html = "".join(interval_blocks) or (
        "<p>Интервалы ОПУС Газомер не сформированы: проверьте независимый TotalGas, "
        "C1–C5, единицы и положительный LOD TotalGas.</p>"
    )
    return (
        "<h2 class='opus-gasomer-section'>"
        "ОПУС Газомер — пять показателей и голоса</h2>"
        f"<p><b>Профиль:</b> {escape(section.profile_id)} v{escape(section.profile_version)}; "
        f"статус: {escape(section.profile_status)}.<br>"
        f"<b>Режим:</b> {escape(section.calculation_mode)}; источник интервалов: "
        f"{escape(section.interval_source)}; рабочая единица: "
        f"{escape(section.working_unit)}; LOD TotalGas: {escape(lod_text)}.<br>"
        f"<b>Входные кривые:</b> {inputs}.</p>"
        "<table><thead><tr><th>Показатель</th><th>Точная формула профиля</th>"
        f"</tr></thead><tbody>{formula_rows}</tbody></table>"
        + intervals_html
        + "<h3>Происхождение формул</h3><ul>"
        + provenance
        + f"<li>SHA-256 книги: {escape(section.source_workbook_sha256)}</li></ul>"
        + "<h3>Исправления исходной книги</h3><ul>"
        + errata
        + "</ul>"
    )


def _counts_text(counts: tuple[tuple[int, int], ...]) -> str:
    return ", ".join(f"{code}:{count}" for code, count in counts)


def _state_counts_text(counts: tuple[tuple[str, int], ...]) -> str:
    return ", ".join(f"{name}:{count}" for name, count in counts)


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
    "OpusGasomerIndicatorReport",
    "OpusGasomerIntervalReport",
    "OpusGasomerReportSection",
    "build_hydrocarbon_interpretation_report",
    "build_opus_interpretation_report",
    "candidate_evidence_summary",
    "fluid_hypothesis_basis",
    "fluid_hypothesis_label",
    "hydrocarbon_interpretation_html",
    "set_normalized_gas_report_mode",
]
