from __future__ import annotations

import numpy as np
import pyqtgraph as pg
import pytest
from PySide6.QtCore import QPointF

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, StratigraphyInterval
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView


@pytest.mark.parametrize("orientation", ("horizontal", "vertical_bottom_to_top", "vertical_top_to_bottom"))
def test_stratigraphy_caption_stays_inside_visible_portion(qapp, orientation):
    dataset = Dataset("strat-data", "Stratigraphy", DatasetKind.GTI, DepthDomain.MD,
                      np.linspace(5600.0, 5900.0, 301))
    view = TabletView()
    view.resize(700, 650)
    try:
        view.set_layout_model(TabletLayout([
            TrackDefinition("strat", "Стратиграфия", TrackKind.STRATIGRAPHY, width=240),
        ]))
        view.set_stratigraphy([
            StratigraphyInterval("s", 5600.0, 5900.0, "C₁v", "Визейский ярус",
                                 color="#234567", text_orientation=orientation),
        ])
        view.set_dataset(dataset)
        view.show()
        qapp.processEvents()
        for top, bottom in ((5680.0, 5700.0), (5850.0, 5870.0)):
            view.set_visible_depth(top, bottom)
            qapp.processEvents()
            view._update_stratigraphy_text_visibility(top, bottom)
            bar, label = view._rendered["strat"].stratigraphy_items["s"]
            assert isinstance(label, pg.TextItem)
            assert bar.isVisible() and label.isVisible()
            assert top < label.pos().y() < bottom
            assert label.textItem.toPlainText() == "C₁v\nВизейский ярус"
            assert "5600–5900" in label.toolTip()
            assert label.angle == {"horizontal": 0, "vertical_bottom_to_top": 90, "vertical_top_to_bottom": -90}[orientation]
            label.updateTransform(force=True)
            delta = label.mapToScene(QPointF(1, 0)) - label.mapToScene(QPointF(0, 0))
            if orientation == "horizontal":
                assert delta.x() > 0 and abs(delta.y()) < 1e-6
            elif orientation == "vertical_bottom_to_top":
                assert delta.y() < 0 and abs(delta.x()) < 1e-6
            else:
                assert delta.y() > 0 and abs(delta.x()) < 1e-6
    finally:
        view.close()


def test_numeric_las_style_stratigraphy_code_visible_in_narrow_lane(qapp):
    dataset = Dataset("codes", "Codes", DatasetKind.GTI, DepthDomain.MD,
                      np.arange(100.0, 201.0))
    view = TabletView()
    view.resize(500, 600)
    try:
        view.set_layout_model(TabletLayout([
            TrackDefinition("strat", "Стратиграфия", TrackKind.STRATIGRAPHY, width=80),
        ]))
        view.set_stratigraphy([StratigraphyInterval("s", 100.0, 200.0, "7")])
        view.set_dataset(dataset)
        view.show()
        qapp.processEvents()
        view.set_visible_depth(110.0, 130.0)
        qapp.processEvents()
        view._update_stratigraphy_text_visibility(110.0, 130.0)
        bar, label = view._rendered["strat"].stratigraphy_items["s"]
        assert label.isVisible()
        assert label.textItem.toPlainText() == "7"
        assert "7" in bar.toolTip()
        assert 110.0 < label.pos().y() < 130.0
    finally:
        view.close()


def test_imported_las_name_and_code_fit_compact_column(qapp, tmp_path):
    from geoworkbench.project.session import ProjectSession
    from test_las_geology import _base_metadata, _small_geology_las, import_las_with_report

    source = tmp_path / "strat-labels.las"
    source.write_bytes(_small_geology_las(
        (" STRAT_CODE.CODE : Stratigraphy",),
        ("0 7", "1 7"),
        metadata=_base_metadata(stratigraphy=[{
            "top": 0.0, "bottom": 1.0, "short": "C1v",
            "name_ru": "Визейский ярус",
        }]),
    ))
    result = import_las_with_report(source)
    session = ProjectSession()
    well = session.add_dataset(
        result.dataset, "Test", source_document=result.source_document,
        import_report=result.report, create_new_well=True,
    )
    interval, = well.stratigraphy
    view = TabletView()
    view.resize(500, 650)
    try:
        view.set_layout_model(TabletLayout([
            TrackDefinition("strat", "Стратиграфия", TrackKind.STRATIGRAPHY, width=48),
        ]))
        view.set_stratigraphy(well.stratigraphy)
        view.set_dataset(result.dataset)
        view.show()
        qapp.processEvents()
        view._update_stratigraphy_text_visibility(*view.visible_depth_range)
        _, label = view._rendered["strat"].stratigraphy_items[interval.interval_id]
        assert label.isVisible()
        assert "C1v" in label.textItem.toPlainText()
        assert "Визейский ярус" in label.textItem.toPlainText()
        assert label.angle == 90.0
        label.updateTransform(force=True)
        delta = label.mapToScene(QPointF(1, 0)) - label.mapToScene(QPointF(0, 0))
        assert delta.y() < 0 and abs(delta.x()) < 1e-6
        assert interval.text_orientation == "horizontal"
    finally:
        view.close()


@pytest.mark.parametrize("position", ("top", "center", "bottom"))
def test_long_source_caption_fits_its_rank_lane_and_keeps_full_tooltip(qapp, position):
    dataset = Dataset("long-strat", "Stratigraphy", DatasetKind.GTI, DepthDomain.MD,
                      np.arange(100.0, 201.0))
    long_code = "C1v-" + "A123456789" * 20
    view = TabletView()
    view.resize(640, 650)
    try:
        view.set_layout_model(TabletLayout([
            TrackDefinition("strat", "Stratigraphy", TrackKind.STRATIGRAPHY, width=170),
        ]))
        view.set_stratigraphy([
            StratigraphyInterval("system", 100.0, 200.0, long_code,
                                 rank="System / Period", text_position=position),
            StratigraphyInterval("stage", 100.0, 200.0, "C₁v", "Visean",
                                 rank="Stage / Age"),
        ])
        view.set_dataset(dataset)
        view.show()
        qapp.processEvents()
        view.set_visible_depth(110.0, 130.0)
        qapp.processEvents()
        view._update_stratigraphy_text_visibility(110.0, 130.0)
        rendered = view._rendered["strat"]
        bar, label = rendered.stratigraphy_items["system"]
        _, stage = rendered.stratigraphy_items["stage"]
        assert label.isVisible() and stage.isVisible()
        text = label.textItem.toPlainText()
        assert text.endswith("…") and long_code.startswith(text[:-1])
        assert long_code in label.toolTip() and long_code in bar.toolTip()
        assert label.pos().x() != stage.pos().x()
        box = rendered.plot.getViewBox()
        rect = label.textItem.boundingRect()
        width = rect.height() if label.angle else rect.width()
        height = rect.width() if label.angle else rect.height()
        assert width + 4 <= box.width() * 0.94 / 2
        half_md = (height / 2 + 2) / box.height() * 20
        assert 110.0 <= label.pos().y() - half_md + 1e-8
        assert label.pos().y() + half_md <= 130.0 + 1e-8
        if position == "top":
            assert label.pos().y() < 120.0
        elif position == "bottom":
            assert label.pos().y() > 120.0
        else:
            assert label.pos().y() == pytest.approx(120.0)
        assert view._stratigraphy[0].code == long_code
    finally:
        view.close()
