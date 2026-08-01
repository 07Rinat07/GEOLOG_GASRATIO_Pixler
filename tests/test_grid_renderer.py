from __future__ import annotations

import pyqtgraph as pg
import pytest

from geoworkbench.tablet.grid_renderer import (
    GridSettings,
    TabletGridOverlay,
    adaptive_aligned_step,
    aligned_grid_values,
    engineering_tick_levels,
    normalized_grid_lines,
)
from geoworkbench.tablet.models import TrackDefinition, TrackKind


def test_engineering_levels_keep_major_and_intermediate_spacing_stable() -> None:
    assert engineering_tick_levels(1000.0, 1100.0, 4, 10) == (
        (25.0, 1000.0),
        (2.5, 1000.0),
    )
    assert engineering_tick_levels(10.0, 0.0, 5, 1) == ((2.0, 0.0),)


def test_normalized_grid_lines_are_shared_major_minor_positions() -> None:
    lines = normalized_grid_lines(2, 2)

    assert [(line.fraction, line.major) for line in lines] == [
        (0.0, True),
        (0.25, False),
        (0.5, True),
        (0.75, False),
        (1.0, True),
    ]


def test_depth_grid_uses_round_five_metre_values() -> None:
    step = adaptive_aligned_step(47.0, 97.0, 5.0)

    assert step == 5.0
    assert aligned_grid_values(47.0, 97.0, step) == (
        50.0,
        55.0,
        60.0,
        65.0,
        70.0,
        75.0,
        80.0,
        85.0,
        90.0,
        95.0,
    )


def test_depth_grid_coarsens_only_for_a_long_overview() -> None:
    assert adaptive_aligned_step(0.0, 2_000.0, 5.0) == 100.0


def test_screen_settings_preserve_saved_track_configuration() -> None:
    track = TrackDefinition(
        "gas",
        "Gas",
        TrackKind.GAS,
        grid_x=False,
        grid_y=True,
        grid_major_divisions=4,
        grid_minor_divisions=10,
        grid_alpha=0.35,
        grid_print=False,
    )

    assert GridSettings.from_track(track) == GridSettings(False, True, 4, 10, 0.35)


def test_print_suppression_hides_and_restores_one_track_grid(qapp) -> None:
    plot = pg.PlotWidget()
    plot.resize(400, 300)
    plot.show()
    qapp.processEvents()
    overlay = TabletGridOverlay(plot)
    overlay.apply(GridSettings(True, True, 5, 5, 0.3))

    overlay.set_print_suppressed(True)
    assert all(not line.isVisible() for line, _major in overlay._vertical)
    assert all(not line.isVisible() for line, _major in overlay._horizontal)

    overlay.set_print_suppressed(False)
    assert any(line.isVisible() for line, major in overlay._vertical if major)
    assert any(line.isVisible() for line, major in overlay._horizontal if major)
    plot.close()


def test_depth_overlay_aligns_horizontal_lines_to_five_metre_values(qapp) -> None:
    plot = pg.PlotWidget()
    plot.resize(400, 300)
    plot.show()
    qapp.processEvents()
    overlay = TabletGridOverlay(plot)
    overlay.apply(GridSettings(True, True, 5, 5, 0.3))
    overlay.set_horizontal_base_step(5.0)
    plot.setYRange(47.0, 97.0, padding=0.0)
    qapp.processEvents()

    major_positions = [float(line.value()) for line, major in overlay._horizontal if major]
    minor_positions = [float(line.value()) for line, major in overlay._horizontal if not major]
    assert major_positions == [
        50.0,
        55.0,
        60.0,
        65.0,
        70.0,
        75.0,
        80.0,
        85.0,
        90.0,
        95.0,
    ]
    assert minor_positions[:3] == [47.0, 48.0, 49.0]
    assert minor_positions[-2:] == [96.0, 97.0]
    plot.close()


def test_depth_minor_lines_do_not_follow_x_axis_subdivision_setting(qapp) -> None:
    plot = pg.PlotWidget()
    plot.resize(400, 300)
    plot.show()
    qapp.processEvents()
    overlay = TabletGridOverlay(plot)
    overlay.set_horizontal_base_step(5.0)
    plot.setYRange(50.0, 60.0, padding=0.0)

    overlay.apply(GridSettings(True, True, 5, 2, 0.3))
    qapp.processEvents()
    first = tuple((float(line.value()), major) for line, major in overlay._horizontal)

    overlay.apply(GridSettings(True, True, 5, 10, 0.3))
    qapp.processEvents()
    second = tuple((float(line.value()), major) for line, major in overlay._horizontal)

    assert first == second
    assert [value for value, major in second if major] == [50.0, 55.0, 60.0]
    assert len(second) == 11
    plot.close()


def test_print_mode_keeps_minor_lines_and_uses_configured_alpha(qapp) -> None:
    plot = pg.PlotWidget()
    plot.resize(100, 80)
    plot.show()
    qapp.processEvents()
    overlay = TabletGridOverlay(plot)
    overlay.apply(GridSettings(True, True, 10, 10, 0.8))
    overlay.set_horizontal_base_step(5.0)
    plot.setYRange(47.0, 97.0, padding=0.0)
    qapp.processEvents()

    assert not any(line.isVisible() for line, major in overlay._vertical if not major)
    assert not any(line.isVisible() for line, major in overlay._horizontal if not major)

    overlay.set_print_mode(True)

    assert overlay.print_mode is True
    assert all(line.isVisible() for line, _major in overlay._vertical)
    assert all(line.isVisible() for line, _major in overlay._horizontal)
    major_pen = next(line.pen for line, major in overlay._vertical if major)
    minor_pen = next(line.pen for line, major in overlay._vertical if not major)
    assert major_pen.color().alphaF() == pytest.approx(0.8, abs=0.005)
    assert minor_pen.color().alphaF() == pytest.approx(0.8 * 0.45, abs=0.005)

    overlay.set_print_mode(False)
    assert overlay.print_mode is False
    screen_major_pen = next(line.pen for line, major in overlay._vertical if major)
    assert screen_major_pen.color().alphaF() == pytest.approx(0.8 * 0.72, abs=0.005)
    plot.close()


def test_default_print_grid_has_a_legible_alpha_and_line_width_floor(qapp) -> None:
    plot = pg.PlotWidget()
    plot.resize(400, 300)
    plot.show()
    qapp.processEvents()
    overlay = TabletGridOverlay(plot)
    overlay.apply(GridSettings(True, True, 5, 5, 0.2))

    overlay.set_print_mode(True)

    major_pen = next(line.pen for line, major in overlay._vertical if major)
    minor_pen = next(line.pen for line, major in overlay._vertical if not major)
    assert major_pen.color().alphaF() == pytest.approx(0.62, abs=0.005)
    assert minor_pen.color().alphaF() == pytest.approx(0.32, abs=0.005)
    assert major_pen.widthF() == pytest.approx(1.0)
    assert minor_pen.widthF() == pytest.approx(0.55)
    plot.close()


def test_zero_alpha_hides_grid_in_screen_and_print_modes(qapp) -> None:
    plot = pg.PlotWidget()
    plot.resize(400, 300)
    plot.show()
    qapp.processEvents()
    overlay = TabletGridOverlay(plot)
    overlay.apply(GridSettings(True, True, 5, 5, 0.0))

    assert all(not line.isVisible() for line, _major in overlay._vertical)
    assert all(not line.isVisible() for line, _major in overlay._horizontal)

    overlay.set_print_mode(True)
    assert all(not line.isVisible() for line, _major in overlay._vertical)
    assert all(not line.isVisible() for line, _major in overlay._horizontal)
    plot.close()
