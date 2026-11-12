from __future__ import annotations

import numpy as np
import pyqtgraph as pg
import pytest

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
            assert label.angle == {"horizontal": 0, "vertical_bottom_to_top": -90, "vertical_top_to_bottom": 90}[orientation]
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
        assert label.angle == -90.0
        assert interval.text_orientation == "horizontal"
    finally:
        view.close()
