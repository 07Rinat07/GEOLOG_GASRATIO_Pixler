from copy import deepcopy

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QPainter, QPdfWriter

from geoworkbench.printing import masterlog_renderer as renderer
from geoworkbench.printing.image_assets import create_svg_asset
from geoworkbench.printing.masterlog_inspection import MasterlogInspection
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.printing.unicode_support import resolve_unicode_font_profile
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.masterlog_inspection_controller import MasterlogInspectionController
from geoworkbench.project.masterlog_symbol_controller import MasterlogSymbolController
from geoworkbench.services.localization import AppLanguage
from test_masterlog_control_layout import controlled_form


LABELS = {"ru": "Газопроявление", "kk": "Газ Әғқң", "en": "Gas show"}


def _fixture(tmp_path, language, anchor="depth"):
    session, template = controlled_form()
    column = template.columns[1]
    inspection = MasterlogInspection(
        column.column_id, LABELS[language.value], 150, "C1", 2, "м³/кг·µg",
        interval=(140, 160) if anchor == "interval" else None,
    )
    callout = MasterlogInspectionController(session).pin(template, inspection, language)
    source = tmp_path / "symbol.svg"
    source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
                      '<rect width="10" height="10" fill="#ff0000"/></svg>', encoding="utf-8")
    asset = create_svg_asset(source)
    session.image_assets[asset.asset_id] = asset
    symbol = MasterlogSymbolController(session).add(
        template.template_id, depth=140 if anchor == "interval" else 150,
        bottom_depth=160 if anchor == "interval" else None, anchor_type=anchor,
        column_id=column.column_id, asset_ref=asset.asset_id, width_mm=8, height_mm=8,
        label=LABELS[language.value],
    )
    return session, template, callout, symbol


def _paint(painter, session, template, kind):
    function = renderer._paint_inspection_callouts if kind == "inspection" else renderer._paint_depth_symbols
    function(painter, QRectF(0, 0, 180, 80), template, template.columns[1], session, (130, 170))


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", [72, 96, 144, 300, 600])
@pytest.mark.parametrize("anchor", ["depth", "interval"])
@pytest.mark.parametrize("kind", ["inspection", "symbol"])
def test_callout_unicode_pdf_preserves_anchor_geometry_and_dpi_baseline(
    qapp, tmp_path, monkeypatch, language, dpi, anchor, kind
):
    session, template, callout, _ = _fixture(tmp_path, language, anchor)
    before = deepcopy((template, session.current_well.canvas_objects, session.image_assets))
    source_values = session.current_dataset.curve_by_mnemonic("C1").values.copy()
    old_ui_font = QFont(qapp.font())
    calls = []
    original_print_font = renderer.print_font

    def capture(size, *, text):
        font = original_print_font(size, text=text)
        calls.append((size, text, font.families()))
        return font

    monkeypatch.setattr(renderer, "print_font", capture)
    snapshots = []
    expected = callout.properties["text"] if kind == "inspection" else LABELS[language.value]
    try:
        qapp.setFont(QFont("Courier New", 19))
        for index, resolution in enumerate((72, dpi)):
            target = tmp_path / f"callout-{index}.pdf"
            writer = QPdfWriter(str(target))
            writer.setResolution(resolution)
            painter = QPainter(writer)
            painter.scale(resolution / 25.4, resolution / 25.4)
            try:
                _paint(painter, session, template, kind)
            finally:
                painter.end()
            with fitz.open(target) as document:
                text = document[0].get_text()
                for line in expected.splitlines():
                    assert line in text
                spans = [span for block in document[0].get_text("dict")["blocks"]
                         if "lines" in block for line in block["lines"] for span in line["spans"]]
                drawings = [(draw["type"], draw["color"], draw["fill"], tuple(draw["rect"]))
                            for draw in document[0].get_drawings()]
                assert drawings
                snapshots.append((spans, drawings))
    finally:
        qapp.setFont(old_ui_font)
    assert (template, session.current_well.canvas_objects, session.image_assets) == before
    np.testing.assert_array_equal(session.current_dataset.curve_by_mnemonic("C1").values, source_values)
    assert len(calls) == 2
    for size, text, families in calls:
        assert size == renderer.modern_oilfield_report_profile().typography.caption_pt
        assert text == expected
        assert families == list(resolve_unicode_font_profile(text).families)
    baseline, actual = snapshots
    assert [span["text"] for span in actual[0]] == [span["text"] for span in baseline[0]]
    for base_span, actual_span in zip(baseline[0], actual[0]):
        assert actual_span["size"] == pytest.approx(base_span["size"], abs=0.08)
        assert actual_span["bbox"] == pytest.approx(base_span["bbox"], abs=0.3)
    assert len(actual[1]) == len(baseline[1])
    for base_draw, actual_draw in zip(baseline[1], actual[1]):
        assert actual_draw[:3] == base_draw[:3]
        assert actual_draw[3] == pytest.approx(base_draw[3], abs=0.3)


@pytest.mark.parametrize("kind", ["inspection", "symbol"])
@pytest.mark.parametrize("excluded", ["template", "column", "depth"])
def test_callout_font_resolution_keeps_existing_scope_filter(qapp, tmp_path, monkeypatch, kind, excluded):
    session, template, callout, symbol = _fixture(tmp_path, AppLanguage.KK)
    item = callout if kind == "inspection" else next(
        value for value in session.current_well.canvas_objects if value.object_id == symbol.object_id
    )
    if excluded == "template":
        item.properties["template_id"] = "other"
    elif excluded == "column":
        item.track_id = "other"
    else:
        item.top_depth = item.bottom_depth = 180

    def unexpected(*args, **kwargs):
        pytest.fail("Excluded object must not resolve a font")

    monkeypatch.setattr(renderer, "print_font", unexpected)
    writer = QPdfWriter(str(tmp_path / "excluded.pdf"))
    painter = QPainter(writer)
    try:
        _paint(painter, session, template, kind)
    finally:
        painter.end()


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("page_format", ["A4", "A3", "roll"])
def test_callouts_and_svg_export_after_package_reopen(qapp, tmp_path, language, page_format):
    session, template, callout, _ = _fixture(tmp_path, language, "interval")
    template.page_format = page_format
    package = tmp_path / "callouts.geologpkg"
    ProjectController(session=session).save_project(package)
    restored = ProjectController().open_project(package)
    saved = restored.project.masterlog_templates[template.template_id]
    before = deepcopy((saved, restored.current_well.canvas_objects, restored.image_assets))
    source_values = restored.current_dataset.curve_by_mnemonic("C1").values.copy()
    target = renderer.export_masterlog_pdf(
        saved, restored, tmp_path / "callouts.pdf", settings=MasterlogOutputSettings(130, 170, language),
    )
    with fitz.open(target) as document:
        text = "".join(page.get_text() for page in document)
        for line in callout.properties["text"].splitlines():
            assert line in text
        assert text.count(LABELS[language.value]) >= 2
        assert any(draw["fill"] == (1.0, 0.0, 0.0) for page in document for draw in page.get_drawings())
    assert (saved, restored.current_well.canvas_objects, restored.image_assets) == before
    np.testing.assert_array_equal(restored.current_dataset.curve_by_mnemonic("C1").values, source_values)
