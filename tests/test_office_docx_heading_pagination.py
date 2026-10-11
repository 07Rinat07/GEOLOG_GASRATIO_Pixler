from dataclasses import replace
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import pytest

from geoworkbench.data.hydrocarbon_interpretation_export import export_hydrocarbon_interpretation_docx
from geoworkbench.data.hydrocarbon_interpretation_export_docx_polished import export_polished_hydrocarbon_interpretation_docx
from geoworkbench.printing.interpretation_report import build_interpretation_report
from geoworkbench.printing.interpretation_report_office import export_interpretation_report_docx
from geoworkbench.services.hydrocarbon_interpretation import build_hydrocarbon_interpretation_report
from geoworkbench.services.localization import AppLanguage
from test_interpretation_report import _session
from test_interpretation_report_charts import _session_with_report_curves


NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = "{" + NS["w"] + "}"


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("kind", ["geology", "standard", "opus", "polished_standard", "polished_opus"])
def test_office_headings_keep_with_content_and_rows_paginate_independently(tmp_path, language, kind):
    session = _session() if kind == "geology" else _session_with_report_curves(depth_span=30, samples=61)
    dataset = session.current_dataset
    before_depth = dataset.depth.copy()
    before_curves = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    path = tmp_path / f"headings-{kind}-{language.value}.docx"
    if kind == "geology":
        report = build_interpretation_report(session, language=language)
        before_report = repr(report)
        export_interpretation_report_docx(report, path, language=language)
    else:
        report = replace(build_hydrocarbon_interpretation_report(session),
                         report_profile="opus" if kind.endswith("opus") else "standard")
        before_report = repr(report)
        exporter = (export_polished_hydrocarbon_interpretation_docx
                    if kind.startswith("polished") else export_hydrocarbon_interpretation_docx)
        exporter(report, path, dataset=dataset, language=language)
    with zipfile.ZipFile(path) as package:
        assert package.testzip() is None
        root = ET.fromstring(package.read("word/document.xml"))
    body = root.find("w:body", NS)
    assert body is not None
    headings = []
    ordinary = []
    for paragraph in body.findall("w:p", NS):
        style = paragraph.find("w:pPr/w:pStyle", NS)
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", NS))
        if style is not None and style.get(W + "val") in {"Title", "Heading1"}:
            assert text
            assert paragraph.find("w:pPr/w:keepNext", NS) is not None
            assert paragraph.find("w:pPr/w:keepLines", NS) is not None
            headings.append(text)
        elif not kind.startswith("polished") and text:
            assert paragraph.find("w:pPr/w:keepNext", NS) is None
            ordinary.append(text)
    assert len(headings) >= 3
    if not kind.startswith("polished"):
        assert ordinary
    tables = body.findall("w:tbl", NS)
    assert tables
    for table in tables:
        assert not table.findall(".//w:keepNext", NS)
        for row in table.findall("w:tr", NS):
            assert row.find("w:trPr/w:cantSplit", NS) is not None
    assert repr(report) == before_report
    np.testing.assert_array_equal(dataset.depth, before_depth)
    for key, values in before_curves.items():
        np.testing.assert_array_equal(dataset.curves[key].values, values)
