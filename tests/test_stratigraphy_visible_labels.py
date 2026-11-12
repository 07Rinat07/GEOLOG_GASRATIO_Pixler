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
