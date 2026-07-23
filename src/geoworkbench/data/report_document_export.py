from __future__ import annotations

import html
import os
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape as xml_escape

import numpy as np

from geoworkbench.data.number_format import format_decimal_number
from geoworkbench.domain.models import CurveData, Dataset, DatasetIndex, IndexRole, IndexType
from geoworkbench.services.coverage import ChannelAvailability, ChannelCoverage
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.parameter_labels import localized_curve_name
from geoworkbench.services.report_definition import ResolvedReportDefinition
from geoworkbench.services.text_normalization import clean_display_text, clean_mnemonic


REPORT_DOCUMENT_SCHEMA_VERSION = 1
MISSING_CELL = "—"
UNAVAILABLE_CELL = "#N/A"


class ReportDocumentExportError(RuntimeError):
    """Raised when a DOCX or HTML report cannot be serialized."""


@dataclass(frozen=True, slots=True)
class ReportDocumentColumn:
    key: str
    title: str
    technical_name: str
    unit: str
    availability: ChannelAvailability | None
    coverage: ChannelCoverage | None

    @property
    def header(self) -> str:
        unit = f" [{self.unit}]" if self.unit else ""
        return f"{self.title} · {self.technical_name}{unit}"


@dataclass(frozen=True, slots=True)
class ReportDocumentModel:
    title: str
    dataset_name: str
    language: AppLanguage
    definition_sha256: str
    index_id: str
    interval_start: str
    interval_end: str
    sample_count: int
    columns: tuple[ReportDocumentColumn, ...]
    rows: tuple[tuple[str, ...], ...]
    schema_version: int = REPORT_DOCUMENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != REPORT_DOCUMENT_SCHEMA_VERSION:
            raise ValueError("Неподдерживаемая версия report document model")
        if not self.columns:
            raise ValueError("Report document model должен содержать колонки")
        if len(self.rows) != self.sample_count:
            raise ValueError("Количество строк document model не совпадает с sample_count")
        width = len(self.columns)
        if any(len(row) != width for row in self.rows):
            raise ValueError("Строки document model имеют разную ширину")


_LABELS: dict[AppLanguage, dict[str, str]] = {
    AppLanguage.RU: {
        "report": "Инженерный отчёт",
        "metadata": "Параметры отчёта",
        "coverage": "Покрытие каналов",
        "data": "Данные",
        "dataset": "Набор данных",
        "interval": "Интервал",
        "samples": "Отсчётов",
        "definition": "ReportDefinition SHA-256",
        "channel": "Канал",
        "availability": "Доступность",
        "observed": "Наблюдений",
        "zeros": "Нулей",
        "missing": "Пропусков",
        "coverage_percent": "Покрытие, %",
        "available": "доступен",
        "unavailable": "недоступен",
        "legend": (
            "Обозначения: 0 — измеренный ноль; — — пропущенный отсчёт; "
            "#N/A — канал недоступен."
        ),
        "unresolved": "Неопределённый канал",
    },
    AppLanguage.KK: {
        "report": "Инженерлік есеп",
        "metadata": "Есеп параметрлері",
        "coverage": "Арналардың қамтылуы",
        "data": "Деректер",
        "dataset": "Деректер жинағы",
        "interval": "Аралық",
        "samples": "Есептер саны",
        "definition": "ReportDefinition SHA-256",
        "channel": "Арна",
        "availability": "Қолжетімділік",
        "observed": "Бақылаулар",
        "zeros": "Нөлдер",
        "missing": "Өткізіп алынғандар",
        "coverage_percent": "Қамту, %",
        "available": "қолжетімді",
        "unavailable": "қолжетімсіз",
        "legend": "Белгілер: 0 — өлшенген нөл; — — өткізіп алынған есеп; #N/A — арна қолжетімсіз.",
        "unresolved": "Анықталмаған арна",
    },
    AppLanguage.EN: {
        "report": "Engineering report",
        "metadata": "Report parameters",
        "coverage": "Channel coverage",
        "data": "Data",
        "dataset": "Dataset",
        "interval": "Interval",
        "samples": "Samples",
        "definition": "ReportDefinition SHA-256",
        "channel": "Channel",
        "availability": "Availability",
        "observed": "Observed",
        "zeros": "Zeros",
        "missing": "Missing",
        "coverage_percent": "Coverage, %",
        "available": "available",
        "unavailable": "unavailable",
        "legend": "Legend: 0 — observed zero; — — missing sample; #N/A — channel unavailable.",
        "unresolved": "Unresolved channel",
    },
}


def build_report_document_model(
    dataset: Dataset,
    report: ResolvedReportDefinition,
    *,
    language: AppLanguage | str | None = None,
) -> ReportDocumentModel:
    """Build one deterministic document model from an already resolved report."""

    if dataset.dataset_id != report.definition.dataset_id:
        raise ReportDocumentExportError("Resolved report относится к другому dataset")
    try:
        index = dataset.indexes[report.interval.index_id]
    except KeyError as exc:
        raise ReportDocumentExportError(
            f"Индекс отчёта не найден: {report.interval.index_id}"
        ) from exc

    export_language = AppLanguage(language or report.definition.language)
    labels = _LABELS[export_language]
    indices = np.asarray(report.interval.indices, dtype=np.int64)
    coverage_by_key = {item.channel_key: item for item in report.coverage}
    coverage_by_mnemonic = {item.mnemonic.casefold(): item for item in report.coverage}

    columns: list[ReportDocumentColumn] = [
        ReportDocumentColumn(
            key=f"index:{index.index_id}",
            title=_index_title(index, export_language),
            technical_name=("DEPTH" if index.role is IndexRole.DEPTH else index.mnemonic),
            unit=_index_unit(index),
            availability=None,
            coverage=None,
        )
    ]
    curves: list[CurveData] = []
    for curve_id in report.curve_ids:
        try:
            curve = dataset.curves[curve_id]
        except KeyError as exc:
            raise ReportDocumentExportError(f"Кривая отчёта не найдена: {curve_id}") from exc
        curves.append(curve)
        metadata = curve.metadata
        canonical = clean_mnemonic(metadata.canonical_mnemonic or metadata.original_mnemonic)
        friendly = localized_curve_name(
            canonical,
            description=clean_display_text(metadata.description or ""),
            unit=clean_display_text(metadata.unit or ""),
            language=export_language,
        ).strip()
        if not friendly:
            friendly = labels["unresolved"]
        columns.append(
            ReportDocumentColumn(
                key=curve_id,
                title=friendly,
                technical_name=clean_mnemonic(metadata.original_mnemonic),
                unit=clean_display_text(metadata.unit or ""),
                availability=ChannelAvailability.AVAILABLE,
                coverage=coverage_by_key.get(curve_id),
            )
        )

    unavailable = tuple(report.unavailable_channel_mnemonics)
    for mnemonic in unavailable:
        coverage = coverage_by_mnemonic.get(mnemonic.casefold())
        columns.append(
            ReportDocumentColumn(
                key=f"unavailable:{mnemonic.casefold()}",
                title=labels["unresolved"],
                technical_name=mnemonic,
                unit="",
                availability=ChannelAvailability.UNAVAILABLE,
                coverage=coverage,
            )
        )

    rows: list[tuple[str, ...]] = []
    index_values = np.asarray(index.values)
    for row_index in indices:
        values: list[str] = [_format_index_value(index, index_values[int(row_index)])]
        for curve in curves:
            values.append(_format_curve_value(float(curve.values[int(row_index)])))
        values.extend(UNAVAILABLE_CELL for _mnemonic in unavailable)
        rows.append(tuple(values))

    return ReportDocumentModel(
        title=report.definition.name or labels["report"],
        dataset_name=clean_display_text(dataset.name),
        language=export_language,
        definition_sha256=report.definition.content_sha256,
        index_id=index.index_id,
        interval_start=str(report.interval.start),
        interval_end=str(report.interval.end),
        sample_count=report.interval.sample_count,
        columns=tuple(columns),
        rows=tuple(rows),
    )


def export_report_html(
    dataset: Dataset,
    target: str | Path,
    report: ResolvedReportDefinition,
    *,
    overwrite: bool = False,
    language: AppLanguage | str | None = None,
) -> Path:
    destination = Path(target)
    _validate_destination(destination, {".html", ".htm"}, overwrite)
    model = build_report_document_model(dataset, report, language=language)
    payload = _html_document(model).encode("utf-8")
    return _write_atomic_bytes(destination, payload, "HTML")


def export_report_docx(
    dataset: Dataset,
    target: str | Path,
    report: ResolvedReportDefinition,
    *,
    overwrite: bool = False,
    language: AppLanguage | str | None = None,
) -> Path:
    destination = Path(target)
    _validate_destination(destination, {".docx"}, overwrite)
    model = build_report_document_model(dataset, report, language=language)
    temporary = _temporary_path(destination)
    try:
        _write_docx_package(temporary, model)
        os.replace(temporary, destination)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        if isinstance(exc, (FileExistsError, ReportDocumentExportError)):
            raise
        raise ReportDocumentExportError(f"Не удалось экспортировать DOCX: {destination}") from exc
    return destination


def _html_document(model: ReportDocumentModel) -> str:
    labels = _LABELS[model.language]
    coverage_rows = "".join(_html_coverage_row(column, labels) for column in model.columns[1:])
    header = "".join(f"<th>{html.escape(column.header)}</th>" for column in model.columns)
    body_rows: list[str] = []
    for row in model.rows:
        cells: list[str] = []
        for value in row:
            state = _cell_state(value)
            cells.append(
                f'<td class="state-{state}" data-state="{state}">{html.escape(value)}</td>'
            )
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    metadata = (
        _html_meta_row(labels["dataset"], model.dataset_name)
        + _html_meta_row(
            labels["interval"], f"{model.interval_start} — {model.interval_end}"
        )
        + _html_meta_row(labels["samples"], str(model.sample_count))
        + _html_meta_row(labels["definition"], model.definition_sha256)
    )
    return f"""<!doctype html>
<html lang="{model.language.value}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(model.title)}</title>
<style>
:root {{ color-scheme: light; font-family: Arial, Helvetica, sans-serif; }}
body {{ margin: 24px; color: #17202a; background: #fff; }}
h1 {{ margin: 0 0 18px; font-size: 24px; }}
h2 {{ margin: 24px 0 10px; font-size: 17px; }}
table {{ width: 100%; border-collapse: collapse; margin: 8px 0 18px; }}
th, td {{ border: 1px solid #8796a5; padding: 6px 8px; text-align: left; vertical-align: top; }}
th {{ background: #e8f0f7; font-weight: 700; }}
.meta {{ width: auto; min-width: 55%; }}
.meta th {{ width: 220px; }}
.data {{ font-variant-numeric: tabular-nums; font-size: 12px; }}
.state-missing {{ color: #6b7280; text-align: center; }}
.state-unavailable {{ color: #9b1c1c; background: #fff1f1; text-align: center; font-weight: 700; }}
.state-zero {{ color: #111827; font-weight: 700; }}
.legend {{ padding: 10px 12px; border-left: 4px solid #507aa3; background: #f5f8fb; }}
.hash {{ font-family: Consolas, monospace; word-break: break-all; }}
@media print {{
  body {{ margin: 10mm; }}
  table {{ break-inside: auto; }}
  tr {{ break-inside: avoid; }}
  thead {{ display: table-header-group; }}
}}
</style>
</head>
<body>
<h1>{html.escape(model.title)}</h1>
<h2>{html.escape(labels['metadata'])}</h2>
<table class="meta"><tbody>{metadata}</tbody></table>
<h2>{html.escape(labels['coverage'])}</h2>
<table class="coverage"><thead><tr>
<th>{html.escape(labels['channel'])}</th><th>{html.escape(labels['availability'])}</th>
<th>{html.escape(labels['observed'])}</th><th>{html.escape(labels['zeros'])}</th>
<th>{html.escape(labels['missing'])}</th><th>{html.escape(labels['coverage_percent'])}</th>
</tr></thead><tbody>{coverage_rows}</tbody></table>
<p class="legend">{html.escape(labels['legend'])}</p>
<h2>{html.escape(labels['data'])}</h2>
<table class="data"><thead><tr>{header}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>
</body>
</html>
"""


def _html_meta_row(label: str, value: str) -> str:
    css = ' class="hash"' if "SHA-256" in label else ""
    return f"<tr><th>{html.escape(label)}</th><td{css}>{html.escape(value)}</td></tr>"


def _html_coverage_row(column: ReportDocumentColumn, labels: dict[str, str]) -> str:
    coverage = column.coverage
    availability = column.availability or ChannelAvailability.AVAILABLE
    if coverage is None:
        observed = zero = missing = 0
        percent = "0"
    else:
        observed = coverage.observed_count
        zero = coverage.zero_count
        missing = coverage.missing_count
        percent = format_decimal_number(coverage.coverage_percent)
    availability_text = (
        labels["available"]
        if availability is ChannelAvailability.AVAILABLE
        else labels["unavailable"]
    )
    return (
        "<tr>"
        f"<td>{html.escape(column.header)}</td>"
        f"<td>{html.escape(availability_text)}</td>"
        f"<td>{observed}</td><td>{zero}</td><td>{missing}</td><td>{percent}</td>"
        "</tr>"
    )


def _write_docx_package(path: Path, model: ReportDocumentModel) -> None:
    entries = {
        "[Content_Types].xml": _docx_content_types(),
        "_rels/.rels": _docx_package_relationships(),
        "docProps/app.xml": _docx_app_properties(),
        "docProps/core.xml": _docx_core_properties(model),
        "word/_rels/document.xml.rels": _docx_document_relationships(),
        "word/document.xml": _docx_document(model),
        "word/styles.xml": _docx_styles(),
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, entries[name].encode("utf-8"))


def _docx_document(model: ReportDocumentModel) -> str:
    labels = _LABELS[model.language]
    metadata_rows = (
        (labels["dataset"], model.dataset_name),
        (labels["interval"], f"{model.interval_start} — {model.interval_end}"),
        (labels["samples"], str(model.sample_count)),
        (labels["definition"], model.definition_sha256),
    )
    coverage_rows: list[tuple[str, ...]] = [
        (
            labels["channel"],
            labels["availability"],
            labels["observed"],
            labels["zeros"],
            labels["missing"],
            labels["coverage_percent"],
        )
    ]
    for column in model.columns[1:]:
        coverage = column.coverage
        availability = column.availability or ChannelAvailability.AVAILABLE
        coverage_rows.append(
            (
                column.header,
                labels["available"]
                if availability is ChannelAvailability.AVAILABLE
                else labels["unavailable"],
                str(coverage.observed_count if coverage else 0),
                str(coverage.zero_count if coverage else 0),
                str(coverage.missing_count if coverage else 0),
                format_decimal_number(coverage.coverage_percent if coverage else 0.0),
            )
        )
    data_rows: list[tuple[str, ...]] = [tuple(column.header for column in model.columns)]
    data_rows.extend(model.rows)
    body = (
        _w_paragraph(model.title, style="Title")
        + _w_paragraph(labels["metadata"], style="Heading1")
        + _w_table(metadata_rows, header=False)
        + _w_paragraph(labels["coverage"], style="Heading1")
        + _w_table(coverage_rows, header=True)
        + _w_paragraph(labels["legend"])
        + _w_paragraph(labels["data"], style="Heading1")
        + _w_table(data_rows, header=True)
        + '<w:sectPr><w:pgSz w:w="16838" w:h="11906" w:orient="landscape"/>'
        '<w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720" '
        'w:header="360" w:footer="360" w:gutter="0"/></w:sectPr>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )


def _w_paragraph(text: str, *, style: str | None = None) -> str:
    properties = f'<w:pPr><w:pStyle w:val="{xml_escape(style)}"/></w:pPr>' if style else ""
    return (
        f"<w:p>{properties}<w:r><w:t xml:space=\"preserve\">"
        f"{xml_escape(text)}"
        "</w:t></w:r></w:p>"
    )


def _w_table(rows: Iterable[tuple[str, ...]], *, header: bool) -> str:
    values = tuple(rows)
    if not values:
        return ""
    width = len(values[0])
    if any(len(row) != width for row in values):
        raise ReportDocumentExportError("DOCX table содержит строки разной ширины")
    borders = (
        '<w:tblPr><w:tblW w:w="0" w:type="auto"/><w:tblBorders>'
        '<w:top w:val="single" w:sz="4" w:color="8796A5"/>'
        '<w:left w:val="single" w:sz="4" w:color="8796A5"/>'
        '<w:bottom w:val="single" w:sz="4" w:color="8796A5"/>'
        '<w:right w:val="single" w:sz="4" w:color="8796A5"/>'
        '<w:insideH w:val="single" w:sz="4" w:color="B7C3CE"/>'
        '<w:insideV w:val="single" w:sz="4" w:color="B7C3CE"/>'
        '</w:tblBorders></w:tblPr>'
    )
    result = ["<w:tbl>", borders]
    for row_index, row in enumerate(values):
        result.append("<w:tr>")
        for value in row:
            shading = (
                '<w:tcPr><w:shd w:val="clear" w:color="auto" w:fill="D9EAF7"/></w:tcPr>'
                if header and row_index == 0
                else "<w:tcPr/>"
            )
            bold = "<w:rPr><w:b/></w:rPr>" if header and row_index == 0 else ""
            result.append(
                f"<w:tc>{shading}<w:p><w:r>{bold}<w:t xml:space=\"preserve\">"
                f"{xml_escape(value)}"
                "</w:t></w:r></w:p></w:tc>"
            )
        result.append("</w:tr>")
    result.append("</w:tbl>")
    return "".join(result)


def _docx_content_types() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.'
        'document.main+xml"/>'
        '<Override PartName="/word/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        '<Override PartName="/docProps/core.xml" '
        'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        '</Types>'
    )


def _docx_package_relationships() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/package/2006/relationships/'
        'metadata/core-properties" '
        'Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
        'extended-properties" '
        'Target="docProps/app.xml"/>'
        '</Relationships>'
    )


def _docx_document_relationships() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
        '</Relationships>'
    )


def _docx_styles() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
        '<w:name w:val="Normal"/><w:rPr>'
        '<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
        '<w:sz w:val="20"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/>'
        '<w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
        '<w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="26"/></w:rPr></w:style>'
        '</w:styles>'
    )


def _docx_core_properties(model: ReportDocumentModel) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties '
        'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:title>{xml_escape(model.title)}</dc:title>"
        '<dc:creator>GEOLOG GASRATIO@Pixler</dc:creator>'
        f"<dc:language>{model.language.value}</dc:language>"
        f"<cp:keywords>{model.definition_sha256}</cp:keywords>"
        '</cp:coreProperties>'
    )


def _docx_app_properties() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties '
        'xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        '<Application>GEOLOG GASRATIO@Pixler</Application><AppVersion>0.7</AppVersion>'
        '</Properties>'
    )


def _index_title(index: DatasetIndex, language: AppLanguage) -> str:
    names = {
        AppLanguage.RU: {"depth": "Глубина", "time": "Дата и время", "other": "Индекс"},
        AppLanguage.KK: {"depth": "Тереңдік", "time": "Күні мен уақыты", "other": "Индекс"},
        AppLanguage.EN: {"depth": "Depth", "time": "Date and time", "other": "Index"},
    }
    role = index.role.value
    return names[language].get(role, names[language]["other"])


def _index_unit(index: DatasetIndex) -> str:
    if index.index_type is IndexType.DATETIME:
        return index.timezone or "UTC"
    return clean_display_text(index.unit or "")


def _format_index_value(index: DatasetIndex, value: object) -> str:
    if index.index_type is IndexType.DATETIME:
        normalized = np.datetime64(value, "ns")
        if np.isnat(normalized):
            return MISSING_CELL
        return np.datetime_as_string(normalized, unit="ms")
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return MISSING_CELL
    return MISSING_CELL if not np.isfinite(numeric) else format_decimal_number(numeric)


def _format_curve_value(value: float) -> str:
    if not np.isfinite(value):
        return MISSING_CELL
    return format_decimal_number(value)


def _cell_state(value: str) -> str:
    if value == UNAVAILABLE_CELL:
        return "unavailable"
    if value == MISSING_CELL:
        return "missing"
    try:
        return "zero" if float(value) == 0.0 else "value"
    except ValueError:
        return "value"


def _validate_destination(destination: Path, suffixes: set[str], overwrite: bool) -> None:
    if destination.suffix.casefold() not in suffixes:
        raise ReportDocumentExportError(
            "Неподдерживаемое расширение document export: " + destination.suffix
        )
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)


def _temporary_path(destination: Path) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(descriptor)
    return Path(name)


def _write_atomic_bytes(destination: Path, payload: bytes, label: str) -> Path:
    temporary = _temporary_path(destination)
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, destination)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        if isinstance(exc, FileExistsError):
            raise
        raise ReportDocumentExportError(
            f"Не удалось экспортировать {label}: {destination}"
        ) from exc
    return destination
