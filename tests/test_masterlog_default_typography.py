from copy import deepcopy

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QRectF, QSizeF
from PySide6.QtGui import QFont, QPainter, QPdfWriter

from geoworkbench.domain.annotation_style import AnnotationStyle
from geoworkbench.domain.models import MasterlogHeaderElement
from geoworkbench.printing import masterlog_renderer as renderer
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.printing.unicode_support import resolve_unicode_font_profile
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.lithotype_catalog_models import CatalogLithotype
from geoworkbench.services.localization import AppLanguage
from test_masterlog_control_layout import controlled_form


TEXTS = {"ru": "Песчаник", "kk": "Құмтас Әғқң", "en": "Sandstone"}
CATALOG = {"sand": CatalogLithotype("sand", "S", TEXTS["ru"], TEXTS["en"],
                                  "sedimentary", "#ffee00", "solid", False, TEXTS["kk"])}


def _paint_header(painter, session, template, language, kind, override):
    rect = QRectF(0, 0, 120, 20)
    if kind == "text":
        properties = {f"text_{key}": value for key, value in TEXTS.items()}
        if override:
            properties.update(font_size_mm=3.7, bold=True)
        element = MasterlogHeaderElement("title", "text", 0, 0, 120, 20, properties)
        renderer._paint_header_element(painter, element, session, template, None, language, CATALOG)
    elif kind == "placeholder":
        properties = {f"placeholder_text_{key}": value for key, value in TEXTS.items()}
        if override:
            properties["placeholder_font_size_mm"] = 3.7
        renderer._paint_image_placeholder(painter, rect, properties, language)
    else:
        properties = {"lithotype_id": "sand", "display_mode": "pattern_code_name"}
        if override:
            properties.update(font_size_mm=3.7, bold=True)
        renderer._paint_lithotype_swatch(painter, rect, properties, language, CATALOG)


def _pdf_snapshot(tmp_path, name, dpi, paint):
    target = tmp_path / f"{name}.pdf"
    writer = QPdfWriter(str(target))
    writer.setResolution(dpi)
    painter = QPainter(writer)
    painter.scale(dpi / 25.4, dpi / 25.4)
    try:
        paint(painter)
    finally:
        painter.end()
    with fitz.open(target) as document:
        spans = [span for block in document[0].get_text("dict")["blocks"]
                 if "lines" in block for line in block["lines"] for span in line["spans"]]
        return document[0].get_text(), spans


def _assert_baseline(baseline, actual):
    assert actual[0] == baseline[0]
    assert len(actual[1]) == len(baseline[1])
    for base_span, actual_span in zip(baseline[1], actual[1]):
        assert actual_span["size"] == pytest.approx(base_span["size"], abs=0.08)
        assert actual_span["bbox"] == pytest.approx(base_span["bbox"], abs=0.3)


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", [72, 96, 144, 300, 600])
@pytest.mark.parametrize("kind", ["text", "placeholder", "swatch"])
@pytest.mark.parametrize("override", [False, True])
def test_header_default_font_uses_actual_unicode_and_keeps_saved_sizes(
    qapp, tmp_path, monkeypatch, language, dpi, kind, override
):
    session, template = controlled_form()
    calls = []
    sizes = []
    original_print_font = renderer.print_font
    original_scaled_font = renderer._set_scaled_font_mm

    def capture_size(painter, font, size):
        sizes.append(size)
        original_scaled_font(painter, font, size)

    def capture(*args, **kwargs):
        font = original_print_font(*args, **kwargs)
        calls.append((kwargs["text"], font.families(), font.bold()))
        return font

    monkeypatch.setattr(renderer, "print_font", capture)
    monkeypatch.setattr(renderer, "_set_scaled_font_mm", capture_size)
    old_font = QFont(qapp.font())
    try:
        qapp.setFont(QFont("Courier New", 19))
        def paint(painter):
            _paint_header(painter, session, template, language, kind, override)
        baseline = _pdf_snapshot(tmp_path, "baseline", 72, paint)
        actual = _pdf_snapshot(tmp_path, "actual", dpi, paint)
    finally:
        qapp.setFont(old_font)
    expected = ("S — " if kind == "swatch" else "") + TEXTS[language.value]
    assert expected in actual[0]
    assert len(calls) == 2
    for text, families, bold in calls:
        assert text == expected
        assert families == list(resolve_unicode_font_profile(text).families)
        assert bold == (override or kind == "placeholder")
    _assert_baseline(baseline, actual)
    if override:
        assert sizes == [3.7, 3.7]


@pytest.mark.parametrize("depth_range", [(-12.5, 12.5), (1000000, 1000010)])
@pytest.mark.parametrize("dpi", [72, 96, 144, 300, 600])
def test_depth_labels_use_profile_font_and_preserve_signed_aligned_grid(qapp, tmp_path, monkeypatch, depth_range, dpi):
    calls = []
    original_print_font = renderer.print_font

    def capture(size, *, text):
        font = original_print_font(size, text=text)
        calls.append((size, text, font.families()))
        return font

    monkeypatch.setattr(renderer, "print_font", capture)
    expected = [f"{value:g}" for value, _ in renderer._aligned_depth_grid_values(depth_range, 1)]
    old_font = QFont(qapp.font())
    try:
        qapp.setFont(QFont("Courier New", 19))
        def paint(painter):
            renderer._paint_depth_axis(painter, QRectF(0, 8, 35, 160), depth_range)
        baseline = _pdf_snapshot(tmp_path, "baseline", 72, paint)
        actual = _pdf_snapshot(tmp_path, "actual", dpi, paint)
    finally:
        qapp.setFont(old_font)
    for label in expected:
        assert label in actual[0]
    assert [text for _, text, _ in calls] == expected * 2
    for size, text, families in calls:
        assert size == renderer.modern_oilfield_report_profile().typography.table_pt
        assert families == list(resolve_unicode_font_profile(text).families)
    _assert_baseline(baseline, actual)


@pytest.mark.parametrize("dpi", [72, 96, 144, 300, 600])
def test_explicit_annotation_font_contract_remains(qapp, tmp_path, dpi):
    style = AnnotationStyle(font_family="Courier New", font_size=9, bold=True, italic=True, underline=True)

    def paint(painter):
        renderer._paint_annotation_text(painter, QRectF(0, 0, 100, 30), "Saved annotation", style)
        assert painter.font().family() == style.font_family
        assert painter.font().bold() and painter.font().italic() and painter.font().underline()

    baseline = _pdf_snapshot(tmp_path, "baseline", 72, paint)
    actual = _pdf_snapshot(tmp_path, "actual", dpi, paint)
    _assert_baseline(baseline, actual)


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", [72, 96, 144, 300, 600])
def test_simple_footer_keeps_unicode_and_searchable_brand(qapp, tmp_path, monkeypatch, language, dpi):
    session, template = controlled_form()
    template.columns = []
    template.header_elements = []
    monkeypatch.setattr(renderer, "masterlog_document_control_layout", lambda *args, **kwargs: None)
    label = TEXTS[language.value]
    def paint(painter):
        renderer.paint_masterlog(
            painter, QRectF(0, 0, 180, 240), template, session,
            canvas_size_mm=QSizeF(180, 240), page_label=label,
        )
    baseline = _pdf_snapshot(tmp_path, "baseline", 72, paint)
    actual = _pdf_snapshot(tmp_path, "actual", dpi, paint)
    assert label in actual[0]
    assert renderer.REPORT_BRAND_WORDMARK in actual[0]
    _assert_baseline(baseline, actual)


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("page_format", ["A4", "A3", "roll"])
def test_default_typography_exports_after_reopen(qapp, tmp_path, language, page_format):
    session, template = controlled_form()
    template.page_format = page_format
    template.header_elements = [MasterlogHeaderElement("title", "text", 5, 5, 150, 15,
                               {f"text_{key}": value for key, value in TEXTS.items()})]
    package = tmp_path / "typography.geologpkg"
    ProjectController(session=session).save_project(package)
    restored = ProjectController().open_project(package)
    saved = restored.project.masterlog_templates[template.template_id]
    before = deepcopy(saved)
    source_values = restored.current_dataset.curve_by_mnemonic("C1").values.copy()
    target = renderer.export_masterlog_pdf(saved, restored, tmp_path / "typography.pdf",
                                          settings=MasterlogOutputSettings(130, 170, language))
    with fitz.open(target) as document:
        text = "".join(page.get_text() for page in document)
        assert TEXTS[language.value] in text
        assert "150" in text
    assert saved == before
    np.testing.assert_array_equal(restored.current_dataset.curve_by_mnemonic("C1").values, source_values)
