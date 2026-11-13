"""Uniform readable rock captions preserve source records and editable growth."""

from copy import deepcopy

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPdfWriter, QTextOption

from geoworkbench.domain.models import CuttingsSample, Dataset, DatasetKind, DepthDomain, LithologyInterval
from geoworkbench.printing import masterlog_renderer as renderer
from geoworkbench.printing.rock_description_presentation import (
    ROCK_DESCRIPTION_POINT_SIZE, rock_description_plain_text,
)
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.daily_las_growth import analyze_daily_las_growth, apply_daily_las_growth
from geoworkbench.services.localization import AppLanguage
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView
from geoworkbench.ui.rock_description_dialog import RockDescriptionDialog


def _dataset(identifier, depth):
    dataset = Dataset(identifier, identifier, DatasetKind.GTI, DepthDomain.MD,
                      np.asarray(depth, dtype=float), headers={"WELL": "Test"})
    dataset.upsert_curve("ROP", np.asarray(depth, dtype=float), unit="m/h", provenance="source")
    return dataset


def _view(dataset, samples, intervals=(), *, show_borders=True):
    view = TabletView()
    view.resize(640, 650)
    view.set_cuttings(list(samples), refresh=False)
    view.set_lithology(list(intervals), (), refresh=False)
    view.set_layout_and_dataset(TabletLayout([
        TrackDefinition("rock", "Описание пород", TrackKind.TEXT, width=300,
                        show_description_borders=show_borders),
    ]), dataset)
    view.show()
    return view


def _assert_font(item):
    font = item.textItem.font()
    assert font.pointSizeF() == ROCK_DESCRIPTION_POINT_SIZE
    assert not font.bold() and not font.italic() and not font.underline()
    assert item.textItem.document().defaultTextOption().alignment() == Qt.AlignmentFlag.AlignLeft


def test_source_text_normalization_is_display_only(qapp):
    assert rock_description_plain_text("Пор <5% >2%\r\nCaCO₃") == "Пор <5% >2%\nCaCO₃"
    rich = '<p style="font-size:22pt"><b>Известняк</b></p><p>Құмтас &amp; sandstone</p>'
    assert rock_description_plain_text(rich) == "Известняк\nҚұмтас & sandstone"
    assert rock_description_plain_text("Песчаник <b>средний</b>", rich=False) == "Песчаник <b>средний</b>"


def test_short_long_and_fallback_descriptions_share_font_and_reflow(qapp):
    dataset = _dataset("uniform", np.arange(100, 161))
    long_text = " ".join(["Известняк плотный, мелкокристаллический, CaCO₃ 97%."] * 20)
    samples = [
        CuttingsSample("short", 100, 110, description="Бурение с отбором керна №3."),
        CuttingsSample("long", 110, 120,
                       description=f'<p style="font-size:28pt; text-align:right"><b>{long_text}</b></p>'),
    ]
    intervals = [LithologyInterval("fallback", 120, 160, "limestone", description="Известняк серый.")]
    before = deepcopy((samples, intervals))
    view = _view(dataset, samples, intervals)
    try:
        view.set_visible_depth(100, 160)
        qapp.processEvents()
        view._update_lithology_text_visibility(100, 160)
        items = view._rendered["rock"].lithology_description_items
        assert items is not None
        assert set(items) == {"short", "long", "fallback"}
        for item in items.values():
            assert item.isVisible()
            _assert_font(item)
        assert items["short"].toPlainText() == samples[0].description
        assert items["long"].toPlainText().endswith("…")
        assert long_text in items["long"].toolTip()
        assert items["fallback"].toPlainText() == intervals[0].description
        initial = len(items["long"].toPlainText())
        view.set_visible_depth(110, 120)
        qapp.processEvents()
        view._update_lithology_text_visibility(110, 120)
        item = view._rendered["rock"].lithology_description_items["long"]
        _assert_font(item)
        assert len(item.toPlainText()) > initial
        view.set_visible_depth(113, 118)
        qapp.processEvents()
        view._update_lithology_text_visibility(113, 118)
        item = view._rendered["rock"].lithology_description_items["long"]
        assert item.isVisible() and 113 < item.pos().y() < 118
        _assert_font(item)
        assert (samples, intervals) == before
    finally:
        view.close()


def test_explicit_no_wrap_preserves_font_and_full_text(qapp):
    sample = CuttingsSample("nowrap", 100, 120, description="Длинное описание " * 25,
                            description_word_wrap=False)
    view = _view(_dataset("nowrap", np.arange(100, 121)), [sample])
    try:
        view.set_visible_depth(100, 120)
        qapp.processEvents()
        view._update_lithology_text_visibility(100, 120)
        item = view._rendered["rock"].lithology_description_items["nowrap"]
        assert item.isVisible() and item.toPlainText().endswith("…")
        _assert_font(item)
        assert item.textItem.document().defaultTextOption().wrapMode() == QTextOption.WrapMode.NoWrap
        assert sample.description.strip() in item.toolTip()
    finally:
        view.close()


def test_borderless_short_intervals_keep_full_hover_text(qapp):
    sample = CuttingsSample("tiny", 100, 100.1, description="Известняк <5% пор.")
    layer = LithologyInterval("tiny-layer", 101, 101.1, "limestone",
                              description="Плотный известняк.")
    before = deepcopy((sample, layer))
    view = _view(_dataset("tiny", np.arange(100, 161)), [sample], [layer],
                 show_borders=False)
    try:
        view.set_visible_depth(100, 160)
        qapp.processEvents()
        view._update_lithology_text_visibility(100, 160)
        rendered = view._rendered["rock"]
        assert rendered.lithology_description_items is not None
        assert rendered.description_frames is not None
        for identity, expected in (("tiny", "Известняк &lt;5% пор."),
                                   ("tiny-layer", "Плотный известняк.")):
            item = rendered.lithology_description_items[identity]
            frame = rendered.description_frames[identity]
            assert not item.isVisible()
            assert frame.isVisible() and frame.contains(frame.rect().center())
            assert expected in frame.toolTip()
            assert frame.pen().style() == Qt.PenStyle.NoPen
            assert frame.brush().color().alpha() == 0
            assert frame.acceptedMouseButtons() == Qt.MouseButton.NoButton
        assert (sample, layer) == before
    finally:
        view.close()


def test_appended_depth_and_edited_descriptions_keep_same_style(qapp):
    target = _dataset("old", [100, 101, 102])
    source = _dataset("incoming", [102, 103, 104])
    session = ProjectSession()
    well = session.add_dataset(target, "Test", create_new_well=True)
    controller = CuttingsController(session)
    old = controller.set_description(100, 102, "<p><b>Известняк</b></p>")
    original = deepcopy(old)
    plan = analyze_daily_las_growth(target, source, source_name="new.las", source_sha256="a" * 64)
    apply_daily_las_growth(target, source, plan)
    assert target.depth.tolist() == [100, 101, 102, 103, 104]
    assert well.cuttings == [original]  # numeric growth does not invent descriptions
    added = controller.set_description(102, 104, '<p style="font-size:20pt">Новые данные</p>')
    view = _view(target, well.cuttings)
    try:
        view.set_visible_depth(100, 104)
        qapp.processEvents()
        view._update_lithology_text_visibility(100, 104)
        items = view._rendered["rock"].lithology_description_items
        assert items[added.sample_id].toPlainText() == "Новые данные"
        for item in items.values():
            _assert_font(item)
        dialog = RockDescriptionDialog(102, 104, language=AppLanguage.RU, sample=added)
        try:
            assert dialog.editor.editor.toPlainText() == "Новые данные"
            dialog.editor.editor.setPlainText("Уточнено геологом")
            controller.update_description(added.sample_id, top_depth=102, bottom_depth=104,
                                          description=dialog.description_html)
        finally:
            dialog.close()
        view.set_cuttings(well.cuttings)
        view.set_visible_depth(100, 104)
        qapp.processEvents()
        view._update_lithology_text_visibility(100, 104)
        item = view._rendered["rock"].lithology_description_items[added.sample_id]
        assert item.toPlainText() == "Уточнено геологом"
        _assert_font(item)
        assert old == original and len(well.cuttings) == 2
    finally:
        view.close()


@pytest.mark.parametrize("dpi", [72, 300])
def test_pdf_uses_same_physical_size_for_short_and_elided_text(qapp, tmp_path, dpi):
    target = _dataset("print", np.arange(100, 121))
    session = ProjectSession()
    well = session.add_dataset(target, "Test", create_new_well=True)
    well.cuttings = [
        CuttingsSample("short", 100, 110, description="Известняк."),
        CuttingsSample("long", 110, 120, description='<p style="font-size:26pt">' +
                       "Плотный известняк " * 60 + "</p>"),
    ]
    before = deepcopy(well.cuttings)
    path = tmp_path / f"fixed-{dpi}.pdf"
    writer = QPdfWriter(str(path))
    writer.setResolution(dpi)
    painter = QPainter(writer)
    try:
        painter.scale(dpi / 25.4, dpi / 25.4)
        renderer._paint_cuttings_descriptions(painter, QRectF(0, 0, 55, 20), session, (100, 120))
    finally:
        painter.end()
    with fitz.open(path) as doc:
        page = doc[0]
        text = page.get_text()
        assert "Известняк." in text and "Плотный" in text and "…" in text
        spans = [s for block in page.get_text("dict")["blocks"] if "lines" in block
                 for line in block["lines"] for s in line["spans"]]
        assert spans
        assert all(s["size"] == pytest.approx(ROCK_DESCRIPTION_POINT_SIZE, abs=0.3) for s in spans)
    assert well.cuttings == before


def test_real_las_description_import_uses_uniform_style(qapp, tmp_path):
    from geoworkbench.data.las_adapter import import_las_with_report

    source = tmp_path / "description.las"
    raw = "\n".join((
        "~Version Information", " VERS. 2.0 : LAS 2.0", " WRAP. NO : One row",
        "~Well Information", " STRT.M 100 : Start", " STOP.M 104 : Stop",
        " STEP.M 1 : Step", " NULL. -999.25 : Null", " WELL. Test : Well",
        "~Curve Information", " DEPT.M : Depth",
        " ОПИСАНИЕ_ID.CODE : ID описания",
        "~Other information",
        "# DESC id=1; top=100; bottom=104; text=Известняк плотный, CaCO3 97%.",
        "~ASCII Log Data", "100 1", "101 1", "102 1", "103 1", "104 1", "",
    )).encode("cp1251")
    source.write_bytes(raw)
    imported = import_las_with_report(source)
    session = ProjectSession()
    well = session.add_dataset(imported.dataset, "Test", create_new_well=True,
                               source_document=imported.source_document,
                               import_report=imported.report)
    sample, = well.cuttings
    assert sample.description == "Известняк плотный, CaCO3 97%."
    view = _view(imported.dataset, well.cuttings)
    try:
        view.set_visible_depth(100, 104)
        qapp.processEvents()
        view._update_lithology_text_visibility(100, 104)
        item = view._rendered["rock"].lithology_description_items[sample.sample_id]
        assert item.toPlainText() == sample.description
        _assert_font(item)
        assert source.read_bytes() == raw
    finally:
        view.close()
