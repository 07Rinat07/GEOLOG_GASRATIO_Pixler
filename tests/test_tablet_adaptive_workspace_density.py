"""Adaptive tablet workspace: keep curves, depth and print geometry intact."""

from copy import deepcopy

import numpy as np
import pytest
from PySide6.QtCore import QPoint

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.services.localization import AppLanguage
from geoworkbench.tablet.header_geometry import (
    compact_curve_header_rows, curve_header_viewport_height, tablet_compact_screen,
)
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView


@pytest.mark.parametrize("width,height,compact", [
    (900, 540, True), (1280, 580, True), (1600, 680, True),
    (1800, 900, False), (2400, 1200, False),
])
def test_screen_density_uses_logical_workspace_dimensions(width, height, compact):
    assert tablet_compact_screen("auto", width, height) is compact
    assert tablet_compact_screen("compact", width, height)
    assert not tablet_compact_screen("full", width, height)


def test_header_budget_keeps_complete_rows():
    assert compact_curve_header_rows(360, 96) == 1
    assert compact_curve_header_rows(520, 96) == 2
    assert compact_curve_header_rows(2000, 96) == 2


@pytest.mark.parametrize("language", list(AppLanguage))
def test_compact_tablet_keeps_aligned_plots_and_editing(qapp, language):
    depth = np.arange(100.0, 201.0)
    dataset = Dataset("responsive", "Responsive", DatasetKind.GTI, DepthDomain.MD, depth)
    names = [f"S{i}" for i in range(1, 10)]
    for i, name in enumerate(names):
        dataset.upsert_curve(name, depth + i, unit="m/h", provenance="las:source")
    layout = TabletLayout([
        TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120,
                        title_orientation="vertical_bottom_to_top"),
        TrackDefinition("dense", "Dense curves", TrackKind.CURVE,
                        curve_mnemonics=names, width=360),
        TrackDefinition("text", "Description", TrackKind.TEXT, width=300),
    ])
    view = TabletView(language=language)
    view.resize(1280, 600)
    view.set_layout_and_dataset(layout, dataset)
    view.show()
    view.set_visible_depth(120, 170)
    original = deepcopy(layout.tracks)
    values = {name: dataset.curve_by_mnemonic(name).values.copy() for name in names}
    try:
        def settle():
            qapp.processEvents()
            view._restore_visible_depth_after_resize()
            qapp.processEvents()

        settle()
        tracks = [entry.widget for entry in view._rendered.values()]
        dense = view._rendered["dense"].widget
        for width, height in ((900, 540), (1280, 580), (1600, 680)):
            view.resize(width, height)
            settle()
            assert view._compact_screen()
            assert view._curve_pencil_scroll.isHidden()
            assert view._compact_pencil_button.isVisible()
            assert view._screen_density.isVisible()
            assert view.rect().contains(view._screen_density.mapTo(view, QPoint(0, 0)))
            assert view.rect().contains(view._screen_density.mapTo(
                view, QPoint(view._screen_density.width() - 1, 0)))
            assert 0 < dense.curve_header_scroll.height() <= curve_header_viewport_height(2)
            scrollbar = dense.curve_header_scroll.verticalScrollBar()
            assert scrollbar.maximum() > 0
            scrollbar.setValue(scrollbar.maximum())
            assert scrollbar.value() == scrollbar.maximum()
            assert len(dense._curve_header_labels) == len(names)
            assert len({track.plot.y() for track in tracks}) == 1
            assert len({track.plot.height() for track in tracks}) == 1
            assert all(track.plot.geometry().bottom() < track.height() for track in tracks)
            assert view.visible_depth_range == pytest.approx((120, 170))

        compact_plot_height = dense.plot.height()
        view._screen_density.setCurrentIndex(view._screen_density.findData("full"))
        settle()
        assert dense.curve_header_scroll.height() == curve_header_viewport_height(7)
        assert dense.plot.height() < compact_plot_height
        assert not view._curve_pencil_scroll.isHidden()

        view._screen_density.setCurrentIndex(view._screen_density.findData("compact"))
        settle()
        view._compact_pencil_button.click()
        settle()
        assert view.curve_pencil_enabled
        assert not view._curve_pencil_scroll.isHidden()
        target = view.curve_pencil_target
        view.resize(900, 540)
        settle()
        assert view.curve_pencil_enabled and view.curve_pencil_target == target
        assert not view._curve_pencil_scroll.isHidden()
        assert view.set_curve_pencil_mode(False)
        settle()
        assert view._curve_pencil_scroll.isHidden()
        assert view.visible_depth_range == pytest.approx((120, 170))

        # Auto expands on a large workspace, then collapses on the laptop.
        view._screen_density.setCurrentIndex(view._screen_density.findData("auto"))
        view.resize(1800, 900)
        settle()
        assert not view._compact_screen()
        assert dense.curve_header_scroll.height() == curve_header_viewport_height(7)
        view.resize(900, 540)
        settle()
        assert view._compact_screen()

        # Print clones must not inherit the operator's screen-only density.
        clone = view.create_print_clone()
        try:
            assert not clone._compact_screen()
            printed = clone._rendered["dense"].widget
            printed.set_print_mode(True)
            assert printed.curve_header_scroll.height() == printed.print_curve_header_height
            assert len(printed._curve_header_labels) == len(names)
        finally:
            clone.close()
        assert layout.tracks == original
        for name in names:
            np.testing.assert_array_equal(dataset.curve_by_mnemonic(name).values, values[name])
    finally:
        view.close()
