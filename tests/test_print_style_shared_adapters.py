from dataclasses import replace
import zipfile
from html import unescape
from types import SimpleNamespace
from xml.etree import ElementTree

import fitz
import pytest
from openpyxl import load_workbook
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter

from geoworkbench.data import hydrocarbon_interpretation_export as word
from geoworkbench.printing import document_renderer as tablet
from geoworkbench.printing import interpretation_report as geology
from geoworkbench.printing import interpretation_report_office as office
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.services.localization import AppLanguage, Localizer
from test_interpretation_report import _session


@pytest.mark.parametrize("language", list(AppLanguage))
def test_geology_preview_pdf_and_office_use_shared_profile(qapp, tmp_path, monkeypatch, language):
    visual = modern_oilfield_report_profile(grayscale=True)
    visual = replace(visual, typography=replace(visual.typography, title_pt=23, table_pt=8))
    for adapter in (geology, office, word):
        monkeypatch.setattr(adapter, "modern_oilfield_report_profile", lambda: visual)
    session = _session()
    report = geology.build_interpretation_report(session)
    html = geology.interpretation_report_html(report, language=language)
    assert visual.brand_wordmark in unescape(html)
    assert f"background: {visual.palette.table_header}" in html
    assert "font-size: 23pt" in html
    assert "font-size: 8pt" in html
    assert session.current_dataset is not None
    values = {key: curve.values.copy() for key, curve in session.current_dataset.curves.items()}
    pdf = geology.export_interpretation_report_pdf(
        report, tmp_path / "geology.pdf", language=language
    )
    with fitz.open(pdf) as document:
        text = "".join(page.get_text() for page in document)
    assert visual.brand_wordmark in text
    assert report.well_name in text
    xlsx = office.export_interpretation_report_xlsx(
        report, tmp_path / "geology.xlsx", language=language
    )
    workbook = load_workbook(xlsx)
    assert workbook.worksheets[0]["A1"].font.sz == 23
    sheet = workbook.worksheets[1]
    assert sheet["A1"].fill.fgColor.rgb[-6:] == visual.palette.table_header[1:]
    assert sheet["A1"].font.sz == 8
    assert sheet["A2"].fill.fgColor.rgb[-6:] == visual.palette.table_alt[1:]
    docx = office.export_interpretation_report_docx(
        report, tmp_path / "geology.docx", language=language
    )
    with zipfile.ZipFile(docx) as archive:
        styles = ElementTree.fromstring(archive.read("word/styles.xml"))
        document_xml = ElementTree.fromstring(archive.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    value = "{" + ns["w"] + "}val"
    title = styles.find("w:style[@w:styleId='Title']/w:rPr/w:sz", ns)
    assert title.attrib[value] == "46"
    fill = "{" + ns["w"] + "}fill"
    assert visual.palette.table_header[1:] in {
        node.attrib[fill] for node in document_xml.findall(".//w:shd", ns)
    }
    import numpy as np

    for key, source in values.items():
        np.testing.assert_array_equal(session.current_dataset.curves[key].values, source)


@pytest.mark.parametrize("width", [180, 600])
def test_tablet_footer_reserves_page_number_and_restores_painter(qapp, monkeypatch, width):
    visual = modern_oilfield_report_profile(grayscale=True)
    monkeypatch.setattr(tablet, "modern_oilfield_report_profile", lambda: visual)
    image = QImage(width, 50, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    old_pen, old_font = painter.pen(), painter.font()
    drawn = []

    class CapturePainter:
        def __getattr__(self, name):
            return getattr(painter, name)

        def drawText(self, rect, flags, text):
            drawn.append((QRectF(rect), text))
            painter.drawText(rect, flags, text)

    try:
        tablet._paint_footer(
            CapturePainter(),
            QRectF(0, 0, width, 40),
            page=SimpleNamespace(index=999, total=999),
            show_page_numbers=True,
            localizer=Localizer.create(AppLanguage.EN),
        )
        assert painter.pen() == old_pen
        assert painter.font() == old_font
        assert len(drawn) == 2
        assert drawn[0][0].right() < drawn[1][0].right()
        assert "999" in drawn[1][1]
        if width == 600:
            assert drawn[0][1] == visual.brand_wordmark
        else:
            assert len(drawn[0][1]) < len(visual.brand_wordmark)
    finally:
        painter.end()


@pytest.mark.parametrize("dpi", [72, 96, 144, 300, 600])
def test_tablet_header_and_footer_keep_physical_rule_thickness(qapp, dpi):
    image = QImage(1200, 120, QImage.Format.Format_ARGB32)
    image.setDotsPerMeterX(round(dpi / 0.0254))
    image.setDotsPerMeterY(round(dpi / 0.0254))
    painter = QPainter(image)
    widths = []

    class CapturePainter:
        def __getattr__(self, name):
            return getattr(painter, name)

        def drawLine(self, *args):
            widths.append(painter.pen().widthF())
            painter.drawLine(*args)

    capture = CapturePainter()
    try:
        tablet._paint_header(capture, QRectF(0, 0, 1200, 50), title="Well A", range_text="100–200 m")
        tablet._paint_footer(
            capture, QRectF(0, 60, 1200, 50), page=SimpleNamespace(index=1, total=1),
            show_page_numbers=True, localizer=Localizer.create(AppLanguage.EN),
        )
        assert len(widths) == 2
        expected_points = modern_oilfield_report_profile().layout.thin_rule_pt
        for width in widths:
            assert width * 72 / image.logicalDpiY() == pytest.approx(expected_points)
    finally:
        painter.end()
