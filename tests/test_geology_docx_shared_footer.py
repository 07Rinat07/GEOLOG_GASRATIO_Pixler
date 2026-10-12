import xml.etree.ElementTree as ET
import zipfile

import pytest

from geoworkbench.printing.interpretation_report import build_interpretation_report
from geoworkbench.printing.interpretation_report_office import export_interpretation_report_docx
from geoworkbench.printing.report_document_control_docx import report_document_control_docx_footer
from geoworkbench.services.localization import AppLanguage
from test_interpretation_report import _session


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
P = "{http://schemas.openxmlformats.org/package/2006/relationships}"


@pytest.mark.parametrize("language", list(AppLanguage))
def test_geology_docx_wires_shared_footer_with_reserved_page_space(tmp_path, language):
    report = build_interpretation_report(_session(), language=language)
    before = repr(report)
    path = tmp_path / "geology.docx"
    export_interpretation_report_docx(report, path, language=language)
    with zipfile.ZipFile(path) as package:
        assert package.testzip() is None
        assert package.read("word/footer.xml") == report_document_control_docx_footer(None, language)
        document = ET.fromstring(package.read("word/document.xml"))
        section = document.find(".//" + W + "sectPr")
        reference = section.find(W + "footerReference")
        relationships = ET.fromstring(package.read("word/_rels/document.xml.rels"))
        relationship = next(node for node in relationships if node.get("Id") == reference.get(R + "id"))
        assert relationship.tag == P + "Relationship"
        assert relationship.get("Type").endswith("/footer")
        assert relationship.get("Target") == "footer.xml"
        types = ET.fromstring(package.read("[Content_Types].xml"))
        assert any(node.get("PartName") == "/word/footer.xml" and node.get("ContentType").endswith(".footer+xml") for node in types)
        margins = section.find(W + "pgMar")
        assert int(margins.get(W + "bottom")) - int(margins.get(W + "footer")) >= 720
        footer = ET.fromstring(package.read("word/footer.xml"))
        assert [node.get(W + "instr") for node in footer.iter(W + "fldSimple")] == ["PAGE", "NUMPAGES"]
    assert repr(report) == before
