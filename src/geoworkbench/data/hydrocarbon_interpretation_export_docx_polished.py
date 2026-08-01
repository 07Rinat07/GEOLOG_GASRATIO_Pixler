from __future__ import annotations

import os
from pathlib import Path
import tempfile
import zipfile
from xml.etree import ElementTree as ET

from defusedxml.ElementTree import fromstring

from geoworkbench.data.hydrocarbon_interpretation_export import (
    export_hydrocarbon_interpretation_docx,
)
from geoworkbench.domain.models import Dataset
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
    InterpretationReportIdentity,
    default_interpretation_report_identity,
)
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
)
from geoworkbench.services.localization import AppLanguage


_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_XML_NS = "http://www.w3.org/XML/1998/namespace"
ET.register_namespace("w", _W_NS)


def export_polished_hydrocarbon_interpretation_docx(
    report: HydrocarbonInterpretationReport,
    target: str | Path,
    *,
    dataset: Dataset | None = None,
    identity: InterpretationReportIdentity | None = None,
    overwrite: bool = False,
) -> Path:
    """Export Word with a separate portrait cover and landscape report body."""

    destination = Path(target)
    if destination.suffix.casefold() != ".docx":
        destination = destination.with_suffix(".docx")
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    details = (
        identity
        or default_interpretation_report_identity(report, AppLanguage.RU)
    ).cleaned()
    source = _temporary_docx(destination, "source")
    rewritten = _temporary_docx(destination, "rewritten")
    try:
        export_hydrocarbon_interpretation_docx(
            report,
            source,
            dataset=dataset,
            overwrite=True,
        )
        _rewrite_cover(source, rewritten, report, details)
        os.replace(rewritten, destination)
    finally:
        source.unlink(missing_ok=True)
        rewritten.unlink(missing_ok=True)
    return destination


def _temporary_docx(destination: Path, label: str) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.stem}-{label}-",
        suffix=".docx",
        dir=destination.parent,
    )
    os.close(descriptor)
    return Path(name)


def _rewrite_cover(
    source: Path,
    target: Path,
    report: HydrocarbonInterpretationReport,
    identity: InterpretationReportIdentity,
) -> None:
    with (
        zipfile.ZipFile(source, "r") as input_package,
        zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as output_package,
    ):
        for item in input_package.infolist():
            data = input_package.read(item.filename)
            if item.filename == "word/document.xml":
                data = _document_with_polished_cover(data, report, identity)
            output_package.writestr(item, data)


def _document_with_polished_cover(
    xml: bytes,
    report: HydrocarbonInterpretationReport,
    identity: InterpretationReportIdentity,
) -> bytes:
    root = fromstring(xml)
    body = root.find(_q("body"))
    if body is None:
        raise RuntimeError("Word-отчёт не содержит основного раздела документа")

    children = list(body)
    first_heading = next(
        (
            index
            for index, child in enumerate(children)
            if child.tag == _q("p") and _paragraph_style(child) == "Heading1"
        ),
        None,
    )
    if first_heading is None:
        raise RuntimeError("Не удалось отделить титульный лист Word от отчёта")

    for child in children[:first_heading]:
        body.remove(child)
    for index, element in enumerate(_cover_elements(report, identity)):
        body.insert(index, element)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _paragraph_style(paragraph: ET.Element) -> str:
    style = paragraph.find(f"{_q('pPr')}/{_q('pStyle')}")
    return "" if style is None else style.get(_q("val"), "")


def _cover_elements(
    report: HydrocarbonInterpretationReport,
    identity: InterpretationReportIdentity,
) -> tuple[ET.Element, ...]:
    details = identity.cleaned()
    elements: list[ET.Element] = [
        _paragraph(
            "GEOLOG GASRATIO@Pixler",
            alignment="center",
            after=220,
            size=22,
            bold=True,
            color="174F78",
        ),
        _control_table(
            (
                ("Документ", details.document_number),
                ("Ревизия", details.revision),
                ("Статус", details.document_status),
                ("Дата отчёта", details.report_date),
            )
        ),
        _paragraph(
            details.report_title or "Отчёт по интерпретации газового каротажа",
            alignment="center",
            before=720,
            after=100,
            size=44,
            bold=True,
            color="172033",
            keep_next=True,
        ),
        _paragraph(
            details.report_subtitle,
            alignment="center",
            after=360,
            size=22,
            color="526579",
        ),
        _details_table(
            (
                ("Проект", details.project_name),
                ("Скважина", details.well_name),
                ("Месторождение / площадь", details.field_name),
                ("Местоположение", details.location),
                ("Оператор / заказчик", details.operator_name),
                ("Сервисная компания", details.contractor_name),
                ("Буровая / установка", details.rig_name),
                ("Набор данных", details.dataset_name),
                ("Интервал отчёта", details.interval),
                ("Сформирован", report.generated_at),
                ("Основная газовая кривая", report.primary_mnemonic or "—"),
                ("Порог robust z", f"{report.threshold:.2f}"),
            )
        ),
        _paragraph("", before=80, after=80, size=4),
        _approval_table(
            (
                ("Подготовил", details.prepared_by),
                ("Проверил", details.checked_by),
                ("Утвердил", details.approved_by),
            )
        ),
    ]
    notes = (
        details.confidentiality,
        details.remarks,
        "Графики, методы, перспективные интервалы и ограничения методики "
        "приведены на следующих страницах.",
    )
    elements.extend(
        _paragraph(
            note,
            alignment="center",
            before=80,
            after=30,
            size=17,
            color="526579",
        )
        for note in notes
        if note.strip()
    )
    elements.append(_portrait_section_break())
    return tuple(elements)


def _paragraph(
    text: str,
    *,
    alignment: str = "left",
    before: int = 0,
    after: int = 0,
    size: int = 20,
    bold: bool = False,
    color: str = "172033",
    keep_next: bool = False,
) -> ET.Element:
    paragraph = ET.Element(_q("p"))
    properties = ET.SubElement(paragraph, _q("pPr"))
    ET.SubElement(properties, _q("jc"), {_q("val"): alignment})
    ET.SubElement(
        properties,
        _q("spacing"),
        {_q("before"): str(before), _q("after"): str(after)},
    )
    if keep_next:
        ET.SubElement(properties, _q("keepNext"))

    run = ET.SubElement(paragraph, _q("r"))
    run_properties = ET.SubElement(run, _q("rPr"))
    ET.SubElement(
        run_properties,
        _q("rFonts"),
        {
            _q("ascii"): "Arial",
            _q("hAnsi"): "Arial",
            _q("eastAsia"): "Arial",
        },
    )
    if bold:
        ET.SubElement(run_properties, _q("b"))
    ET.SubElement(run_properties, _q("color"), {_q("val"): color})
    ET.SubElement(run_properties, _q("sz"), {_q("val"): str(size)})
    text_node = ET.SubElement(run, _q("t"))
    text_node.set(f"{{{_XML_NS}}}space", "preserve")
    text_node.text = text
    return paragraph


def _control_table(items: tuple[tuple[str, str], ...]) -> ET.Element:
    return _table(
        (
            tuple(label for label, _ in items),
            tuple(_value(value) for _, value in items),
        ),
        tuple(2_250 for _ in items),
        shaded_rows=frozenset({0}),
        centered=True,
    )


def _details_table(items: tuple[tuple[str, str], ...]) -> ET.Element:
    return _table(
        tuple((label, _value(value)) for label, value in items),
        (3_100, 5_900),
        shaded_columns=frozenset({0}),
    )


def _approval_table(items: tuple[tuple[str, str], ...]) -> ET.Element:
    return _table(
        (
            tuple(label for label, _ in items),
            tuple(_value(value) for _, value in items),
            tuple("Подпись / дата ____________________" for _ in items),
        ),
        tuple(3_000 for _ in items),
        shaded_rows=frozenset({0}),
        centered=True,
    )


def _table(
    rows: tuple[tuple[str, ...], ...],
    widths: tuple[int, ...],
    *,
    shaded_rows: frozenset[int] = frozenset(),
    shaded_columns: frozenset[int] = frozenset(),
    centered: bool = False,
) -> ET.Element:
    if not rows or any(len(row) != len(widths) for row in rows):
        raise ValueError("Геометрия титульной таблицы Word не соответствует колонкам")

    table = ET.Element(_q("tbl"))
    properties = ET.SubElement(table, _q("tblPr"))
    ET.SubElement(
        properties,
        _q("tblW"),
        {_q("w"): str(sum(widths)), _q("type"): "dxa"},
    )
    ET.SubElement(properties, _q("jc"), {_q("val"): "center"})
    ET.SubElement(properties, _q("tblLayout"), {_q("type"): "fixed"})
    margins = ET.SubElement(properties, _q("tblCellMar"))
    for side, width in (("top", 90), ("left", 100), ("bottom", 90), ("right", 100)):
        ET.SubElement(
            margins,
            _q(side),
            {_q("w"): str(width), _q("type"): "dxa"},
        )
    borders = ET.SubElement(properties, _q("tblBorders"))
    for name, size, color in (
        ("top", 8, "8DA3B8"),
        ("left", 8, "8DA3B8"),
        ("bottom", 8, "8DA3B8"),
        ("right", 8, "8DA3B8"),
        ("insideH", 5, "B8C6D4"),
        ("insideV", 5, "B8C6D4"),
    ):
        ET.SubElement(
            borders,
            _q(name),
            {_q("val"): "single", _q("sz"): str(size), _q("color"): color},
        )
    grid = ET.SubElement(table, _q("tblGrid"))
    for width in widths:
        ET.SubElement(grid, _q("gridCol"), {_q("w"): str(width)})

    for row_index, values in enumerate(rows):
        row = ET.SubElement(table, _q("tr"))
        row_properties = ET.SubElement(row, _q("trPr"))
        ET.SubElement(row_properties, _q("cantSplit"))
        for column_index, (value, width) in enumerate(zip(values, widths, strict=True)):
            shaded = row_index in shaded_rows or column_index in shaded_columns
            cell = ET.SubElement(row, _q("tc"))
            cell_properties = ET.SubElement(cell, _q("tcPr"))
            ET.SubElement(
                cell_properties,
                _q("tcW"),
                {_q("w"): str(width), _q("type"): "dxa"},
            )
            ET.SubElement(cell_properties, _q("vAlign"), {_q("val"): "center"})
            if shaded:
                ET.SubElement(
                    cell_properties,
                    _q("shd"),
                    {_q("val"): "clear", _q("fill"): "EAF1F7"},
                )
            cell.append(
                _paragraph(
                    value,
                    alignment="center" if centered else "left",
                    before=70,
                    after=70,
                    size=18,
                    bold=shaded,
                )
            )
    return table


def _portrait_section_break() -> ET.Element:
    paragraph = ET.Element(_q("p"))
    properties = ET.SubElement(paragraph, _q("pPr"))
    section = ET.SubElement(properties, _q("sectPr"))
    ET.SubElement(section, _q("type"), {_q("val"): "nextPage"})
    ET.SubElement(
        section,
        _q("pgSz"),
        {_q("w"): "11906", _q("h"): "16838"},
    )
    ET.SubElement(
        section,
        _q("pgMar"),
        {
            _q("top"): "1134",
            _q("right"): "1134",
            _q("bottom"): "1134",
            _q("left"): "1134",
            _q("header"): "708",
            _q("footer"): "708",
            _q("gutter"): "0",
        },
    )
    return paragraph


def _value(text: str) -> str:
    return text.strip() or "—"


def _q(tag: str) -> str:
    return f"{{{_W_NS}}}{tag}"


__all__ = ["export_polished_hydrocarbon_interpretation_docx"]
