"""Explicit source-bound geology in Word; no implicit well lookup."""
from dataclasses import replace
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import pytest

from geoworkbench.data.hydrocarbon_interpretation_export import export_hydrocarbon_interpretation_docx
from geoworkbench.data.hydrocarbon_interpretation_export_docx_polished import export_polished_hydrocarbon_interpretation_docx
from geoworkbench.services.interpretation_geology_interval_evidence_html import geology_interval_evidence_table
from geoworkbench.services.localization import AppLanguage
from test_interpretation_geology_evidence_signed_pdf import _actual_source


@pytest.mark.parametrize("exporter", (export_hydrocarbon_interpretation_docx, export_polished_hydrocarbon_interpretation_docx))
@pytest.mark.parametrize("language", tuple(AppLanguage))
def test_word_contains_exact_shared_projection_only_when_selected(tmp_path, language, exporter):
    _, report, evidence = _actual_source()
    plain = exporter(report, tmp_path / "plain.docx", language=language)
    selected = exporter(
        report, tmp_path / "selected.docx", language=language, geology_evidence=(evidence,),
    )
    def text(path):
        with ZipFile(path) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))
        return " ".join(root.itertext())
    projection = geology_interval_evidence_table(evidence, language)
    assert projection.title not in text(plain)
    result = text(selected)
    assert projection.title in result
    assert projection.intro in result
    for row in (*projection.coverage_rows, *projection.rows):
        for cell in row:
            assert cell in result


@pytest.mark.parametrize("change", ("dataset", "axis", "candidate", "duplicate"))
def test_foreign_evidence_preserves_existing_destination(tmp_path, change):
    _, report, evidence = _actual_source()
    selected = (evidence,)
    if change == "dataset":
        selected = (replace(evidence, dataset_id="foreign"),)
    elif change == "axis":
        selected = (replace(evidence, depth_axis_id="foreign"),)
    elif change == "candidate":
        selected = (replace(evidence, gas_top=1003.0),)
    else:
        selected = (evidence, evidence)
    target = tmp_path / "preserved.docx"
    target.write_bytes(b"existing document")
    with pytest.raises(ValueError):
        export_hydrocarbon_interpretation_docx(report, target, overwrite=True, geology_evidence=selected)
    assert target.read_bytes() == b"existing document"
