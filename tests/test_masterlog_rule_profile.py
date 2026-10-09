from copy import deepcopy
from dataclasses import replace

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QPdfWriter

from geoworkbench.domain.models import CuttingsComponent, MasterlogColumnTemplate
from geoworkbench.printing import masterlog_renderer as renderer
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.project.controller import ProjectController
from geoworkbench.services.localization import AppLanguage
from test_masterlog_callout_unicode import _fixture as callout_fixture
from test_masterlog_default_typography import CATALOG
from test_masterlog_description_unicode import DESCRIPTIONS, _session
from test_masterlog_geology_label_unicode import _fixture as geology_fixture


KINDS = ["lithology", "cuttings", "calcimetry", "stratigraphy", "lba", "rock_text", "sample_text", "interpretation", "inspection", "swatch", "missing_swatch"]


def _profile(kind):
    visual = modern_oilfield_report_profile(grayscale=kind == "grayscale")
    if kind != "custom":
        return visual
    return replace(visual, palette=replace(visual.palette, page="#fafbfc", text="#102030",
                   border="#405060", border_strong="#203040", critical="#a01020"),
                   layout=replace(visual.layout, thin_rule_pt=1.2, strong_rule_pt=2.4))


def _geology():
    session, template = _session()
    other, _ = geology_fixture()
    session.current_well.stratigraphy = deepcopy(other.current_well.stratigraphy)
    sample = session.current_well.cuttings[0]
    sample.components = [CuttingsComponent("sand", 100)]
    sample.calcite_percent, sample.dolomite_percent = 0, 25
    sample.lba_type_id, sample.lba_color, sample.lba_intensity = "light", "БГ", 3
    session.current_well.lithology[0].lithotype_id = "sand"
    return session, template


def _paint(painter, session, template, language, kind):
    rect = QRectF(0, 0, 170, 70)
    column = MasterlogColumnTemplate("geology", "Geology", kind, 170)
    depth = (130, 170)
    if kind == "lithology":
        renderer._paint_lithology_column(painter, rect, column, session, depth, CATALOG)
    elif kind == "cuttings":
        renderer._paint_cuttings_column(painter, rect, column, session, depth, CATALOG)
    elif kind == "calcimetry":
        renderer._paint_calcimetry_column(painter, rect, column, session.current_dataset, session, depth, {})
    elif kind == "stratigraphy":
        renderer._paint_stratigraphy_column(painter, rect, session, depth, language)
    elif kind == "lba":
        renderer._paint_lba_column(painter, rect, column, session, depth, language)
    elif kind == "rock_text":
        renderer._paint_lithology_descriptions(painter, rect, session, depth, language, CATALOG)
    elif kind == "sample_text":
        renderer._paint_cuttings_descriptions(painter, rect, session, depth, language)
    elif kind == "interpretation":
        renderer._paint_sample_interpretations(painter, rect, session, depth, language)
    elif kind == "inspection":
        renderer._paint_inspection_callouts(painter, rect, template, template.columns[1], session, depth)
    else:
        renderer._paint_lithotype_swatch(painter, QRectF(0, 0, 120, 20),
                    {"lithotype_id": "sand" if kind == "swatch" else "missing", "frame": True}, language, CATALOG)


def _snapshot(tmp_path, name, dpi, paint):
    target = tmp_path / f"{name}.pdf"
    writer = QPdfWriter(str(target))
    writer.setResolution(dpi)
    painter = QPainter(writer)
    painter.scale(dpi / 25.4, dpi / 25.4)
    # Production columns inherit the physical font established by their heading.
    renderer._set_scaled_unicode_font_points(painter, "Geology", renderer.modern_oilfield_report_profile().typography.table_pt)
    try:
        paint(painter)
    finally:
        painter.end()
    with fitz.open(target) as document:
        return document[0].get_text(), document[0].get_drawings(), document[0].get_text("dict")


def _rgb(hex_color):
    return tuple(int(hex_color[i:i+2], 16) / 255 for i in (1, 3, 5))


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", [72, 96, 144, 300, 600])
@pytest.mark.parametrize("profile", ["default", "grayscale", "custom"])
@pytest.mark.parametrize("kind", KINDS)
def test_masterlog_rules_keep_geometry_and_semantic_colours_at_physical_dpi(qapp, tmp_path, monkeypatch, language, dpi, profile, kind):
    session, template = callout_fixture(tmp_path, language)[:2] if kind == "inspection" else _geology()
    before = deepcopy((template, session.current_well.lithology, session.current_well.cuttings,
                       session.current_well.stratigraphy, session.current_well.canvas_objects))
    source = session.current_dataset.curve_by_mnemonic("C1").values.copy()
    def paint(p):
        _paint(p, session, template, language, kind)
    original = _snapshot(tmp_path, "original", 72, paint)
    visual = _profile(profile)
    monkeypatch.setattr(renderer, "modern_oilfield_report_profile", lambda: visual)
    baseline = _snapshot(tmp_path, "baseline", 72, paint)
    actual = _snapshot(tmp_path, "actual", dpi, paint)
    assert actual[0] == baseline[0] == original[0]
    assert len(actual[1]) == len(baseline[1]) == len(original[1])
    for old, base, draw in zip(original[1], baseline[1], actual[1]):
        assert tuple(base["rect"]) == pytest.approx(tuple(old["rect"]), abs=0.3)
        assert tuple(draw["rect"]) == pytest.approx(tuple(base["rect"]), abs=0.3)
        assert draw["width"] == pytest.approx(base["width"], abs=0.03)
        if kind == "interpretation" and old["fill"] is not None:
            assert draw["fill"] == base["fill"] == pytest.approx(_rgb(visual.palette.table_alt), abs=0.002)
        elif kind != "inspection":
            assert draw["fill"] == base["fill"] == old["fill"]
        assert draw["color"] == base["color"]
    role = "critical" if kind in ("inspection", "missing_swatch") else (
            "border" if kind in ("lba", "rock_text", "sample_text", "swatch") else "border_strong")
    rules = [draw for draw in actual[1] if draw["color"] == pytest.approx(_rgb(getattr(visual.palette, role)), abs=0.002)]
    assert rules
    expected = [visual.layout.strong_rule_pt] if kind == "missing_swatch" else [visual.layout.thin_rule_pt]
    if kind == "inspection":
        expected.append(visual.layout.strong_rule_pt)
        fill = next(draw for draw in actual[1] if draw["fill"] is not None)
        assert fill["fill"] == pytest.approx(_rgb(visual.palette.page), abs=0.002)
        assert fill["fill_opacity"] == pytest.approx(225 / 255, abs=0.002)
        spans = [span for block in actual[2]["blocks"] if "lines" in block for line in block["lines"] for span in line["spans"]]
        assert spans and all(span["color"] == int(visual.palette.text[1:], 16) for span in spans)
    for width in expected:
        assert any(draw["width"] == pytest.approx(width, abs=0.03) for draw in rules)
    if kind == "swatch":
        frame = [draw for draw in actual[1] if draw["color"] == pytest.approx(_rgb(visual.palette.border_strong), abs=0.002)]
        assert any(draw["width"] == pytest.approx(visual.layout.strong_rule_pt, abs=0.03) for draw in frame)
    if kind in ("calcimetry", "lba"):
        old_neutral = {_rgb(modern_oilfield_report_profile().palette.border), _rgb(modern_oilfield_report_profile().palette.border_strong)}
        # Factual component lines and intensity glyphs keep their own widths/colours.
        for old, draw in zip(original[1], actual[1]):
            if old["color"] is not None and not any(old["color"] == pytest.approx(c, abs=0.002) for c in old_neutral):
                assert draw["color"] == old["color"]
                assert draw["width"] == pytest.approx(old["width"], abs=0.03)
    assert (template, session.current_well.lithology, session.current_well.cuttings,
            session.current_well.stratigraphy, session.current_well.canvas_objects) == before
    np.testing.assert_array_equal(session.current_dataset.curve_by_mnemonic("C1").values, source)


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("page_format", ["A4", "A3", "roll"])
@pytest.mark.parametrize("profile", ["default", "grayscale", "custom"])
def test_masterlog_rule_profile_export_after_reopen(qapp, tmp_path, monkeypatch, language, page_format, profile):
    session, template = _geology()
    template.page_format = page_format
    template.columns = [MasterlogColumnTemplate("depth", "Depth", "depth", 20),
        MasterlogColumnTemplate("rock", "Rock", "description", 60),
        MasterlogColumnTemplate("lba", "LBA", "lba", 40),
        MasterlogColumnTemplate("calc", "Calcimetry", "calcimetry", 40),
        MasterlogColumnTemplate("strat", "Stratigraphy", "stratigraphy", 40)]
    target = tmp_path / "rules.geologpkg"
    ProjectController(session=session).save_project(target)
    restored = ProjectController().open_project(target)
    saved = restored.project.masterlog_templates[template.template_id]
    before = deepcopy((saved, restored.current_well.lithology, restored.current_well.cuttings, restored.current_well.stratigraphy))
    source = restored.current_dataset.curve_by_mnemonic("C1").values.copy()
    visual = _profile(profile)
    monkeypatch.setattr(renderer, "modern_oilfield_report_profile", lambda: visual)
    output = renderer.export_masterlog_pdf(saved, restored, tmp_path / "masterlog.pdf", settings=MasterlogOutputSettings(130, 170, language))
    with fitz.open(output) as document:
        text = " ".join(" ".join(page.get_text() for page in document).split())
        assert DESCRIPTIONS[language.value] in text
        assert "БГ" in text and "K₁" in text
        drawings = [draw for page in document for draw in page.get_drawings() if draw["color"] is not None]
        assert any(draw["width"] == pytest.approx(visual.layout.thin_rule_pt, abs=0.03) for draw in drawings)
    assert (saved, restored.current_well.lithology, restored.current_well.cuttings, restored.current_well.stratigraphy) == before
    np.testing.assert_array_equal(restored.current_dataset.curve_by_mnemonic("C1").values, source)


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("profile", ["default", "grayscale", "custom"])
def test_saved_swatch_colours_and_size_keep_priority(qapp, tmp_path, monkeypatch, language, profile):
    visual = _profile(profile)
    monkeypatch.setattr(renderer, "modern_oilfield_report_profile", lambda: visual)
    properties = {"lithotype_id": "sand", "frame": True, "frame_color": "#123456",
                  "background": "#abcdef", "color": "#654321", "font_size_mm": 3.7}
    before = deepcopy(properties)
    sizes = []
    original = renderer._set_scaled_font_mm
    def record(painter, font, size):
        sizes.append(size)
        original(painter, font, size)
    monkeypatch.setattr(renderer, "_set_scaled_font_mm", record)
    def paint(painter):
        renderer._paint_lithotype_swatch(painter, QRectF(0, 0, 120, 20), properties, language, CATALOG)
    text, drawings, content = _snapshot(tmp_path, "saved-swatch", 300, paint)
    assert CATALOG["sand"].localized_name(language.value) in text
    assert 3.7 in sizes and properties == before
    assert any(draw["fill"] == pytest.approx(_rgb("#abcdef"), abs=0.002) for draw in drawings)
    assert any(draw["color"] == pytest.approx(_rgb("#123456"), abs=0.002)
               and draw["width"] == pytest.approx(visual.layout.strong_rule_pt, abs=0.03) for draw in drawings)
    spans = [span for block in content["blocks"] if "lines" in block for line in block["lines"] for span in line["spans"]]
    assert spans and all(span["color"] == 0x654321 for span in spans)
