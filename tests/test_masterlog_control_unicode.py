from copy import deepcopy

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QSizeF
from PySide6.QtGui import QFont

from geoworkbench.printing import masterlog_renderer as renderer
from geoworkbench.printing.masterlog_document_control import masterlog_document_control_layout
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.printing.report_document_control import compact_report_footer
from geoworkbench.printing.unicode_support import resolve_unicode_font_profile
from geoworkbench.project.controller import ProjectController
from geoworkbench.services.localization import AppLanguage
from test_masterlog_control_layout import controlled_form
from test_masterlog_default_typography import _assert_baseline, _pdf_snapshot


TEXTS = {"ru": "Инженер №7", "kk": "Әғқң Өұүһі №7", "en": "Engineer №7"}


def _localized_form(language):
    session, template = controlled_form()
    template.properties["header_fields"]["header.prepared_by"] = TEXTS[language.value]
    return session, template


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", [72, 96, 144, 300, 600])
@pytest.mark.parametrize("region", ["header", "footer"])
def test_control_regions_select_full_text_font_before_measuring(
    qapp, tmp_path, monkeypatch, language, dpi, region,
):
    session, template = _localized_form(language)
    template.properties["header_fields"]["header.confidentiality"] = TEXTS[language.value] * 30
    control = masterlog_document_control_layout(template, session, (145, 355), 180, language)
    page_label = TEXTS[language.value]
    calls = []
    original_font = renderer.print_font

    def capture(*args, **kwargs):
        font = original_font(*args, **kwargs)
        calls.append((kwargs.get("text"), font.families(), font.bold()))
        return font

    monkeypatch.setattr(renderer, "print_font", capture)

    def paint(painter):
        before_font = QFont(painter.font())
        before_pen = painter.pen()
        before_transform = painter.transform()
        if region == "header":
            renderer._paint_masterlog_document_control(painter, 20, 180, control)
        else:
            renderer._paint_masterlog_control_footer(painter, QSizeF(180, 240), control, page_label)
        assert painter.font() == before_font
        assert painter.pen() == before_pen
        assert painter.transform() == before_transform

    old_font = QFont(qapp.font())
    try:
        qapp.setFont(QFont("Courier New", 19))
        baseline = _pdf_snapshot(tmp_path, "baseline", 72, paint)
        actual = _pdf_snapshot(tmp_path, "actual", dpi, paint)
    finally:
        qapp.setFont(old_font)
    if region == "header":
        expected = [renderer.modern_oilfield_report_profile().brand_wordmark]
        expected.extend(f"{label}: {value}" if label else value for label, value in control.rows)
        bold = [True] + [False] * len(control.rows)
        assert TEXTS[language.value] in actual[0]
    else:
        expected = [page_label, renderer.modern_oilfield_report_profile().brand_wordmark,
                    page_label, compact_report_footer(control.snapshot)]
        bold = [False] * len(expected)
        assert page_label in actual[0]
    assert [text for text, _, _ in calls] == expected * 2
    assert [is_bold for _, _, is_bold in calls] == bold * 2
    for text, families, _ in calls:
        assert families == list(resolve_unicode_font_profile(text).families)
    if region == "header":
        assert any(len(text) > 100 for text in expected)
    else:
        assert len(expected[-1]) < len(template.properties["header_fields"]["header.confidentiality"])
    assert "…" in actual[0]
    _assert_baseline(baseline, actual)


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("page_format", ["A4", "A3", "roll"])
def test_control_unicode_after_package_reopen(qapp, tmp_path, language, page_format):
    session, template = _localized_form(language)
    template.page_format = page_format
    package = tmp_path / "control-unicode.geologpkg"
    ProjectController(session=session).save_project(package)
    restored = ProjectController().open_project(package)
    saved = restored.project.masterlog_templates[template.template_id]
    before = deepcopy(saved)
    depths = restored.current_dataset.depth.copy()
    values = restored.current_dataset.curve_by_mnemonic("C1").values.copy()
    target = renderer.export_masterlog_pdf(
        saved, restored, tmp_path / "control-unicode.pdf",
        settings=MasterlogOutputSettings(145, 355, language),
    )
    with fitz.open(target) as document:
        for page in document:
            text = page.get_text()
            assert TEXTS[language.value] in text
            assert renderer.REPORT_BRAND_WORDMARK in text
            assert "145 — 355 m" in text
            assert "STALE RANGE" not in text
    assert saved == before
    np.testing.assert_array_equal(restored.current_dataset.depth, depths)
    np.testing.assert_array_equal(restored.current_dataset.curve_by_mnemonic("C1").values, values)
