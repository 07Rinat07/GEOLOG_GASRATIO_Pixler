"""Footer Word table layout must not mix percentage and twip widths."""

from xml.etree import ElementTree as ET

import pytest

from geoworkbench.printing.report_document_control import ReportDocumentControl
from geoworkbench.printing.report_document_control_docx import (
    _FOOTER_GRID_TWIPS,
    _FOOTER_WIDTH_TWIPS,
    report_document_control_docx_footer,
)
from geoworkbench.services.localization import AppLanguage


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("with_details", (False, True))
def test_footer_uses_matching_twip_grid_within_a4_printable_body(
    language: AppLanguage, with_details: bool,
) -> None:
    control = (
        ReportDocumentControl(
            title="Report",
            subtitle="Control",
            control=(),
            context=(),
            approvals=(),
            notes=(),
            footer_items=("DOC-21", "Rev 3", "Approved"),
        )
        if with_details
        else None
    )
    root = ET.fromstring(report_document_control_docx_footer(control, language))
    table = root.find(W + "tbl")
    assert table is not None
    props = table.find(W + "tblPr")
    assert props is not None
    width = props.find(W + "tblW")
    assert width is not None
    assert width.attrib[W + "type"] == "dxa"
    assert int(width.attrib[W + "w"]) == _FOOTER_WIDTH_TWIPS
    assert _FOOTER_WIDTH_TWIPS == sum(_FOOTER_GRID_TWIPS)
    assert _FOOTER_WIDTH_TWIPS < 16838 - 2 * 850
    assert props.find(W + "tblLayout").attrib[W + "type"] == "fixed"
    grid = table.find(W + "tblGrid")
    assert grid is not None
    assert tuple(int(node.attrib[W + "w"]) for node in grid) == _FOOTER_GRID_TWIPS
    rows = table.findall(W + "tr")
    assert len(rows) == 1
    first_cells = rows[0].findall(W + "tc")
    assert len(first_cells) == 2
    for cell, expected in zip(first_cells, _FOOTER_GRID_TWIPS):
        tc_width = cell.find(W + "tcPr").find(W + "tcW")
        assert tc_width.attrib[W + "type"] == "dxa"
        assert int(tc_width.attrib[W + "w"]) == expected
    if len(rows) > 1:
        detail = rows[1].find(W + "tc")
        detail_props = detail.find(W + "tcPr")
        assert detail_props.find(W + "gridSpan").attrib[W + "val"] == "2"
        assert int(detail_props.find(W + "tcW").attrib[W + "w"]) == _FOOTER_WIDTH_TWIPS
        strings = [node.text or "" for node in detail.iter(W + "t")]
        assert "DOC-21" in " ".join(strings)
    assert root.find(W + "p") is not None
