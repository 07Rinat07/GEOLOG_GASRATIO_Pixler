"""PRINT-STYLE-01: preserve operator-entered line breaks and tabs in Word."""

from __future__ import annotations

from dataclasses import replace
from xml.etree import ElementTree as ET
import zipfile

import pytest

from geoworkbench.data.hydrocarbon_interpretation_export import (
    _paragraph as ordinary_paragraph,
    _table_row,
    export_hydrocarbon_interpretation_docx,
)
from geoworkbench.data.hydrocarbon_interpretation_export_docx_polished import (
    _paragraph as polished_paragraph,
    export_polished_hydrocarbon_interpretation_docx,
)
from geoworkbench.printing.docx_xml_characters import docx_word_text_parts
from geoworkbench.services.localization import AppLanguage
from test_interpretation_report_identity import _manual_identity, _report


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
SOURCE = "Известняк & <плотный>\r\nЛБА\t2-бг\nКальцит\r97 % 🛢\x00\ud800"
EXPECTED = (
    ("text", "Известняк & <плотный>"),
    ("break", ""),
    ("text", "ЛБА"),
    ("tab", ""),
    ("text", "2-бг"),
    ("break", ""),
    ("text", "Кальцит"),
    ("break", ""),
    ("text", "97 % 🛢"),
)


def _run_parts(run: ET.Element) -> tuple[tuple[str, str], ...]:
    parts = []
    for element in run:
        kind = element.tag.rsplit("}", 1)[-1]
        if kind == "t":
            assert element.get(XML_SPACE) == "preserve"
            parts.append(("text", element.text or ""))
        elif kind == "br":
            parts.append(("break", ""))
        elif kind == "tab":
            parts.append(("tab", ""))
    return tuple(parts)


def test_word_text_parts_preserve_order_and_source() -> None:
    before = SOURCE
    assert docx_word_text_parts(SOURCE) == EXPECTED
    assert SOURCE == before
    assert docx_word_text_parts("") == (("text", ""),)
    assert docx_word_text_parts("\r\n\t\r") == (
        ("break", ""), ("tab", ""), ("break", ""),
    )
    assert docx_word_text_parts("  plain  ") == (("text", "  plain  "),)


@pytest.mark.parametrize("where", ("ordinary", "table", "cover"))
def test_word_text_markup_contains_real_break_and_tab_elements(where: str) -> None:
    if where == "ordinary":
        node = ET.fromstring(ordinary_paragraph(SOURCE, style="Normal"))
    elif where == "table":
        node = ET.fromstring(_table_row((SOURCE,), (5200,)))
    else:
        node = polished_paragraph(SOURCE, bold=True)
    runs = node.findall(".//" + W + "r")
    assert any(_run_parts(run) == EXPECTED for run in runs)
    assert "\ud800" not in ET.tostring(node, encoding="unicode")
    assert "Известняк & <плотный>" in "".join(node.itertext())


@pytest.mark.parametrize("language", (AppLanguage.RU, AppLanguage.KK, AppLanguage.EN))
@pytest.mark.parametrize("orientation", ("portrait", "landscape"))
@pytest.mark.parametrize("polished", (False, True))
def test_produced_word_preserves_line_breaks_tabs_and_source(
    tmp_path, language: AppLanguage, orientation: str, polished: bool,
) -> None:
    report = replace(_report(), project_name=SOURCE)
    identity = replace(_manual_identity(), report_title=SOURCE, remarks=SOURCE)
    previous_report, previous_identity = repr(report), repr(identity)
    path = tmp_path / "sample.docx"
    if polished:
        exported = export_polished_hydrocarbon_interpretation_docx(
            report, path, identity=identity, language=language,
            orientation=orientation,
        )
    else:
        exported = export_hydrocarbon_interpretation_docx(
            report, path, language=language, orientation=orientation,
        )
    with zipfile.ZipFile(exported) as archive:
        assert archive.testzip() is None
        root = ET.fromstring(archive.read("word/document.xml"))
        assert any(_run_parts(run) == EXPECTED for run in root.findall(".//" + W + "r"))
        page_sizes = root.findall(".//" + W + "pgSz")
        assert page_sizes
        assert all(page.get(W + "orient") == orientation for page in page_sizes)
    assert repr(report) == previous_report
    assert repr(identity) == previous_identity
