from copy import deepcopy
from dataclasses import replace
from xml.etree import ElementTree as ET
import zipfile

import numpy as np
import pytest

from geoworkbench.data.hydrocarbon_interpretation_export import export_hydrocarbon_interpretation_docx
from geoworkbench.data.hydrocarbon_interpretation_export_docx_polished import export_polished_hydrocarbon_interpretation_docx
from geoworkbench.domain.depth_interval import DepthInterval
from geoworkbench.domain.report_composition import (
    InterpretationReportComposition, report_header_fields, with_report_header_fields,
)
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
    default_interpretation_report_identity, identity_with_report_header_fields, report_header_fields_from_identity,
)
from geoworkbench.printing.report_visual_system import REPORT_BRAND_WORDMARK, modern_oilfield_report_profile
from geoworkbench.project.controller import ProjectController
from geoworkbench.services.hydrocarbon_interpretation import build_hydrocarbon_interpretation_report
from geoworkbench.services.localization import AppLanguage
from test_interpretation_report_charts import _session_with_report_curves
from test_interpretation_report_identity import _manual_identity, _report


_NAMESPACES = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'rel': 'http://schemas.openxmlformats.org/package/2006/relationships',
    'ct': 'http://schemas.openxmlformats.org/package/2006/content-types',
}
_W = '{' + _NAMESPACES['w'] + '}'


def _text(element):
    return ''.join(node.text or '' for node in element.findall('.//w:t', _NAMESPACES))


def _check_footer_package(path, language, expected_sections, has_details):
    with zipfile.ZipFile(path) as package:
        assert package.testzip() is None
        for name in package.namelist():
            if name.endswith(('.xml', '.rels')):
                ET.fromstring(package.read(name))
        document = ET.fromstring(package.read('word/document.xml'))
        footer = ET.fromstring(package.read('word/footer.xml'))
        relationships = ET.fromstring(package.read('word/_rels/document.xml.rels'))
        types = ET.fromstring(package.read('[Content_Types].xml'))
        assert any(item.get('Type', '').endswith('/styles') and item.get('Target') == 'styles.xml'
                   for item in relationships)
        footer_relationships = [item for item in relationships if item.get('Type', '').endswith('/footer')]
        assert len(footer_relationships) == 1
        relation = footer_relationships[0]
        assert relation.get('Target') == 'footer.xml'
        assert any(item.get('PartName') == '/word/footer.xml' and item.get('ContentType', '').endswith('footer+xml')
                   for item in types)
        sections = document.findall('.//w:sectPr', _NAMESPACES)
        assert len(sections) == expected_sections
        rows = footer.findall('.//w:tr', _NAMESPACES)
        assert len(rows) == (2 if has_details else 1)
        table_height = 0
        for row in rows:
            height = row.find('w:trPr/w:trHeight', _NAMESPACES)
            assert height.get(_W + 'hRule') == 'exact'
            assert row.find('w:trPr/w:cantSplit', _NAMESPACES) is not None
            table_height += int(height.get(_W + 'val'))
        for section in sections:
            reference = section.find('w:footerReference', _NAMESPACES)
            assert reference.get('{' + _NAMESPACES['r'] + '}id') == relation.get('Id')
            assert reference.get(_W + 'type') == 'default'
            margin = section.find('w:pgMar', _NAMESPACES)
            assert int(margin.get(_W + 'bottom')) - int(margin.get(_W + 'footer')) >= table_height + 20
            assert section.find('w:pgNumType', _NAMESPACES) is None
        assert {field.get(_W + 'instr') for field in footer.findall('.//w:fldSimple', _NAMESPACES)} == {'PAGE', 'NUMPAGES'}
        assert all(field.get(_W + 'dirty') == 'true' for field in footer.findall('.//w:fldSimple', _NAMESPACES))
        assert footer.find('.//w:tblPr/w:tblW', _NAMESPACES).get(_W + 'type') == 'pct'
        assert footer.find('.//w:tblPr/w:tblLayout', _NAMESPACES).get(_W + 'type') == 'fixed'
        cells = rows[0].findall('w:tc', _NAMESPACES)
        assert _text(cells[0]) == REPORT_BRAND_WORDMARK
        assert cells[0].find('.//w:b', _NAMESPACES) is not None
        assert cells[1].find('.//w:jc', _NAMESPACES).get(_W + 'val') == 'right'
        page_label = {AppLanguage.RU: 'Страница', AppLanguage.KK: 'Бет', AppLanguage.EN: 'Page'}[language]
        assert page_label in _text(cells[1])
        sizes = footer.findall('.//w:rPr/w:sz', _NAMESPACES)
        assert sizes and all(int(size.get(_W + 'val')) == round(modern_oilfield_report_profile().typography.footer_pt * 2)
                             for size in sizes)
        if has_details:
            assert len(_text(rows[1])) <= 96
        assert document.find('.//w:pgSz', _NAMESPACES) is not None
        assert 'customXml/geolog-classification-audit.xml' in package.namelist()
    return document, footer


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('profile', ['standard', 'opus'])
@pytest.mark.parametrize('date', ['', '07.10.2026'])
@pytest.mark.parametrize('long_values', [False, True])
def test_polished_word_footer_uses_reopened_identity_on_both_sections(qapp, tmp_path, language, profile, date, long_values):
    session = _session_with_report_curves(depth_span=30, samples=61)
    number = 'DOC<&42' + (' Long document' * 20 if long_values else '')
    confidentiality = 'Internal' + (' long confidentiality' * 20 if long_values else '')
    identity = replace(_manual_identity(), document_number=number, revision='07', document_status='Approved',
        report_date=date, confidentiality=confidentiality, interval='STALE', prepared_by='Engineer A')
    dataset_id = session.current_dataset.dataset_id
    session.report_compositions[dataset_id] = with_report_header_fields(InterpretationReportComposition(),
        language.value, report_header_fields_from_identity(identity, profile))
    package = tmp_path / 'saved.geologpkg'
    ProjectController(session=session).save_project(package)
    restored = ProjectController().open_project(package)
    report = replace(build_hydrocarbon_interpretation_report(restored), report_profile=profile,
                     analysis_depth_interval=DepthInterval(1305, 1320))
    before = deepcopy(restored.report_compositions)
    resolved = identity_with_report_header_fields(default_interpretation_report_identity(report, language),
        report_header_fields(restored.report_compositions[dataset_id], language.value, profile))
    dataset = restored.current_dataset
    depth = dataset.depth.copy()
    curves = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    target = export_polished_hydrocarbon_interpretation_docx(report, tmp_path / 'controlled.docx',
        dataset=dataset, identity=resolved, language=language)
    document, footer = _check_footer_package(target, language, 2, True)
    body_text, footer_text = _text(document), _text(footer)
    assert number in body_text and confidentiality in body_text
    assert 'DOC<&42' in footer_text and '07' in footer_text
    assert ('…' in footer_text) == long_values
    if not long_values:
        assert 'Approved' in footer_text and 'Internal' in footer_text
    assert 'Engineer A' in body_text and 'Engineer A' not in footer_text
    assert 'STALE' not in body_text and report.generated_at not in footer_text
    assert ('07.10.2026' in body_text) == bool(date)
    assert '07.10.2026' not in footer_text
    assert restored.report_compositions == before
    np.testing.assert_array_equal(dataset.depth, depth)
    for key, values in curves.items():
        np.testing.assert_array_equal(dataset.curves[key].values, values)


def test_polished_word_cover_uses_shared_visual_profile(tmp_path, monkeypatch):
    from geoworkbench.data import hydrocarbon_interpretation_export_docx_polished as polished

    base = modern_oilfield_report_profile()
    visual = replace(
        base,
        palette=replace(
            base.palette,
            accent="#123456",
            text="#234567",
            text_secondary="#345678",
            text_muted="#456789",
            border="#56789A",
            border_strong="#6789AB",
            table_header="#ABCDEF",
        ),
        typography=replace(
            base.typography,
            title_pt=24.0,
            subtitle_pt=11.0,
            section_pt=13.0,
            body_pt=9.0,
            table_pt=8.0,
        ),
    )
    monkeypatch.setattr(polished, "modern_oilfield_report_profile", lambda: visual)
    identity = replace(
        _manual_identity(),
        summary="Profile-driven summary",
        conclusion="Profile-driven conclusion",
    )

    target = polished.export_polished_hydrocarbon_interpretation_docx(
        _report(),
        tmp_path / "profile-driven.docx",
        identity=identity,
        language=AppLanguage.EN,
    )

    with zipfile.ZipFile(target) as package:
        document = ET.fromstring(package.read("word/document.xml"))

    colors = {
        node.get(_W + "val")
        for node in document.findall(".//w:rPr/w:color", _NAMESPACES)
        if node.get(_W + "val")
    }
    fills = {
        node.get(_W + "fill")
        for node in document.findall(".//w:shd", _NAMESPACES)
        if node.get(_W + "fill")
    }
    border_colors = {
        node.get(_W + "color")
        for node in document.findall(".//w:tblBorders/*", _NAMESPACES)
        if node.get(_W + "color")
    }
    sizes = {
        int(node.get(_W + "val"))
        for node in document.findall(".//w:rPr/w:sz", _NAMESPACES)
        if node.get(_W + "val")
    }

    assert visual.brand_wordmark in _text(document)
    for value in (
        visual.palette.accent,
        visual.palette.text,
        visual.palette.text_secondary,
        visual.palette.text_muted,
    ):
        assert value.lstrip("#").upper() in colors
    assert visual.palette.table_header.lstrip("#").upper() in fills
    assert visual.palette.border.lstrip("#").upper() in border_colors
    assert visual.palette.border_strong.lstrip("#").upper() in border_colors
    for points in (
        visual.typography.title_pt,
        visual.typography.subtitle_pt,
        visual.typography.section_pt,
        visual.typography.body_pt,
        visual.typography.table_pt,
    ):
        assert round(points * 2.0) in sizes


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('profile', ['standard', 'opus'])
def test_ordinary_word_gets_shared_brand_and_page_fields(tmp_path, language, profile):
    report = replace(_report(), report_profile=profile)
    before = deepcopy(report)
    target = export_hydrocarbon_interpretation_docx(report, tmp_path / 'ordinary.docx', language=language)
    document, footer = _check_footer_package(target, language, 1, False)
    assert report.project_name in _text(document)
    assert report.generated_at not in _text(footer)
    assert report == before


def test_footer_failure_preserves_existing_document_and_cleans_staging(tmp_path, monkeypatch):
    from geoworkbench.data import hydrocarbon_interpretation_export_docx_polished as exporter

    target = tmp_path / 'existing.docx'
    target.write_bytes(b'original document')
    def fail_footer(*args):
        raise RuntimeError('footer failed')
    monkeypatch.setattr(exporter, 'report_document_control_docx_footer', fail_footer)
    with pytest.raises(RuntimeError, match='footer failed'):
        exporter.export_polished_hydrocarbon_interpretation_docx(_report(), target,
            identity=_manual_identity(), overwrite=True)
    assert target.read_bytes() == b'original document'
    assert list(tmp_path.iterdir()) == [target]
