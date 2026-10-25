"""Gas-ratio Word reports use the selected A4 orientation on every section."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET
import zipfile

import pytest

from geoworkbench.data.hydrocarbon_interpretation_export import export_hydrocarbon_interpretation_docx
from geoworkbench.data.hydrocarbon_interpretation_export_docx_polished import (
    export_polished_hydrocarbon_interpretation_docx,
)
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
    default_interpretation_report_identity,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui import interpretation_report_workspace_drilling as drilling
from test_interpretation_report_identity import _report
from test_interpretation_method_comparison_explicit_ui import _workspace


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def test_word_table_resize_rejects_xml_entities():
    from defusedxml.common import EntitiesForbidden
    from geoworkbench.data.hydrocarbon_interpretation_export import _resize_docx_tables

    xml = '<!DOCTYPE root [<!ENTITY injected "expanded">]><root>&injected;</root>'
    with pytest.raises(EntitiesForbidden):
        _resize_docx_tables(xml, 9600)


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("report_profile", ("standard", "opus"))
@pytest.mark.parametrize("polished", (False, True))
@pytest.mark.parametrize("orientation", ("portrait", "landscape"))
def test_gas_word_cover_body_and_footer_use_selected_a4_orientation(
    tmp_path: Path, language: AppLanguage, report_profile: str,
    polished: bool, orientation: str,
) -> None:
    report = replace(_report(), report_profile=report_profile)
    before = deepcopy(report)
    export = export_polished_hydrocarbon_interpretation_docx if polished else export_hydrocarbon_interpretation_docx
    path = export(report, tmp_path / "gas.docx", language=language, orientation=orientation)
    expected = ("11906", "16838") if orientation == "portrait" else ("16838", "11906")
    printable = int(expected[0]) - 2 * 850
    with zipfile.ZipFile(path) as package:
        assert package.testzip() is None
        for name in package.namelist():
            if name.endswith((".xml", ".rels")):
                ET.fromstring(package.read(name))
        document = ET.fromstring(package.read("word/document.xml"))
        sections = document.findall(".//" + W + "sectPr")
        assert len(sections) == (2 if polished else 1)
        for section in sections:
            size = section.find(W + "pgSz")
            assert size is not None
            assert (size.get(W + "w"), size.get(W + "h")) == expected
            assert size.get(W + "orient") == orientation
            margins = section.find(W + "pgMar")
            assert margins is not None
            assert int(expected[0]) - int(margins.get(W + "left")) - int(margins.get(W + "right")) >= (9600 if orientation == "portrait" else 15000)
        tables = document.findall(".//" + W + "tbl")
        assert tables
        for table in tables:
            width = int(table.find(W + "tblPr").find(W + "tblW").get(W + "w"))
            widths = tuple(int(col.get(W + "w")) for col in table.find(W + "tblGrid"))
            assert widths and all(w > 0 for w in widths)
            assert width == sum(widths)
            assert width <= (9600 if orientation == "portrait" else printable)
            for row in table.findall(W + "tr"):
                cells = tuple(int(cell.find(W + "tcPr").find(W + "tcW").get(W + "w"))
                              for cell in row.findall(W + "tc"))
                assert cells == widths
        footer = ET.fromstring(package.read("word/footer.xml"))
        table = footer.find(W + "tbl")
        assert table is not None
        footer_width = int(table.find(W + "tblPr").find(W + "tblW").get(W + "w"))
        footer_grid = tuple(int(node.get(W + "w")) for node in table.find(W + "tblGrid"))
        assert footer_width == sum(footer_grid) == (9600 if orientation == "portrait" else 15000)
        text = "".join(node.text or "" for node in document.iter(W + "t"))
        assert report.project_name in text
        assert report.well_name in text
    assert report == before


@pytest.mark.parametrize("export", (
    export_hydrocarbon_interpretation_docx,
    export_polished_hydrocarbon_interpretation_docx,
))
@pytest.mark.parametrize("orientation", ("portrait", "landscape"))
def test_explicit_word_orientation_preserves_existing_document_on_invalid_value(
    tmp_path: Path, export, orientation: str,
) -> None:
    destination = tmp_path / "previous.docx"
    destination.write_bytes(b"previous approved report")
    with pytest.raises(ValueError, match="Word page orientation"):
        export(_report(), destination, orientation="invalid-" + orientation, overwrite=True)
    assert destination.read_bytes() == b"previous approved report"


@pytest.mark.parametrize("export", (
    export_hydrocarbon_interpretation_docx,
    export_polished_hydrocarbon_interpretation_docx,
))
def test_word_export_defaults_to_portrait(tmp_path: Path, export) -> None:
    path = export(_report(), tmp_path / "default.docx")
    with zipfile.ZipFile(path) as package:
        document = ET.fromstring(package.read("word/document.xml"))
        assert {size.get(W + "orient") for size in document.findall(".//" + W + "pgSz")} == {"portrait"}


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("orientation", ("portrait", "landscape"))
def test_ui_choice_survives_language_change_and_is_forwarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp,
    language: AppLanguage, orientation: str,
) -> None:
    workspace = _workspace(language)
    assert workspace.word_orientation.objectName() == "interpretation-word-page-orientation"
    assert workspace.word_orientation.currentData() == "portrait"
    idx = workspace.word_orientation.findData(orientation)
    assert idx >= 0
    workspace.word_orientation.setCurrentIndex(idx)
    next_lang = {AppLanguage.RU: AppLanguage.EN,
                 AppLanguage.EN: AppLanguage.KK,
                 AppLanguage.KK: AppLanguage.RU}[language]
    workspace.set_language(next_lang)
    assert workspace.word_orientation.currentData() == orientation
    target = tmp_path / "portrait.docx"
    monkeypatch.setattr(workspace, "_choose_target", lambda suffix, file_filter: target)
    monkeypatch.setattr(workspace, "_show_export_success", lambda path: None)
    monkeypatch.setattr(workspace, "_select_report_identity",
                        lambda report: default_interpretation_report_identity(
                            report, workspace._report_output_language()))
    captured = []
    def capture(report, destination, **kwargs):
        captured.append(kwargs)
        return destination
    monkeypatch.setattr(drilling, "export_polished_hydrocarbon_interpretation_docx", capture)
    workspace._export_docx()
    assert len(captured) == 1
    assert captured[0]["orientation"] == orientation
    workspace.close()
