from __future__ import annotations

import os
from pathlib import Path
from collections.abc import Callable
import tempfile
import zipfile
from xml.sax.saxutils import escape as xml_escape


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


class HydrocarbonInterpretationExportError(RuntimeError):
    pass


def export_hydrocarbon_interpretation_xlsx(
    report: HydrocarbonInterpretationReport,
    dataset: Dataset,
    target: str | Path,
    *,
    language: AppLanguage = AppLanguage.RU,
    overwrite: bool = False,
    progress: Callable[[str, int, int], None] | None = None,
) -> Path:
    """Export the single readable workbook used by every interpretation workflow."""

    from geoworkbench.data.hydrocarbon_interpretation_export_readable import (
        export_readable_hydrocarbon_interpretation_xlsx,
    )

    return export_readable_hydrocarbon_interpretation_xlsx(
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
    overwrite: bool = False,
) -> Path:
    if dataset is not None:
        _validate_dataset(report, dataset)
    destination = _prepare_target(target, ".docx", overwrite=overwrite)
    temporary = _temporary_path(destination)
    try:
        _write_docx(temporary, report, dataset, language)
        os.replace(temporary, destination)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        if isinstance(exc, (FileExistsError, HydrocarbonInterpretationExportError)):
            raise
        raise HydrocarbonInterpretationExportError(
            f"Не удалось экспортировать Word: {destination}"
        ) from exc
    return destination


def _write_docx(
    path: Path,
    report: HydrocarbonInterpretationReport,
    dataset: Dataset | None,
    language: AppLanguage,
) -> None:
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
        _paragraph(f"{labels.generated}: {report.generated_at}"),
        _paragraph(f"{labels.primary_gas_curve}: {report.primary_mnemonic or '—'}"),
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
                    method.method,
                    labels.available if method.available else labels.no_data,
                    ", ".join(method.available_mnemonics) or labels.no_data,
                    method.calculation or "—",
                    method.source,
                )
                for method in report.methods
            ),
            widths=(2_400, 1_000, 2_200, 4_700, 4_800),
        ),
    ]
    if report.opus_gasomer is not None:
        body.extend(_opus_gasomer_docx(report, language))
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
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        + "".join(body)
        + '<w:sectPr><w:pgSz w:w="16838" w:h="11906" w:orient="landscape"/>'
        '<w:pgMar w:top="850" w:right="850" w:bottom="850" w:left="850" '
        'w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>'
        "</w:body></w:document>"
    )
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
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>',
        )
        package.writestr("word/styles.xml", _docx_styles())


def _opus_gasomer_docx(
    report: HydrocarbonInterpretationReport,
    language: AppLanguage,
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
                    name,
                    curve_names.get(name, "—"),
                    curve_units.get(name, "—") or "—",
                )
                for name in ("TOTAL_GAS", "C1", "C2", "C3", "C4", "C5")
            ),
            widths=(2_600, 6_500, 6_000),
        ),
        _table(
            (labels.indicator, labels.exact_formula),
            tuple(section.formulas),
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
                f"{report.depth_unit}: {labels.class_label} {interval.class_code} — "
                f"{interval.class_label}; {labels.class_support} "
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
                        item.mnemonic,
                        "—" if item.median_value is None else f"{item.median_value:.6g}",
                        f"{item.class_code} — {item.class_label}",
                        f"{item.vote_support * 100.0:.1f}%",
                        f"{item.available_rows}/{item.total_rows}",
                        ", ".join(
                            f"{code}:{count}" for code, count in item.vote_counts
                        )
                        + "; "
                        + ", ".join(
                            f"{name}:{count}" for name, count in item.state_counts
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


def _paragraph(text: str, *, style: str | None = None) -> str:
    style_xml = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f'<w:p>{style_xml}<w:r><w:t xml:space="preserve">{_xml_text(text)}</w:t></w:r></w:p>'


def _table(
    headers: tuple[str, ...],
    rows: tuple[tuple[str, ...], ...],
    *,
    widths: tuple[int, ...],
) -> str:
    if len(widths) != len(headers) or any(len(row) != len(headers) for row in rows):
        raise ValueError("Геометрия таблицы отчёта не соответствует числу колонок")
    grid = "".join(f'<w:gridCol w:w="{width}"/>' for width in widths)
    header = _table_row(headers, widths, header=True)
    body = "".join(_table_row(row, widths) for row in rows)
    return (
        '<w:tbl><w:tblPr><w:tblW w:w="15100" w:type="dxa"/>'
        '<w:tblLayout w:type="fixed"/><w:tblCellMar>'
        '<w:top w:w="90" w:type="dxa"/><w:left w:w="90" w:type="dxa"/>'
        '<w:bottom w:w="90" w:type="dxa"/><w:right w:w="90" w:type="dxa"/>'
        '</w:tblCellMar><w:tblBorders>'
        '<w:top w:val="single" w:sz="6" w:color="8290A3"/>'
        '<w:left w:val="single" w:sz="6" w:color="8290A3"/>'
        '<w:bottom w:val="single" w:sz="6" w:color="8290A3"/>'
        '<w:right w:val="single" w:sz="6" w:color="8290A3"/>'
        '<w:insideH w:val="single" w:sz="4" w:color="8290A3"/>'
        '<w:insideV w:val="single" w:sz="4" w:color="8290A3"/>'
        "</w:tblBorders></w:tblPr>"
        f"<w:tblGrid>{grid}</w:tblGrid>{header}{body}</w:tbl>"
    )


def _table_row(
    values: tuple[str, ...],
    widths: tuple[int, ...],
    *,
    header: bool = False,
) -> str:
    cells = []
    for value, width in zip(values, widths, strict=True):
        run_properties = (
            '<w:rPr><w:b/><w:sz w:val="18"/></w:rPr>'
            if header
            else '<w:rPr><w:sz w:val="18"/></w:rPr>'
        )
        shading = '<w:shd w:val="clear" w:fill="DCE8F4"/>' if header else ""
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
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
        '<w:name w:val="Normal"/><w:rPr><w:sz w:val="20"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Title">'
        '<w:name w:val="Title"/><w:basedOn w:val="Normal"/>'
        '<w:rPr><w:b/><w:sz w:val="34"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading1">'
        '<w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>'
        '<w:rPr><w:b/><w:sz w:val="26"/></w:rPr></w:style>'
        '<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/>'
        '<w:tblPr><w:tblBorders>'
        '<w:top w:val="single" w:sz="4" w:color="808080"/>'
        '<w:left w:val="single" w:sz="4" w:color="808080"/>'
        '<w:bottom w:val="single" w:sz="4" w:color="808080"/>'
        '<w:right w:val="single" w:sz="4" w:color="808080"/>'
        '<w:insideH w:val="single" w:sz="4" w:color="808080"/>'
        '<w:insideV w:val="single" w:sz="4" w:color="808080"/>'
        "</w:tblBorders></w:tblPr></w:style></w:styles>"
    )


def _validate_dataset(report: HydrocarbonInterpretationReport, dataset: Dataset) -> None:
    if report.dataset_id != dataset.dataset_id:
        raise HydrocarbonInterpretationExportError("Отчёт относится к другому набору данных")
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
            f"Кривые с неверным числом отсчётов: {names}{suffix}"
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
