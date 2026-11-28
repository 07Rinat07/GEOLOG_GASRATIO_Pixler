"""Archie Sw QPainter projection is a separate, exact-row read-only preview.

No interpolation, synthetic thickness, saved curves or tablet layout edits.
"""
from dataclasses import replace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView

from geoworkbench.services.gis_archie_profile import ArchieInputRow, ArchieRowStatus
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.petrophysical_reference_models import PetrophysicalQuality
from geoworkbench.ui.gis_archie_dialog import GisArchieProfileDialog
from geoworkbench.ui.gis_reference_profile_track import (
    GisReferenceProfileTrack, project_profile_track,
)
from test_gis_archie_profile import _evaluate


@pytest.fixture()
def archie_profile():
    return _evaluate((
        ArchieInputRow(2, 100.0, 0.2, 10.0),
        ArchieInputRow(3, 101.0, None, 10.0),
        ArchieInputRow(4, 102.0, 0.1, 0.2),
        ArchieInputRow(5, 103.0, -1.0, 10.0),
    ))


def test_archie_track_retains_md_missing_invalid_and_outlier_without_clipping(archie_profile):
    profile = archie_profile
    projection = project_profile_track(profile)
    assert projection.value_bounds[0] == 0.0
    assert projection.value_bounds[1] > 1.0
    assert tuple(p.row_index for p in projection.points) == (0, 1, 2, 3)
    assert tuple(p.depth_fraction for p in projection.points) == (0.0, 1/3, 2/3, 1.0)
    good, missing, outlier, invalid = projection.points
    assert good.status is ArchieRowStatus.ESTIMATED
    assert good.quality is PetrophysicalQuality.VALID
    assert good.value_fraction is not None and 0 < good.value_fraction < 1
    assert missing.status is ArchieRowStatus.MISSING_INPUT and missing.value_fraction is None
    assert outlier.quality is PetrophysicalQuality.OUTSIDE_PHYSICAL_RANGE
    assert outlier.value_fraction == 1.0  # full source range, not clipped to Sw=1
    assert profile.rows[2].estimate is not None
    assert profile.rows[2].estimate.value > 1.0
    assert invalid.status is ArchieRowStatus.INVALID_INPUT
    assert invalid.value_fraction is None and invalid.quality is None
    viewport = project_profile_track(profile, visible_md_bounds=(101.5, 102.5))
    assert tuple(p.row_index for p in viewport.points) == (2,)
    assert viewport.value_bounds == projection.value_bounds
    assert viewport.points[0].depth_fraction == 0.5
    assert project_profile_track(profile, visible_md_bounds=(104.0, 106.0)).points == ()


@pytest.mark.parametrize("language", tuple(AppLanguage))
def test_archie_track_paints_and_table_selects_original_md_row(qapp, archie_profile, language):
    pairs = ((0.2, 10.0), (float("nan"), 10.0), (0.1, 0.2), (-1.0, 10.0))
    preview = GisArchieProfileDialog(archie_profile, pairs, language=language)
    try:
        preview.show()
        qapp.processEvents()
        track = preview.track
        assert isinstance(track, GisReferenceProfileTrack)
        assert track.profile is archie_profile
        assert track.accessibleName() == Localizer.create(language).text(
            "petro_reference.archie_title"
        )
        assert track.isVisible()
        assert track.projection.points[1].value_fraction is None
        assert track.projection.points[3].status is ArchieRowStatus.INVALID_INPUT
        preview.table.setCurrentIndex(preview.model.index(1, 2))
        assert track.selected_row == 1
        assert not track.grab().toImage().isNull()
        preview.table.setCurrentIndex(preview.model.index(2, 4))
        assert track.selected_row == 2
        track.set_visible_md_bounds((101.0, 102.0))
        assert tuple(p.row_index for p in track.projection.points) == (1, 2)
        assert track.selected_row == 2
        assert not track.grab().toImage().isNull()
        track.set_visible_md_bounds(None)
        assert len(track.projection.points) == 4
        assert not track.grab().toImage().isNull()
        assert preview.profile is archie_profile
    finally:
        preview.close()


def test_archie_source_values_are_readable_and_scroll_at_compact_width(qapp):
    pairs = (
        (0.12345678901234566, 1.2345678901234567e-12),
        (0.12345678901234568, 1.2345678901234569e-12),
    )
    profile = _evaluate(tuple(
        ArchieInputRow(index, 100.0 + index, phi, rt)
        for index, (phi, rt) in enumerate(pairs)
    ))
    preview = GisArchieProfileDialog(profile, pairs, language=AppLanguage.EN)
    try:
        preview.resize(480, 360)
        preview.show()
        qapp.processEvents()
        table = preview.table
        header = table.horizontalHeader()
        scrollbar = table.horizontalScrollBar()
        viewport = table.viewport().rect()
        for column, value in enumerate(pairs[0], start=2):
            index = preview.model.index(0, column)
            assert header.sectionResizeMode(column) == QHeaderView.ResizeMode.Interactive
            assert table.columnWidth(column) >= table.sizeHintForColumn(column)
            assert index.data(Qt.ItemDataRole.ToolTipRole) == str(value)

            start = header.sectionPosition(column)
            scrollbar.setValue(start)
            assert viewport.contains(table.visualRect(index).topLeft())
            scrollbar.setValue(start + table.columnWidth(column) - viewport.width())
            assert viewport.contains(table.visualRect(index).bottomRight())
    finally:
        preview.close()


def test_archie_projection_stable_under_replaced_model_coefficients(archie_profile):
    baseline = project_profile_track(archie_profile)
    changed = replace(archie_profile, coefficients=replace(
        archie_profile.coefficients, saturation_exponent=2.25,
    ))
    # Projection is based on the actual immutable computed estimates, not
    # silently recomputed from an altered coefficient label.
    assert project_profile_track(changed) == baseline
