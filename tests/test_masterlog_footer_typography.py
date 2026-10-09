from copy import deepcopy
from dataclasses import replace

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QMarginsF, QRectF, QSizeF
from PySide6.QtGui import QFont, QPainter, QPdfWriter

from geoworkbench.printing import masterlog_renderer as renderer
from geoworkbench.printing.masterlog_document_control import masterlog_document_control_layout
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.printing.report_document_control import compact_report_footer
from geoworkbench.project.controller import ProjectController
from geoworkbench.services.localization import AppLanguage
from test_masterlog_control_layout import controlled_form
from test_masterlog_default_typography import TEXTS, _assert_baseline


def _pdf_snapshot(tmp_path, name, dpi, paint):
    target = tmp_path / f"{name}.pdf"
    writer = QPdfWriter(str(target))
    writer.setResolution(dpi)
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))
    painter = QPainter(writer)
    painter.scale(dpi / 25.4, dpi / 25.4)
    try:
        paint(painter)
    finally:
        painter.end()
    with fitz.open(target) as document:
        spans = [span for block in document[0].get_text("dict")["blocks"] if "lines" in block
                 for line in block["lines"] for span in line["spans"]]
        return document[0].get_text(), spans


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", [72, 96, 144, 300, 600])
@pytest.mark.parametrize("controlled", [False, True])
@pytest.mark.parametrize("custom", [False, True])
def test_masterlog_footer_uses_shared_role_at_physical_dpi(
    qapp, tmp_path, monkeypatch, language, dpi, controlled, custom,
):
    visual = renderer.modern_oilfield_report_profile()
    if custom:
        visual = replace(visual, typography=replace(visual.typography, footer_pt=8.5, table_pt=9.5))
    monkeypatch.setattr(renderer, "modern_oilfield_report_profile", lambda: visual)
    session, template = controlled_form()
    template.columns = []
    template.header_elements = []
    control = masterlog_document_control_layout(template, session, (145, 355), 180, language)
    label = TEXTS[language.value]
    sizes = []
    original = renderer._set_scaled_font_points

    def capture(painter, font, size):
        sizes.append(size)
        original(painter, font, size)

    monkeypatch.setattr(renderer, "_set_scaled_font_points", capture)
    if not controlled:
        monkeypatch.setattr(renderer, "masterlog_document_control_layout", lambda *args, **kwargs: None)

    def paint(painter):
        before = (QFont(painter.font()), painter.pen(), painter.transform())
        if controlled:
            renderer._paint_masterlog_document_control(painter, 20, 180, control)
            renderer._paint_masterlog_control_footer(painter, QSizeF(180, 240), control, label)
        else:
            renderer.paint_masterlog(
                painter, QRectF(0, 0, 180, 240), template, session,
                canvas_size_mm=QSizeF(180, 240), page_label=label,
            )
        assert (painter.font(), painter.pen(), painter.transform()) == before

    baseline = _pdf_snapshot(tmp_path, "baseline", 72, paint)
    actual = _pdf_snapshot(tmp_path, "actual", dpi, paint)
    expected = ([visual.typography.table_pt] * (1 + len(control.rows))
                + [visual.typography.footer_pt] * 4) if controlled else [visual.typography.footer_pt]
    assert sizes == expected * 2
    assert label in actual[0]
    assert visual.brand_wordmark in actual[0]
    if controlled:
        assert compact_report_footer(control.snapshot) in actual[0]
    footer_top = (230.0 if controlled else 235.0) * 72 / 25.4
    footer_spans = [span for span in actual[1] if span["bbox"][1] >= footer_top - 0.3]
    assert len(footer_spans) == (3 if controlled else 2)
    for span in footer_spans:
        assert span["bbox"][1] >= footer_top - 0.3
        assert span["bbox"][0] >= 2 * 72 / 25.4 - 0.3
        assert span["bbox"][2] <= 178 * 72 / 25.4 + 0.3
        assert span["bbox"][3] <= 239.5 * 72 / 25.4 + 0.3
    _assert_baseline(baseline, actual)


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("page_format", ["A4", "A3", "roll"])
@pytest.mark.parametrize("controlled", [False, True])
def test_footer_profile_survives_masterlog_reopen(qapp, tmp_path, language, page_format, controlled):
    session, template = controlled_form()
    template.page_format = page_format
    if not controlled:
        template.properties["header_fields"] = {}
    package = tmp_path / "footer-profile.geologpkg"
    ProjectController(session=session).save_project(package)
    restored = ProjectController().open_project(package)
    saved = restored.project.masterlog_templates[template.template_id]
    before = deepcopy(saved)
    depths = restored.current_dataset.depth.copy()
    values = restored.current_dataset.curve_by_mnemonic("C1").values.copy()
    target = renderer.export_masterlog_pdf(
        saved, restored, tmp_path / "footer-profile.pdf",
        settings=MasterlogOutputSettings(145, 355, language),
    )
    visual = renderer.modern_oilfield_report_profile()
    control = masterlog_document_control_layout(saved, restored, (145, 355), 180, language)

    def paint_baseline(painter):
        if controlled:
            renderer._paint_masterlog_control_footer(painter, QSizeF(180, 240), control, "Page 1")
        else:
            renderer.paint_masterlog(
                painter, QRectF(0, 0, 180, 240), saved, restored,
                canvas_size_mm=QSizeF(180, 240), page_label="Page 1", language=language,
            )

    baseline = _pdf_snapshot(tmp_path, "baseline", 72, paint_baseline)
    baseline_brand = [span for span in baseline[1] if visual.brand_wordmark in span["text"]]
    expected_size = max(baseline_brand, key=lambda span: span["bbox"][1])["size"]
    with fitz.open(target) as document:
        for page in document:
            spans = [span for block in page.get_text("dict")["blocks"] if "lines" in block
                     for line in block["lines"] for span in line["spans"]]
            brand = [span for span in spans if visual.brand_wordmark in span["text"]]
            assert brand
            footer = max(brand, key=lambda span: span["bbox"][1])
            assert footer["size"] == pytest.approx(expected_size, abs=0.08)
            assert footer["bbox"][3] <= page.rect.height
            if controlled:
                assert "DOC-42" in page.get_text()
    assert saved == before
    np.testing.assert_array_equal(restored.current_dataset.depth, depths)
    np.testing.assert_array_equal(restored.current_dataset.curve_by_mnemonic("C1").values, values)
