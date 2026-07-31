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
from geoworkbench.services.localization import AppLanguage


class HydrocarbonInterpretationExportError(RuntimeError):
    pass


def export_hydrocarbon_interpretation_xlsx(
    report: HydrocarbonInterpretationReport,
    dataset: Dataset,
    target: str | Path,
    *,
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
        overwrite=overwrite,
        progress=progress,
    )


def export_hydrocarbon_interpretation_docx(
    report: HydrocarbonInterpretationReport,
    target: str | Path,
    *,
    dataset: Dataset | None = None,
    overwrite: bool = False,
) -> Path:
    if dataset is not None:
        _validate_dataset(report, dataset)
    destination = _prepare_target(target, ".docx", overwrite=overwrite)
    temporary = _temporary_path(destination)
    try:
        _write_docx(temporary, report, dataset)
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
) -> None:
    statistics: tuple[CandidateIntervalGasStatistics | None, ...] = tuple(
        build_candidate_interval_statistics(dataset, candidate) if dataset is not None else None
        for candidate in report.candidates
    )
    body: list[str] = [
        _paragraph("Отчёт по интерпретации газового каротажа", style="Title"),
        _paragraph(f"Проект: {report.project_name}"),
        _paragraph(f"Скважина: {report.well_name}"),
        _paragraph(f"Набор данных: {report.dataset_name}"),
        _paragraph(f"Сформирован: {report.generated_at}"),
        _paragraph(f"Основная газовая кривая: {report.primary_mnemonic or '—'}"),
        _paragraph(f"Порог robust z: {report.threshold:.2f}"),
        _paragraph("Методы и доступность", style="Heading1"),
        _table(
            ("Метод", "Статус", "Использованные данные", "Источник"),
            tuple(
                (
                    method.method,
                    "доступен" if method.available else "нет данных",
                    ", ".join(method.available_mnemonics) or "нет данных",
                    method.source,
                )
                for method in report.methods
            ),
            widths=(3_800, 1_500, 3_500, 6_300),
        ),
        _paragraph("Перспективные интервалы УВ-проявлений", style="Heading1"),
    ]
    if report.candidates:
        body.append(
            _table(
                (
                    "Интервал",
                    "Сила аномалии",
                    "Предварительная интерпретация",
                    "Абсолютный газ: мин / среднее / макс",
                    "Основание",
                ),
                tuple(
                    (
                        f"{candidate.top_depth:.2f}–{candidate.bottom_depth:.2f} {report.depth_unit}",
                        {"low": "низкая", "medium": "средняя", "high": "высокая"}.get(
                            candidate.anomaly_strength,
                            candidate.anomaly_strength,
                        ),
                        fluid_hypothesis_label(candidate, AppLanguage.RU),
                        absolute_gas_components_summary(item.components, AppLanguage.RU)
                        if item is not None
                        else "нет данных",
                        candidate_evidence_summary(candidate),
                    )
                    for candidate, item in zip(report.candidates, statistics, strict=True)
                ),
                widths=(2_100, 1_600, 3_000, 5_000, 3_400),
            )
        )
    else:
        body.append(_paragraph("Перспективные интервалы по выбранному порогу не найдены."))

    body.append(_paragraph("Интерпретация по интервалам", style="Heading1"))
    if report.candidates:
        for candidate, item in zip(report.candidates, statistics, strict=True):
            basis = fluid_hypothesis_basis(candidate, AppLanguage.RU)
            if item is not None:
                basis = enhanced_fluid_hypothesis_basis(
                    basis,
                    candidate,
                    item,
                    AppLanguage.RU,
                )
            body.append(
                _paragraph(
                    f"{candidate.top_depth:.2f}–{candidate.bottom_depth:.2f} "
                    f"{report.depth_unit}: "
                    f"{fluid_hypothesis_label(candidate, AppLanguage.RU)}. {basis}"
                )
            )
    else:
        body.append(_paragraph("Перспективные интервалы по выбранному порогу не найдены."))

    body.append(_paragraph("Интервалы, подтверждённые геологом", style="Heading1"))
    if report.manual_intervals:
        body.append(
            _table(
                ("Интерпретация", "Интервал", "Тип", "Подпись", "Комментарий"),
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
        body.append(_paragraph("Подтверждённые геологом интервалы пока не заполнены."))
    body.append(_paragraph("Ограничения методики", style="Heading1"))
    body.extend(_paragraph(f"• {warning}") for warning in report.warnings)
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
