from __future__ import annotations

import os
from pathlib import Path
from functools import partial
from typing import Literal
from xml.etree import ElementTree as ET
from collections.abc import Callable
import tempfile
import zipfile
from xml.sax.saxutils import escape as xml_escape


from geoworkbench.services.gas_context_report_labels import (
    gas_context_type_text, gas_context_impact_label, gas_context_identity_label,
)

from geoworkbench.domain.depth_interval import scope_dataset
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.printing.report_document_control_docx import report_document_control_docx_footer
from geoworkbench.domain.models import Dataset
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
    candidate_evidence_summary,
    fluid_hypothesis_basis,
    fluid_hypothesis_label,
)
from geoworkbench.services.interval_gas_statistics import (
    CandidateIntervalGasStatistics,
    absolute_gas_components_summary,
    build_candidate_interval_statistics,
    enhanced_fluid_hypothesis_basis,
)
from geoworkbench.printing.hydrocarbon_report_i18n import hydrocarbon_report_labels
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.interpretation_geology_interval_evidence import GasGeologyIntervalEvidence
from geoworkbench.services.interpretation_geology_evidence_export import verified_report_geology_evidence
from geoworkbench.services.interpretation_geology_interval_evidence_html import geology_interval_evidence_table
from geoworkbench.services.interpretation_method_comparison import MethodComparisonInterval
from geoworkbench.services.interpretation_method_comparison_html import method_comparison_table
from geoworkbench.services.hydrocarbon_interpretation_report_locale import (
    localize_method_calculation,
    localize_method_name,
)
from geoworkbench.services.interpretation_classification_audit import (
    CLASSIFICATION_AUDIT_DOCX_PART,
    interpretation_classification_audit_json,
)
from geoworkbench.services.opus_report_labels import opus_report_label
from geoworkbench.services.parameter_labels import (
    localized_curve_name,
    localized_curve_reference,
)


class HydrocarbonInterpretationExportError(RuntimeError):
    pass


# A4 landscape body: 16838 twips, 850-twip left and right margins.
# Keep a further buffer so Word/LibreOffice border rounding cannot clip cells.
_MAX_BODY_TABLE_WIDTH_TWIPS = 14_000
_PORTRAIT_TABLE_WIDTH_TWIPS = 9_600
_WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _fit_table_widths(widths: tuple[int, ...], *, max_width: int = _MAX_BODY_TABLE_WIDTH_TWIPS) -> tuple[int, ...]:
    """Keep positive weighted columns within the physical Word page width."""
    if not widths or any(type(width) is not int or width <= 0 for width in widths):
        raise ValueError("Column widths must be positive integers")
    if type(max_width) is not int or max_width <= 0:
        raise ValueError("Printable table width must be a positive integer")
    total = sum(widths)
    if total <= max_width:
        return widths
    # Each column requires at least one twip. Scaling first and clamping
    # zero-width columns afterwards could exceed the printable page width.
    count = len(widths)
    if count > max_width:
        raise ValueError("Too many columns to fit the printable Word table width")
    available = max_width - count
    quotas = tuple(divmod(width * available, total) for width in widths)
    scaled = [1 + whole for whole, _ in quotas]
    remainder = max_width - sum(scaled)
    # Largest-remainder apportionment is deterministic, retains proportions
    # to twip precision and makes tblW, tblGrid and tcW agree exactly.
    for index in sorted(
        range(count), key=lambda index: (-quotas[index][1], index)
    )[:remainder]:
        scaled[index] += 1
    return tuple(scaled)

def _resize_docx_tables(document_xml: str | bytes, limit: int) -> bytes:
    """Keep every fixed-grid Word table inside the portrait printable width."""
    root = ET.fromstring(document_xml)
    def q(tag: str) -> str:
        return f"{{{_WORD_NS}}}{tag}"
    for table in root.iter(q("tbl")):
        properties = table.find(q("tblPr"))
        grid = table.find(q("tblGrid"))
        if properties is None or grid is None:
            raise ValueError("Word table has no fixed-width metadata")
        columns = grid.findall(q("gridCol"))
        widths = _fit_table_widths(
            tuple(int(col.get(q("w"), "0")) for col in columns), max_width=limit,
        )
        tbl_width = properties.find(q("tblW"))
        if tbl_width is None:
            raise ValueError("Word table has no declared width")
        tbl_width.set(q("w"), str(sum(widths)))
        for col, width in zip(columns, widths, strict=True):
            col.set(q("w"), str(width))
        for row in table.findall(q("tr")):
            cells = row.findall(q("tc"))
            if len(cells) != len(widths):
                raise ValueError("Word table column count changed")
            for cell, width in zip(cells, widths, strict=True):
                tc_width = cell.find(f'{q("tcPr")}/{q("tcW")}')
                if tc_width is None:
                    raise ValueError("Word table cell is missing width")
                tc_width.set(q("w"), str(width))
    ET.register_namespace("w", _WORD_NS)
    ET.register_namespace("r", _R_NS)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)

_DOCX_PROGRESS = {
    AppLanguage.RU: (
        "Подготовка Word-отчёта",
        "Расчёт интервальной статистики",
        "Сохранение Word-файла",
        "Word-отчёт готов",
        "Не удалось экспортировать Word",
    ),
    AppLanguage.KK: (
        "Word есебін дайындау",
        "Аралық статистиканы есептеу",
        "Word файлын сақтау",
        "Word есебі дайын",
        "Word экспорттау мүмкін болмады",
    ),
    AppLanguage.EN: (
        "Preparing Word report",
        "Calculating interval statistics",
        "Saving Word file",
        "Word report ready",
        "Failed to export Word",
    ),
}


_DOCX_VALIDATION_ERRORS = {
    AppLanguage.RU: (
        "Отчёт относится к другому набору данных",
        "Кривые с неверным числом отсчётов",
    ),
    AppLanguage.KK: (
        "Есеп басқа деректер жинағына жатады",
        "Есеп саны қате қисықтар",
    ),
    AppLanguage.EN: (
        "The report belongs to another dataset",
        "Curves with an invalid sample count",
    ),
}


def export_hydrocarbon_interpretation_xlsx(
    report: HydrocarbonInterpretationReport,
    dataset: Dataset,
    target: str | Path,
    *,
    language: AppLanguage = AppLanguage.RU,
    overwrite: bool = False,
    progress: Callable[[str, int, int], None] | None = None,
    method_comparisons: tuple[MethodComparisonInterval, ...] = (),
    geology_evidence: tuple[GasGeologyIntervalEvidence, ...] = (),
) -> Path:
    """Export the single readable workbook used by every interpretation workflow."""

    from geoworkbench.data.hydrocarbon_interpretation_export_readable import (
        export_readable_hydrocarbon_interpretation_xlsx,
    )

    exporter: Callable[..., Path] = (
        partial(export_readable_hydrocarbon_interpretation_xlsx, method_comparisons=method_comparisons)
        if method_comparisons else export_readable_hydrocarbon_interpretation_xlsx
    )
    if geology_evidence:
        exporter = partial(exporter, geology_evidence=geology_evidence)
    return exporter(
        report,
        dataset,
        target,
        language=language,
        overwrite=overwrite,
        progress=progress,
    )


def export_hydrocarbon_interpretation_docx(
    report: HydrocarbonInterpretationReport,
    target: str | Path,
    *,
    dataset: Dataset | None = None,
    language: AppLanguage = AppLanguage.RU,
    orientation: Literal["landscape", "portrait"] = "portrait",
    overwrite: bool = False,
    progress: Callable[[str, int, int], None] | None = None,
    method_comparisons: tuple[MethodComparisonInterval, ...] = (),
    geology_evidence: tuple[GasGeologyIntervalEvidence, ...] = (),
) -> Path:
    if orientation not in ("landscape", "portrait"):
        raise ValueError("Word page orientation must be landscape or portrait")
    verified_report_geology_evidence(report, geology_evidence)
    progress_prepare, progress_statistics, progress_save, progress_ready, error_export = (
        _DOCX_PROGRESS[language]
    )
    _notify_export_progress(progress, progress_prepare, 0, 100)
    if dataset is not None:
        _validate_dataset(report, dataset, language=language)
        dataset = scope_dataset(dataset, report.analysis_depth_interval)
    _notify_export_progress(progress, progress_statistics, 20, 100)
    destination = _prepare_target(target, ".docx", overwrite=overwrite)
    temporary = _temporary_path(destination)
    try:
        writer = (
            partial(_write_docx, method_comparisons=method_comparisons)
            if method_comparisons else _write_docx
        )
        if geology_evidence:
            writer = partial(writer, geology_evidence=geology_evidence)
        writer(temporary, report, dataset, language, orientation=orientation)
        _notify_export_progress(progress, progress_save, 90, 100)
        os.replace(temporary, destination)
        _notify_export_progress(progress, progress_ready, 100, 100)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        if isinstance(exc, (FileExistsError, HydrocarbonInterpretationExportError)):
            raise
        raise HydrocarbonInterpretationExportError(
            f"{error_export}: {destination}"
        ) from exc
    return destination


def _notify_export_progress(
    progress: Callable[[str, int, int], None] | None,
    stage: str,
    current: int,
    total: int,
) -> None:
    if progress is not None:
        progress(stage, current, total)


def _write_docx(
    path: Path,
    report: HydrocarbonInterpretationReport,
    dataset: Dataset | None,
    language: AppLanguage = AppLanguage.RU,
    *,
    method_comparisons: tuple[MethodComparisonInterval, ...] = (),
    geology_evidence: tuple[GasGeologyIntervalEvidence, ...] = (),
    orientation: Literal["landscape", "portrait"] = "portrait",
) -> None:
    interval = getattr(report, "analysis_depth_interval", None)
    labels = hydrocarbon_report_labels(language)
    statistics: tuple[CandidateIntervalGasStatistics | None, ...] = tuple(
        build_candidate_interval_statistics(dataset, candidate) if dataset is not None else None
        for candidate in report.candidates
    )
    report_title = (
        labels.title_opus
        if report.report_profile == "opus"
        else labels.title_standard
    )
    body: list[str] = [
        _paragraph(report_title, style="Title"),
        _paragraph(f"{labels.project}: {report.project_name}"),
        _paragraph(f"{labels.well}: {report.well_name}"),
        _paragraph(f"{labels.dataset}: {report.dataset_name}"),
        *([_paragraph(interval.formatted(report.depth_unit))] if interval is not None else []),
        _paragraph(
            f"{labels.primary_gas_curve}: "
            f"{localized_curve_reference(report.primary_mnemonic, language=language) if report.primary_mnemonic else '—'}"
        ),
        _paragraph(f"{labels.robust_z_threshold}: {report.threshold:.2f}"),
        _paragraph(labels.methods_heading, style="Heading1"),
        _table(
            (
                labels.method,
                labels.status,
                labels.used_data,
                labels.calculation_rule,
                labels.source_evidence,
            ),
            tuple(
                (
                    localize_method_name(method.method, language),
                    labels.available if method.available else labels.no_data,
                    ", ".join(
                        localized_curve_reference(name, language=language)
                        for name in method.available_mnemonics
                    ) or labels.no_data,
                    localize_method_calculation(method.calculation, language) or "—",
                    method.source,
                )
                for method in report.methods
            ),
            widths=(2_400, 1_000, 2_200, 4_700, 4_800),
        ),
    ]
    if report.opus_gasomer is not None:
        body.extend(_opus_gasomer_docx(report, language))
    if getattr(report, "gas_context_events", ()):
        body.extend(_gas_context_docx(report, language))
    if method_comparisons:
        body.extend(_method_comparisons_docx(method_comparisons, language, report.depth_unit))
    for evidence in geology_evidence:
        presentation = geology_interval_evidence_table(evidence, language)
        body.extend((
            _paragraph(presentation.title, style="Heading1"),
            _paragraph(presentation.intro),
            _paragraph(presentation.interval),
            _paragraph(presentation.coverage_title),
            _table(presentation.coverage_headings, presentation.coverage_rows, widths=(4000, 3500, 6500)),
            _table(presentation.headings, presentation.rows, widths=(1800, 2200, 2500, 2500, 5000)),
        ))
    body.append(_paragraph(labels.prospective_heading, style="Heading1"))
    if report.candidates:
        body.append(
            _table(
                (
                    labels.interval,
                    labels.strength,
                    labels.preliminary_interpretation,
                    labels.absolute_gas,
                    labels.basis,
                ),
                tuple(
                    (
                        f"{candidate.top_depth:.2f}–{candidate.bottom_depth:.2f} {report.depth_unit}",
                        {
                            "low": labels.strength_low,
                            "medium": labels.strength_medium,
                            "high": labels.strength_high,
                        }.get(candidate.anomaly_strength, candidate.anomaly_strength),
                        fluid_hypothesis_label(candidate, language),
                        absolute_gas_components_summary(item.components, language)
                        if item is not None
                        else labels.no_data,
                        candidate_evidence_summary(candidate, language),
                    )
                    for candidate, item in zip(report.candidates, statistics, strict=True)
                ),
                widths=(2_100, 1_600, 3_000, 5_000, 3_400),
            )
        )
    else:
        body.append(_paragraph(labels.no_intervals))

    body.append(_paragraph(labels.details_heading, style="Heading1"))
    if report.candidates:
        for candidate, item in zip(report.candidates, statistics, strict=True):
            basis = fluid_hypothesis_basis(candidate, language)
            if item is not None:
                basis = enhanced_fluid_hypothesis_basis(
                    basis,
                    candidate,
                    item,
                    language,
                )
            body.append(
                _paragraph(
                    f"{candidate.top_depth:.2f}–{candidate.bottom_depth:.2f} "
                    f"{report.depth_unit}: "
                    f"{fluid_hypothesis_label(candidate, language)}. {basis}"
                )
            )
    else:
        body.append(_paragraph(labels.no_intervals))

    body.append(_paragraph(labels.manual_heading, style="Heading1"))
    if report.manual_intervals:
        body.append(
            _table(
                (
                    labels.interpretation,
                    labels.interval,
                    labels.type_label,
                    labels.label,
                    labels.comment,
                ),
                tuple(
                    (
                        item.interpretation_name,
                        f"{item.top_depth:.2f}–{item.bottom_depth:.2f} {report.depth_unit}",
                        item.interval_type,
                        item.label,
                        item.comment,
                    )
                    for item in report.manual_intervals
                ),
                widths=(2_600, 2_200, 2_200, 4_000, 4_100),
            )
        )
    else:
        body.append(_paragraph(labels.no_manual))
    page_width, page_height = ((11906, 16838) if orientation == "portrait" else (16838, 11906))
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<w:body>"
        + "".join(body)
        + f'<w:sectPr><w:footerReference w:type="default" r:id="rIdFooter"/><w:pgSz w:w="{page_width}" w:h="{page_height}" w:orient="{orientation}"/>'
        '<w:pgMar w:top="850" w:right="850" w:bottom="1440" w:left="850" '
        'w:header="708" w:footer="720" w:gutter="0"/></w:sectPr>'
        "</w:body></w:document>"
    )
    if orientation == "portrait":
        document_xml = _resize_docx_tables(document_xml, _PORTRAIT_TABLE_WIDTH_TWIPS)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/styles.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
            '<Override PartName="/word/footer.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
            "</Types>",
        )
        package.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/></Relationships>',
        )
        package.writestr("word/document.xml", document_xml)
        package.writestr(
            "word/_rels/document.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rIdStyles" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
            'Target="styles.xml"/>'
            '<Relationship Id="rIdClassificationAudit" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/customXml" '
            'Target="../customXml/geolog-classification-audit.xml"/>'
            '<Relationship Id="rIdFooter" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" '
            'Target="footer.xml"/></Relationships>',
        )
        package.writestr(
            CLASSIFICATION_AUDIT_DOCX_PART,
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<classificationAudit xmlns="urn:digital-geolog:interpretation-audit:1">'
            + xml_escape(interpretation_classification_audit_json(report))
            + '</classificationAudit>',
        )
        package.writestr("word/styles.xml", _docx_styles())
        package.writestr("word/footer.xml", (report_document_control_docx_footer(None, language, width_twips=_PORTRAIT_TABLE_WIDTH_TWIPS)
             if orientation == "portrait" else report_document_control_docx_footer(None, language)))



def _gas_context_docx(
    report: HydrocarbonInterpretationReport,
    language: AppLanguage,
) -> list[str]:
    labels = {
        AppLanguage.RU: (
            "Газовый контекст интерпретации",
            "Тип газа", "Интервал", "Статус", "Влияние",
            "Измеренный TG", "Измеренные C1–C5",
            "Ручной TG / QC", "QC Δ к среднему TG",
            "Комментарий", "подтверждено",
        ),
        AppLanguage.KK: (
            "Интерпретацияның газ контексті",
            "Газ түрі", "Аралық", "Күй", "Әсер",
            "Өлшенген TG", "Өлшенген C1–C5",
            "Қолмен TG / QC", "Орташа TG-ге QC Δ",
            "Түсініктеме", "расталған",
        ),
        AppLanguage.EN: (
            "Interpretation gas context",
            "Gas type", "Interval", "Status", "Impact",
            "Measured TG", "Measured C1–C5",
            "Manual TG / QC", "QC Δ vs mean TG",
            "Comment", "confirmed",
        ),
    }[language]
    (
        title, gas_type, interval, status, impact, measured_tg, measured_components,
        manual_qc, qc_delta, comment, confirmed,
    ) = labels
    audit_by_id = {item.event_id: item for item in report.gas_context_audit}

    def stats_text(item) -> str:
        if (
            item is None
            or item.minimum is None
            or item.mean is None
            or item.maximum is None
        ):
            return "—"
        unit = f" {item.unit}" if item.unit else ""
        return (
            f"{localized_curve_name(item.mnemonic, language=language)}: "
            f"min {item.minimum:.6g}; mean {item.mean:.6g}; "
            f"max {item.maximum:.6g}{unit}"
        )

    rows: list[tuple[str, ...]] = []
    for event in report.gas_context_events:
        audit = audit_by_id.get(event.event_id)
        measured_total_text = "—"
        component_text = "—"
        delta_text = "—"
        if audit is not None:
            measured_total_text = stats_text(audit.measured_total_gas)
            if audit.measured_components:
                component_text = "; ".join(stats_text(item) for item in audit.measured_components)
            if audit.qc_delta_vs_measured_mean is not None:
                delta_text = f"{audit.qc_delta_vs_measured_mean:.6g}"
                if audit.qc_delta_unit:
                    delta_text += f" {audit.qc_delta_unit}"
        manual_text = (
            "—"
            if event.reported_total_gas is None
            else f"{event.reported_total_gas:g}"
            + (f" {event.reported_unit}" if event.reported_unit else "")
        )
        rows.append(
            (
                f"{gas_context_type_text(event.event_type, language)}; "
                f"{gas_context_identity_label(language)}: {event.event_id}",
                f"{event.top_depth:g}–{event.bottom_depth:g} {report.depth_unit}",
                confirmed,
                gas_context_impact_label(event.effective_impact, language),
                measured_total_text,
                component_text,
                manual_text,
                delta_text,
                event.comment or "—",
            )
        )
    return [
        _paragraph(title, style="Heading1"),
        _table(
            (
                gas_type, interval, status, impact, measured_tg, measured_components,
                manual_qc, qc_delta, comment,
            ),
            tuple(rows),
            widths=(1_700, 1_700, 1_200, 1_800, 2_100, 3_600, 1_700, 1_700, 2_000),
        ),
    ]

def _suppressed_candidates_docx(
    report: HydrocarbonInterpretationReport,
    language: AppLanguage,
) -> list[str]:
    labels = {
        AppLanguage.RU: (
            "Аудит подавленных автоматических кандидатов",
            "Интервал",
            "Основная кривая",
            "max robust z",
            "Автоматическая гипотеза",
            "Причина подавления / evidence",
        ),
        AppLanguage.KK: (
            "Басылған автоматты кандидаттар аудиты",
            "Аралық",
            "Негізгі қисық",
            "max robust z",
            "Автоматты гипотеза",
            "Басу себебі / evidence",
        ),
        AppLanguage.EN: (
            "Suppressed automatic candidates audit",
            "Interval",
            "Primary curve",
            "max robust z",
            "Automatic hypothesis",
            "Suppression reason / evidence",
        ),
    }[language]
    title, interval, primary, robust_z, hypothesis, reason = labels
    rows = tuple(
        (
            f"{candidate.top_depth:g}–{candidate.bottom_depth:g} {report.depth_unit}",
            localized_curve_reference(candidate.primary_mnemonic, language=language),
            f"{candidate.max_robust_z:.3f}",
            fluid_hypothesis_label(candidate, language),
            " | ".join(candidate.evidence),
        )
        for candidate in report.suppressed_candidates
    )
    return [
        _paragraph(title, style="Heading1"),
        _table(
            (interval, primary, robust_z, hypothesis, reason),
            rows,
            widths=(2_200, 2_200, 1_800, 3_000, 6_100),
        ),
    ]


def _opus_gasomer_docx(
    report: HydrocarbonInterpretationReport,
    language: AppLanguage = AppLanguage.RU,
) -> list[str]:
    section = report.opus_gasomer
    if section is None:
        return []
    labels = hydrocarbon_report_labels(language)
    curve_names = dict(section.input_curves)
    curve_units = dict(section.input_units)
    lod_text = (
        labels.lod_not_set
        if section.total_gas_lod is None
        else f"{section.total_gas_lod:.6g} {section.working_unit}"
    )
    class_word = {
        AppLanguage.RU: "класс",
        AppLanguage.KK: "класс",
        AppLanguage.EN: "class",
    }[language]
    body = [
        _paragraph(labels.opus_heading, style="Heading1"),
        _paragraph(
            f"{labels.profile}: {section.profile_id} v{section.profile_version}; "
            f"{labels.status}: {section.profile_status}. {labels.mode}: {section.calculation_mode}; "
            f"{labels.interval_source}: {section.interval_source}; "
            f"{labels.working_unit}: {section.working_unit}; "
            f"{labels.total_gas_lod}: {lod_text}."
        ),
        _table(
            (labels.input_label, labels.curve, labels.source_unit),
            tuple(
                (
                    localized_curve_reference(name, language=language),
                    localized_curve_reference(
                        curve_names.get(name, "—"),
                        language=language,
                    ),
                    curve_units.get(name, "—") or "—",
                )
                for name in ("TOTAL_GAS", "C1", "C2", "C3", "C4", "C5")
            ),
            widths=(2_600, 6_500, 6_000),
        ),
        _table(
            (labels.indicator, labels.exact_formula),
            tuple(
                (localized_curve_reference(name, language=language), formula)
                for name, formula in section.formulas
            ),
            widths=(3_000, 12_100),
        ),
    ]
    if not section.intervals:
        body.append(_paragraph(labels.no_intervals))
    for interval in section.intervals:
        detector = (
            labels.detector_not_run
            if interval.background_median is None
            else (
                f"{labels.local_background}={interval.background_median:.6g}; "
                f"{labels.peak_total_gas}={interval.peak_total_gas:.6g}; "
                f"{labels.delta_tg}={interval.delta_peak:.6g}; "
                f"{labels.max_robust_z}={interval.max_robust_z:.3f}; "
                f"{labels.max_contrast}={interval.max_contrast:.3f}"
            )
        )
        body.append(
            _paragraph(
                f"{interval.top_depth:.2f}–{interval.bottom_depth:.2f} "
                f"{report.depth_unit}: {class_word} {interval.class_code} — "
                f"{opus_report_label(f'class_{interval.class_code}', language)}; "
                f"{labels.class_support} "
                f"{interval.support_fraction * 100.0:.1f}%; "
                f"{labels.valid_rows} {interval.valid_rows}/{interval.total_rows}; {detector}."
            )
        )
        body.append(
            _table(
                (
                    labels.indicator,
                    labels.median,
                    labels.vote,
                    labels.vote_support,
                    labels.available_rows,
                    labels.votes_qc,
                ),
                tuple(
                    (
                        localized_curve_reference(item.mnemonic, language=language),
                        "—" if item.median_value is None else f"{item.median_value:.6g}",
                        f"{item.class_code} — {opus_report_label(f'class_{item.class_code}', language)}",
                        f"{item.vote_support * 100.0:.1f}%",
                        f"{item.available_rows}/{item.total_rows}",
                        ", ".join(
                            f"{code}:{count}" for code, count in item.vote_counts
                        )
                        + "; "
                        + ", ".join(
                            f"{opus_report_label(name, language)}:{count}"
                            for name, count in item.state_counts
                        ),
                    )
                    for item in interval.indicators
                ),
                widths=(2_000, 1_600, 3_100, 1_500, 1_500, 5_400),
            )
        )
    body.append(_paragraph(labels.formula_provenance))
    body.extend(_paragraph(f"• {item}") for item in section.provenance)
    body.append(_paragraph(f"• {labels.workbook_sha}: {section.source_workbook_sha256}"))
    return body


def _method_comparisons_docx(
    comparisons: tuple[MethodComparisonInterval, ...],
    language: AppLanguage,
    depth_unit: str,
) -> list[str]:
    """Show only supplied, source-backed evidence in the same terms as HTML/XLSX."""

    presentation = method_comparison_table(
        comparisons, language, depth_unit=depth_unit,
    )
    return [
        _paragraph(presentation.title, style="Heading1"),
        _paragraph(presentation.intro),
        _table(
            presentation.headings,
            tuple(row.cells for row in presentation.rows),
            widths=(1_750, 1_750, 1_900, 4_200, 4_400),
        ),
    ]


def _paragraph(text: str, *, style: str | None = None) -> str:
    style_xml = ""
    if style:
        # Section labels must stay with their first content paragraph or table.
        pagination = "<w:keepNext/><w:keepLines/>" if style in {"Title", "Heading1"} else ""
        style_xml = f'<w:pPr><w:pStyle w:val="{style}"/>{pagination}</w:pPr>'
    return f'<w:p>{style_xml}<w:r><w:t xml:space="preserve">{_xml_text(text)}</w:t></w:r></w:p>'


def _table(
    headers: tuple[str, ...],
    rows: tuple[tuple[str, ...], ...],
    *,
    widths: tuple[int, ...],
) -> str:
    if len(widths) != len(headers) or any(len(row) != len(headers) for row in rows):
        raise ValueError("Геометрия таблицы отчёта не соответствует числу колонок")
    widths = _fit_table_widths(widths)
    visual = modern_oilfield_report_profile()
    border = visual.palette.border.lstrip("#")
    strong_rule = round(visual.layout.strong_rule_pt * 8)
    thin_rule = round(visual.layout.thin_rule_pt * 8)
    grid = "".join(f'<w:gridCol w:w="{width}"/>' for width in widths)
    header = _table_row(headers, widths, header=True)
    body = "".join(_table_row(row, widths) for row in rows)
    return (
        '<w:tbl><w:tblPr>'
        f'<w:tblW w:w="{sum(widths)}" w:type="dxa"/>'
        '<w:jc w:val="center"/>'
        '<w:tblLayout w:type="fixed"/><w:tblCellMar>'
        '<w:top w:w="90" w:type="dxa"/><w:left w:w="90" w:type="dxa"/>'
        '<w:bottom w:w="90" w:type="dxa"/><w:right w:w="90" w:type="dxa"/>'
        "</w:tblCellMar><w:tblBorders>"
        f'<w:top w:val="single" w:sz="{strong_rule}" w:color="{border}"/>'
        f'<w:left w:val="single" w:sz="{strong_rule}" w:color="{border}"/>'
        f'<w:bottom w:val="single" w:sz="{strong_rule}" w:color="{border}"/>'
        f'<w:right w:val="single" w:sz="{strong_rule}" w:color="{border}"/>'
        f'<w:insideH w:val="single" w:sz="{thin_rule}" w:color="{border}"/>'
        f'<w:insideV w:val="single" w:sz="{thin_rule}" w:color="{border}"/>'
        "</w:tblBorders></w:tblPr>"
        f"<w:tblGrid>{grid}</w:tblGrid>{header}{body}</w:tbl>"
    )



def _table_row(
    values: tuple[str, ...],
    widths: tuple[int, ...],
    *,
    header: bool = False,
) -> str:
    visual = modern_oilfield_report_profile()
    size = round(visual.typography.table_pt * 2)
    text_color = visual.palette.text.lstrip("#")
    cells = []
    for value, width in zip(values, widths, strict=True):
        run_properties = (
            f'<w:rPr><w:b/><w:color w:val="{text_color}"/><w:sz w:val="{size}"/></w:rPr>'
            if header
            else f'<w:rPr><w:color w:val="{text_color}"/><w:sz w:val="{size}"/></w:rPr>'
        )
        shading = (
            f'<w:shd w:val="clear" w:fill="{visual.palette.table_header.lstrip(chr(35))}"/>'
            if header
            else ""
        )
        cells.append(
            f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>'
            f'<w:vAlign w:val="center"/>{shading}</w:tcPr>'
            '<w:p><w:pPr><w:spacing w:after="0"/></w:pPr>'
            f'<w:r>{run_properties}<w:t xml:space="preserve">'
            f"{_xml_text(value)}</w:t></w:r></w:p></w:tc>"
        )
    row_properties = (
        "<w:trPr><w:tblHeader/><w:cantSplit/></w:trPr>"
        if header
        else "<w:trPr><w:cantSplit/></w:trPr>"
    )
    return f"<w:tr>{row_properties}" + "".join(cells) + "</w:tr>"



def _xml_text(value: object) -> str:
    text = "".join(
        character
        for character in str(value)
        if character in "\t\n\r" or ord(character) >= 0x20
    )
    return xml_escape(text)


def _docx_styles() -> str:
    visual = modern_oilfield_report_profile()
    palette, typography = visual.palette, visual.typography
    styles = []
    for name, size, color, bold in (
        ("Normal", typography.body_pt, palette.text, False),
        ("Title", typography.title_pt, palette.accent, True),
        ("Heading1", typography.section_pt, palette.accent_dark, True),
    ):
        default = ' w:default="1"' if name == "Normal" else ""
        based_on = '<w:basedOn w:val="Normal"/>' if name != "Normal" else ""
        styles.append(
            f'<w:style w:type="paragraph"{default} w:styleId="{name}">'
            f'<w:name w:val="{name}"/>{based_on}<w:rPr>'
            + ("<w:b/>" if bold else "")
            + f'<w:color w:val="{color.lstrip("#")}"/>'
            + f'<w:sz w:val="{round(size * 2)}"/></w:rPr></w:style>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        + "".join(styles)
        + "</w:styles>"
    )



def _validate_dataset(
    report: HydrocarbonInterpretationReport,
    dataset: Dataset,
    *,
    language: AppLanguage = AppLanguage.RU,
) -> None:
    dataset_mismatch, invalid_sample_count = _DOCX_VALIDATION_ERRORS[language]
    if report.dataset_id != dataset.dataset_id:
        raise HydrocarbonInterpretationExportError(dataset_mismatch)
    expected_rows = dataset.active_index.values.size
    invalid_curves = tuple(
        curve.metadata.original_mnemonic
        for curve in dataset.curves.values()
        if curve.values.size != expected_rows
    )
    if invalid_curves:
        names = ", ".join(invalid_curves[:5])
        suffix = "…" if len(invalid_curves) > 5 else ""
        raise HydrocarbonInterpretationExportError(
            f"{invalid_sample_count}: {names}{suffix}"
        )


def _prepare_target(target: str | Path, suffix: str, *, overwrite: bool) -> Path:
    destination = Path(target)
    if destination.suffix.casefold() != suffix:
        destination = destination.with_suffix(suffix)
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


def _temporary_path(destination: Path) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.stem}-",
        suffix=destination.suffix,
        dir=destination.parent,
    )
    os.close(descriptor)
    return Path(name)


__all__ = [
    "HydrocarbonInterpretationExportError",
    "export_hydrocarbon_interpretation_docx",
    "export_hydrocarbon_interpretation_xlsx",
]
