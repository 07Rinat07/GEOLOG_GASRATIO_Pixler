"""MD track projection and actual Qt painting retain the exact reviewed rows."""

from dataclasses import replace
from math import inf, nextafter

import numpy as np
import pytest
from PySide6.QtCore import QModelIndex, QRectF
from PySide6.QtGui import QFont, QFontMetrics, QPainter

from geoworkbench.services.gis_reference_calibration import (
    GisProfileRowStatus, evaluate_gis_reference_profile,
)
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.petrophysical_reference_models import PetrophysicalQuality
from geoworkbench.ui import gis_reference_profile_track
from geoworkbench.ui.gis_reference_profile_dialog import GisReferenceProfileDialog
from geoworkbench.ui.gis_reference_profile_track import GisReferenceProfileTrack, project_profile_track
from test_gis_reference_calibration import _calibration, _dataset


@pytest.mark.parametrize("density", (False, True))
@pytest.mark.parametrize("descending", (False, True))
def test_projection_keeps_all_rows_and_depth_increases_down(density, descending):
    dataset = _dataset(density)
    if descending:
        dataset.active_index.values[:] = [102, 101, 100]
    values = dataset.curves["selected"].values.copy()
    profile = evaluate_gis_reference_profile(
        dataset, _calibration(dataset, density), md_top_m=100, md_base_m=102,
    )
    track = project_profile_track(profile)
    assert tuple(p.row_index for p in track.points) == (0, 1, 2)
    assert tuple(p.depth_fraction for p in track.points) == (
        (1.0, 0.5, 0.0) if descending else (0.0, 0.5, 1.0)
    )
    good, missing, outlier = track.points
    assert good.quality is PetrophysicalQuality.VALID
    assert missing.status is GisProfileRowStatus.MISSING_SOURCE
    assert missing.value_fraction is None and missing.quality is None
    assert outlier.quality is (
        PetrophysicalQuality.OUTSIDE_PHYSICAL_RANGE if density
        else PetrophysicalQuality.OUTSIDE_REFERENCE_RANGE
    )
    assert outlier.value_fraction == (0.0 if density else 1.0)
    estimate = profile.rows[2].estimate
    assert estimate is not None
    assert track.value_bounds == (min(0.0, estimate.value), max(1.0, estimate.value))
    np.testing.assert_array_equal(dataset.curves["selected"].values, values)


def test_invalid_zero_missing_and_empty_intervals_remain_distinct():
    dataset = _dataset(True)
    dataset.curves["selected"].values[:] = [0.0, np.nan, 2.71]
    calibration = _calibration(dataset, True)
    profile = evaluate_gis_reference_profile(dataset, calibration, md_top_m=100, md_base_m=102)
    invalid, missing, zero = project_profile_track(profile).points
    assert invalid.status is GisProfileRowStatus.INVALID_MEASUREMENT and invalid.value_fraction is None
    assert missing.status is GisProfileRowStatus.MISSING_SOURCE and missing.value_fraction is None
    assert zero.status is GisProfileRowStatus.ESTIMATED and zero.value_fraction == 0.0
    empty = evaluate_gis_reference_profile(dataset, calibration, md_top_m=100.1, md_base_m=100.9)
    assert project_profile_track(empty).points == ()
    single = evaluate_gis_reference_profile(dataset, calibration, md_top_m=102, md_base_m=102)
    assert project_profile_track(single).points[0].depth_fraction == 0.5


def test_finite_extreme_outlier_scale_does_not_overflow():
    dataset = _dataset()
    profile = evaluate_gis_reference_profile(
        dataset, _calibration(dataset), md_top_m=100, md_base_m=102,
    )
    first, missing, last = profile.rows
    assert first.estimate is not None and last.estimate is not None
    first = replace(first, estimate=replace(first.estimate, value=-1.7e308))
    last = replace(last, estimate=replace(last.estimate, value=1.7e308))
    projection = project_profile_track(replace(profile, rows=(first, missing, last)))
    assert projection.points[0].value_fraction == 0.0
    assert projection.points[2].value_fraction == 1.0


@pytest.mark.parametrize("language", tuple(AppLanguage))
def test_real_track_renders_and_table_selection_identifies_exact_row(qapp, language):
    dataset = _dataset()
    profile = evaluate_gis_reference_profile(
        dataset, _calibration(dataset), md_top_m=100, md_base_m=102,
    )
    dialog = GisReferenceProfileDialog(profile, language=language)
    try:
        dialog.resize(1050, 650)
        dialog.show()
        qapp.processEvents()
        track = dialog.track
        assert track.isVisible() and track.width() >= 220
        dialog.table.setCurrentIndex(dialog.model.index(1, 2))
        assert track.selected_row == 1
        assert track.projection.points[1].value_fraction is None
        image = track.grab().toImage()
        assert not image.isNull() and image.width() >= track.width()
        dialog.table.setCurrentIndex(dialog.model.index(2, 0))
        assert track.selected_row == 2
        dialog.table.setCurrentIndex(QModelIndex())
        assert track.selected_row is None
        assert dialog.profile is profile
    finally:
        dialog.close()



@pytest.mark.parametrize("density", (False, True))
@pytest.mark.parametrize("descending", (False, True))
def test_viewport_retains_actual_row_identity_and_full_profile_value_scale(density, descending):
    dataset = _dataset(density)
    if descending:
        dataset.active_index.values[:] = [102, 101, 100]
    values = dataset.curves["selected"].values.copy()
    depths = dataset.active_index.values.copy()
    profile = evaluate_gis_reference_profile(
        dataset, _calibration(dataset, density), md_top_m=100, md_base_m=102,
    )
    whole = project_profile_track(profile)
    visible = project_profile_track(profile, visible_md_bounds=(100.5, 102.5))
    expected_rows = (0, 1) if descending else (1, 2)
    assert tuple(point.row_index for point in visible.points) == expected_rows
    for point in visible.points:
        original = whole.points[point.row_index]
        assert point.depth_fraction == pytest.approx(
            (profile.rows[point.row_index].md_m - 100.5) / 2,
        )
        assert point.value_fraction == original.value_fraction
        assert point.status is original.status and point.quality is original.quality
    assert visible.value_bounds == whole.value_bounds
    missing = next(point for point in visible.points if point.row_index == 1)
    assert missing.status is GisProfileRowStatus.MISSING_SOURCE
    assert missing.value_fraction is None
    assert project_profile_track(profile, visible_md_bounds=(90, 99)).points == ()
    assert project_profile_track(profile, visible_md_bounds=(100.1, 100.9)).points == ()
    np.testing.assert_array_equal(dataset.curves["selected"].values, values)
    np.testing.assert_array_equal(dataset.active_index.values, depths)


@pytest.mark.parametrize("bounds", ((101, 100), (100, 100), (float("nan"), 102),
                                    (100, float("inf"))))
def test_invalid_viewport_refused(bounds):
    dataset = _dataset()
    profile = evaluate_gis_reference_profile(
        dataset, _calibration(dataset), md_top_m=100, md_base_m=102,
    )
    with pytest.raises(ValueError, match="viewport"):
        project_profile_track(profile, visible_md_bounds=bounds)


def test_singleton_uses_viewport_coordinate_not_profile_midpoint():
    dataset = _dataset()
    profile = evaluate_gis_reference_profile(
        dataset, _calibration(dataset), md_top_m=102, md_base_m=102,
    )
    assert project_profile_track(profile).points[0].depth_fraction == 0.5
    point = project_profile_track(profile, visible_md_bounds=(100, 104)).points[0]
    assert point.depth_fraction == 0.5
    point = project_profile_track(profile, visible_md_bounds=(101, 102)).points[0]
    assert point.depth_fraction == 1.0
    assert point.row_index == 0


def test_real_track_viewport_keeps_offscreen_selection_and_restores_full_profile(qapp):
    dataset = _dataset()
    profile = evaluate_gis_reference_profile(
        dataset, _calibration(dataset), md_top_m=100, md_base_m=102,
    )
    dialog = GisReferenceProfileDialog(profile)
    try:
        dialog.show()
        qapp.processEvents()
        track = dialog.track
        track.select_row(2)
        track.set_visible_md_bounds((99, 101))
        assert track.selected_row == 2
        assert tuple(point.row_index for point in track.projection.points) == (0, 1)
        assert not track.grab().toImage().isNull()
        track.set_visible_md_bounds((101, 103))
        assert track.selected_row == 2
        assert tuple(point.row_index for point in track.projection.points) == (1, 2)
        assert not track.grab().toImage().isNull()
        with pytest.raises(ValueError):
            track.set_visible_md_bounds((103, 101))
        assert tuple(point.row_index for point in track.projection.points) == (1, 2)
        track.set_visible_md_bounds(None)
        assert track.selected_row == 2
        assert len(track.projection.points) == 3
        assert not track.grab().toImage().isNull()
    finally:
        dialog.close()


def test_real_track_paints_exact_md_bounds_before_and_after_zoom(qapp, monkeypatch):
    dataset = _dataset()
    top = 1500.0000002
    middle = nextafter(top, inf)
    base = nextafter(middle, inf)
    dataset.active_index.values[:] = [base, middle, top]
    calibration = _calibration(dataset, md_top_m=top, md_base_m=base)
    profile = evaluate_gis_reference_profile(
        dataset, calibration, md_top_m=top, md_base_m=base,
    )
    labels = []

    class RecordingPainter(QPainter):
        def drawText(self, *args):
            text = args[-1]
            if isinstance(text, str) and text.startswith("1500"):
                labels.append(float(text))
            return super().drawText(*args)

    monkeypatch.setattr(gis_reference_profile_track, "QPainter", RecordingPainter)
    dialog = GisReferenceProfileDialog(profile)
    try:
        track = dialog.track
        dialog.table.setCurrentIndex(dialog.model.index(0, 1))
        for viewport, expected in (
            (None, (top, base)), ((top, middle), (top, middle)), (None, (top, base)),
        ):
            track.set_visible_md_bounds(viewport)
            labels.clear()
            assert not track.grab().isNull()
            assert tuple(labels) == expected
            assert track.selected_row == 0
        assert tuple(point.row_index for point in track.projection.points) == (0, 1, 2)

        singleton = evaluate_gis_reference_profile(
            dataset, calibration, md_top_m=middle, md_base_m=middle,
        )
        single_track = GisReferenceProfileTrack(singleton, dialog.localizer)
        try:
            labels.clear()
            assert not single_track.grab().isNull()
            assert labels == [middle]
        finally:
            single_track.close()
    finally:
        dialog.close()


def test_real_track_fits_md_labels_at_minimum_size(qapp, monkeypatch):
    dataset = _dataset()
    top, base = 1500.0000002000002, 1500.0000002000004
    dataset.active_index.values[:] = [base, top, 1500.0]
    profile = evaluate_gis_reference_profile(
        dataset, _calibration(dataset, md_top_m=top, md_base_m=base),
        md_top_m=top, md_base_m=base,
    )
    depth_labels = []
    plots = []

    class GeometryPainter(QPainter):
        def drawText(self, point, text):
            if text.startswith("1500"):
                glyphs = self.fontMetrics().tightBoundingRect(text)
                bounds = QRectF(glyphs).translated(point)
                depth_labels.append((float(text), self.worldTransform().mapRect(bounds)))
            return super().drawText(point, text)

        def drawRect(self, rect):
            plots.append(self.worldTransform().mapRect(rect))
            return super().drawRect(rect)

    monkeypatch.setattr(gis_reference_profile_track, "QPainter", GeometryPainter)
    track = GisReferenceProfileTrack(profile, Localizer.create(AppLanguage.RU))
    try:
        font = track.font()
        font.setPixelSize(20)
        font.setStretch(QFont.Stretch.UltraExpanded)
        track.setFont(font)
        track.resize(track.minimumSize())
        assert QFontMetrics(font).horizontalAdvance(str(base)) > track.width()
        assert not track.grab().isNull()
        assert track.size() == track.minimumSize()
        available = QRectF(track.rect())
        (painted_top, top_text), (painted_base, base_text) = depth_labels
        assert (painted_top, painted_base) == (top, base)
        assert available.contains(top_text) and available.contains(base_text)
        plot, = plots
        assert available.contains(plot) and plot.width() > available.width() / 2
        assert top_text.bottom() <= plot.top() < plot.bottom() <= base_text.top()
    finally:
        track.close()
