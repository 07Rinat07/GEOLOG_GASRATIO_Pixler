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
from test_interpretation_report_identity import _manual_identity, _report
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



@pytest.mark.parametrize("compact", (False, True))
@pytest.mark.parametrize("language", list(AppLanguage))
def test_operator_can_reach_word_orientation_in_responsive_export_footer(
    qapp, monkeypatch: pytest.MonkeyPatch, language: AppLanguage, compact: bool,
) -> None:
    workspace = _workspace(language)
    workspace.resize(1300, 800)
    workspace.show()
    qapp.processEvents()
    assert not workspace.preview_toggle.isChecked()
    assert not workspace.export_footer.isVisible()
    workspace.preview_toggle.click()
    qapp.processEvents()
    assert workspace.report_panel.isVisible()
    # Exercise both layout branches independently of a particular screen DPI.
    monkeypatch.setattr(workspace, "_EXPORT_COMPACT_BREAKPOINT", 100000 if compact else -1)
    workspace._relayout_export_actions(force=True)
    qapp.processEvents()
    assert workspace.export_footer.isVisible()
    for widget in (workspace.word_orientation_label, workspace.word_orientation):
        assert workspace._export_grid.indexOf(widget) >= 0
        assert widget.isVisible()
        assert widget.parentWidget() is workspace.export_footer
    assert workspace.word_orientation.currentData() == "portrait"
    position = workspace.word_orientation.findData("landscape")
    workspace.word_orientation.setCurrentIndex(position)
    assert workspace.word_orientation.currentData() == "landscape"
    workspace.set_language({AppLanguage.RU: AppLanguage.EN,
                            AppLanguage.KK: AppLanguage.RU,
                            AppLanguage.EN: AppLanguage.KK}[language])
    assert workspace.word_orientation.currentData() == "landscape"
    assert workspace.word_orientation.isVisible()
    workspace.close()



@pytest.mark.parametrize("invalid", (
    "\x00", "\x01", "\x08", "\x0b", "\x0c", "\x1f",
    "\ud800", "\udfff", "\ufffe", "\uffff",
))
def test_word_xml10_filter_drops_only_forbidden_characters(invalid: str) -> None:
    from xml.sax.saxutils import escape
    from geoworkbench.data.hydrocarbon_interpretation_export import _xml_text
    from geoworkbench.printing.docx_xml_characters import docx_xml_safe_text

    source = f"Максат & <M-1>\t\n\rЖазба 🛢{invalid} End"
    accepted = source.replace(invalid, "")
    assert docx_xml_safe_text(source) == accepted
    assert _xml_text(source) == escape(accepted)
    assert "".join(ET.fromstring("<root>" + _xml_text(source) + "</root>").itertext()).replace(
        "\n", ""
    ).startswith("Максат & <M-1>")


def test_word_xml10_filter_preserves_unicode_boundary_characters() -> None:
    from geoworkbench.printing.docx_xml_characters import docx_xml_safe_text

    valid = "".join(chr(cp) for cp in (
        0x9, 0xA, 0xD, 0x20, 0xD7FF, 0xE000, 0xFFFD, 0x10000, 0x10FFFF,
    ))
    assert docx_xml_safe_text(valid) == valid
    assert docx_xml_safe_text("Қазақша 😀 & <геология>") == "Қазақша 😀 & <геология>"


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("orientation", ("portrait", "landscape"))
@pytest.mark.parametrize("polished", (False, True))
@pytest.mark.parametrize("profile", ("standard", "opus"))
def test_complete_word_package_escapes_illegal_unicode_without_changing_inputs(
    tmp_path: Path, language: AppLanguage, orientation: str, polished: bool, profile: str,
) -> None:
    from geoworkbench.printing.docx_xml_characters import docx_xml_safe_text

    unsafe = "Максат-1 & <скважина> Қаз 🛢\x00\ud800\udfff\ufffe\uffff"
    expected = docx_xml_safe_text(unsafe)
    report = replace(
        _report(), report_profile=profile, project_name=unsafe,
        well_name=unsafe, dataset_name=unsafe,
    )
    identity = replace(
        _manual_identity(), report_title=unsafe, report_subtitle=unsafe,
        project_name=unsafe, well_name=unsafe, prepared_by=unsafe, remarks=unsafe,
    )
    before_report, before_identity = deepcopy(report), deepcopy(identity)
    exporter = (
        export_polished_hydrocarbon_interpretation_docx if polished
        else export_hydrocarbon_interpretation_docx
    )
    kwargs = {"identity": identity} if polished else {}
    result = exporter(
        report, tmp_path / "unicode.docx", language=language,
        orientation=orientation, **kwargs,
    )
    with zipfile.ZipFile(result) as package:
        assert package.testzip() is None
        xml_parts = [name for name in package.namelist()
                     if name.endswith((".xml", ".rels"))]
        assert "word/document.xml" in xml_parts
        assert "word/footer.xml" in xml_parts
        assert "customXml/geolog-classification-audit.xml" in xml_parts
        for name in xml_parts:
            ET.fromstring(package.read(name))
        document = ET.fromstring(package.read("word/document.xml"))
        document_text = "".join(node.text or "" for node in document.iter(W + "t"))
        assert expected in document_text
        assert unsafe not in document_text
        sizes = document.findall(".//" + W + "pgSz")
        assert sizes and all(size.get(W + "orient") == orientation for size in sizes)
    assert report == before_report
    assert identity == before_identity


def test_word_footer_removes_illegal_xml_character_from_compact_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from geoworkbench.printing import report_document_control_docx as footer

    source = "Казахстан 🛢\ud800\ufffe\x00 & <M-1>"
    monkeypatch.setattr(footer, "compact_report_footer", lambda control: source)
    xml = footer.report_document_control_docx_footer(None, AppLanguage.RU, width_twips=9600)
    root = ET.fromstring(xml)
    text = "".join(node.text or "" for node in root.iter(W + "t"))
    assert "Казахстан 🛢 & <M-1>" in text
    assert "\ud800" not in text and "\ufffe" not in text and "\x00" not in text
