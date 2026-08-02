from __future__ import annotations

from types import SimpleNamespace

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QPen
from PySide6.QtWidgets import QApplication

from geoworkbench.printing.page_renderer import _tablet_raster_scale
from geoworkbench.printing.tablet_print import (
    _activate_print_curve_styles,
    _print_curve_width,
    _restore_print_curve_styles,
)
from geoworkbench.tablet.models import (
    CurveLineStyle,
    CurveStyle,
    TrackDefinition,
    TrackKind,
)


def test_high_quality_tablet_snapshot_has_real_supersampling_floor() -> None:
    assert _tablet_raster_scale(0.4, high_quality=True) == 2.5
    assert _tablet_raster_scale(3.2, high_quality=True) == 3.2
    assert _tablet_raster_scale(8.0, high_quality=True) == 4.0
    assert _tablet_raster_scale(8.0, high_quality=False) == 1.0


def test_print_curve_width_survives_dense_a4_fitting() -> None:
    assert _print_curve_width(0.8, 2) == 1.55
    assert _print_curve_width(0.8, 7) == 1.35
    assert _print_curve_width(2.4, 7) == 2.4


def test_print_snapshot_uses_configured_pen_and_restores_screen_pen() -> None:
    _application = QApplication.instance() or QApplication([])
    mnemonic = "PIXLER_C1_C2"
    definition = TrackDefinition(
        "pixler",
        "Pixler",
        TrackKind.GAS,
        curve_mnemonics=[mnemonic],
    )
    definition.set_curve_style(
        mnemonic,
        CurveStyle("#ff0000", 1.2, CurveLineStyle.DASH),
    )
    item = pg.PlotDataItem(
        [0.0, 1.0],
        [0.0, 1.0],
        pen=pg.mkPen("#123456", width=0.9),
    )
    rendered = SimpleNamespace(
        definition=definition,
        curve_items={mnemonic: item},
    )

    states = _activate_print_curve_styles((rendered,))  # type: ignore[arg-type]
    print_pen = QPen(item.opts["pen"])
    assert print_pen.color().name().lower() == "#ff0000"
    assert print_pen.widthF() >= 1.55
    assert print_pen.style() is Qt.PenStyle.DashLine

    _restore_print_curve_styles(states)
    restored_pen = QPen(item.opts["pen"])
    assert restored_pen.color().name().lower() == "#123456"
    assert restored_pen.widthF() == 0.9


def test_legacy_curve_without_persisted_style_keeps_live_colour_and_dash() -> None:
    _application = QApplication.instance() or QApplication([])
    mnemonic = "C1_C2"
    definition = TrackDefinition(
        "ratio",
        "Gas Ratio",
        TrackKind.GAS,
        curve_mnemonics=[mnemonic],
    )
    item = pg.PlotDataItem(
        [0.0, 1.0],
        [0.0, 1.0],
        pen=pg.mkPen("#00aa66", width=0.8, style=Qt.PenStyle.DotLine),
    )
    rendered = SimpleNamespace(
        definition=definition,
        curve_items={mnemonic: item},
    )

    states = _activate_print_curve_styles((rendered,))  # type: ignore[arg-type]
    print_pen = QPen(item.opts["pen"])
    assert print_pen.color().name().lower() == "#00aa66"
    assert print_pen.style() is Qt.PenStyle.DotLine
    assert print_pen.widthF() >= 1.55

    _restore_print_curve_styles(states)
    restored_pen = QPen(item.opts["pen"])
    assert restored_pen.color().name().lower() == "#00aa66"
    assert restored_pen.style() is Qt.PenStyle.DotLine
    assert restored_pen.widthF() == 0.8
