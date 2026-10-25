from __future__ import annotations

from xml.etree import ElementTree as ET

from geoworkbench.printing.report_document_control import ReportDocumentControl, compact_report_footer
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.printing.docx_xml_characters import docx_xml_safe_text
from geoworkbench.services.localization import AppLanguage


_WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ET.register_namespace("w", _WORD_NAMESPACE)
_FOOTER_DETAILS_LIMIT = 96
# Fixed Word twips instead of mixing a percentage table width with twip grid columns.
# 15,000 twips fits both A4 landscape report variants (including 850-twip margins).
_FOOTER_WIDTH_TWIPS = 15_000
_FOOTER_GRID_TWIPS = (12_000, 3_000)


def _word_name(name: str) -> str:
    return f"{{{_WORD_NAMESPACE}}}{name}"


def report_document_control_docx_footer(
    control: ReportDocumentControl | None,
    language: AppLanguage,
    *, width_twips: int = _FOOTER_WIDTH_TWIPS,
) -> bytes:
    """A bounded shared Word footer; full document control belongs in the body."""
    if type(width_twips) is not int or not 1 <= width_twips <= _FOOTER_WIDTH_TWIPS:
        raise ValueError("Word footer width exceeds the print region")
    grid_widths = (_FOOTER_GRID_TWIPS if width_twips == _FOOTER_WIDTH_TWIPS
                   else (width_twips * 4 // 5, width_twips - width_twips * 4 // 5))
    visual = modern_oilfield_report_profile()
    root = ET.Element(_word_name("ftr"))
    table = ET.SubElement(root, _word_name("tbl"))
    properties = ET.SubElement(table, _word_name("tblPr"))
    ET.SubElement(properties, _word_name("tblW"), {_word_name("w"): str(width_twips), _word_name("type"): "dxa"})
    borders = ET.SubElement(properties, _word_name("tblBorders"))
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        ET.SubElement(borders, _word_name(edge), {_word_name("val"): "nil"})
    ET.SubElement(properties, _word_name("tblLayout"), {_word_name("type"): "fixed"})
    margins = ET.SubElement(properties, _word_name("tblCellMar"))
    for edge in ("top", "left", "bottom", "right"):
        ET.SubElement(margins, _word_name(edge), {_word_name("w"): "0", _word_name("type"): "dxa"})
    grid = ET.SubElement(table, _word_name("tblGrid"))
    for width in grid_widths:
        ET.SubElement(grid, _word_name("gridCol"), {_word_name("w"): str(width)})

    def row(height: int) -> ET.Element:
        result = ET.SubElement(table, _word_name("tr"))
        row_properties = ET.SubElement(result, _word_name("trPr"))
        ET.SubElement(row_properties, _word_name("cantSplit"))
        ET.SubElement(row_properties, _word_name("trHeight"),
                      {_word_name("val"): str(height), _word_name("hRule"): "exact"})
        return result

    def paragraph(parent: ET.Element, width: int, *, right: bool = False, span: bool = False) -> ET.Element:
        cell = ET.SubElement(parent, _word_name("tc"))
        cell_properties = ET.SubElement(cell, _word_name("tcPr"))
        ET.SubElement(cell_properties, _word_name("tcW"), {_word_name("w"): str(width), _word_name("type"): "dxa"})
        if span:
            ET.SubElement(cell_properties, _word_name("gridSpan"), {_word_name("val"): "2"})
        result = ET.SubElement(cell, _word_name("p"))
        paragraph_properties = ET.SubElement(result, _word_name("pPr"))
        ET.SubElement(paragraph_properties, _word_name("spacing"),
                      {_word_name("before"): "0", _word_name("after"): "0", _word_name("line"): "180",
                       _word_name("lineRule"): "exact"})
        if right:
            ET.SubElement(paragraph_properties, _word_name("jc"), {_word_name("val"): "right"})
        return result

    def text(parent: ET.Element, value: str, *, bold: bool = False) -> None:
        run = ET.SubElement(parent, _word_name("r"))
        run_properties = ET.SubElement(run, _word_name("rPr"))
        ET.SubElement(run_properties, _word_name("rFonts"), {_word_name("ascii"): "Arial", _word_name("hAnsi"): "Arial"})
        if bold:
            ET.SubElement(run_properties, _word_name("b"))
        ET.SubElement(run_properties, _word_name("color"), {_word_name("val"): visual.palette.text_muted.lstrip("#")})
        ET.SubElement(run_properties, _word_name("sz"), {_word_name("val"): str(round(visual.typography.footer_pt * 2))})
        ET.SubElement(run_properties, _word_name("szCs"), {_word_name("val"): str(round(visual.typography.footer_pt * 2))})
        node = ET.SubElement(run, _word_name("t"), {"{http://www.w3.org/XML/1998/namespace}space": "preserve"})
        node.text = docx_xml_safe_text(value)

    first_row = row(240)
    text(paragraph(first_row, grid_widths[0]), visual.brand_wordmark, bold=True)
    page = paragraph(first_row, grid_widths[1], right=True)
    page_label = {AppLanguage.RU: "Страница", AppLanguage.KK: "Бет", AppLanguage.EN: "Page"}[language]
    text(page, page_label + " ")
    for field, separator in (("PAGE", " / "), ("NUMPAGES", "")):
        node = ET.SubElement(page, _word_name("fldSimple"), {_word_name("instr"): field, _word_name("dirty"): "true"})
        text(node, "1")
        if separator:
            text(page, separator)
    details = compact_report_footer(control)
    if details:
        if len(details) > _FOOTER_DETAILS_LIMIT:
            details = details[:_FOOTER_DETAILS_LIMIT - 1].rstrip() + "…"
        text(paragraph(row(400), width_twips, span=True), details)
    # Word requires a trailing paragraph after a footer table. Keep its height
    # explicit so the 32-point table plus this anchor fits a 36-point margin gap.
    anchor = ET.SubElement(root, _word_name("p"))
    anchor_properties = ET.SubElement(anchor, _word_name("pPr"))
    ET.SubElement(anchor_properties, _word_name("spacing"),
                  {_word_name("before"): "0", _word_name("after"): "0", _word_name("line"): "20",
                   _word_name("lineRule"): "exact"})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
