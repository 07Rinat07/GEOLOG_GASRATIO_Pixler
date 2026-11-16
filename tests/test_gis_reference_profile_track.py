"""MD track projection and actual Qt painting retain the exact reviewed rows."""

from dataclasses import replace

import numpy as np
import pytest
from PySide6.QtCore import QModelIndex

from geoworkbench.services.gis_reference_calibration import (
    GisProfileRowStatus, evaluate_gis_reference_profile,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.petrophysical_reference_models import PetrophysicalQuality
from geoworkbench.ui.gis_reference_profile_dialog import GisReferenceProfileDialog
from geoworkbench.ui.gis_reference_profile_track import project_profile_track
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
