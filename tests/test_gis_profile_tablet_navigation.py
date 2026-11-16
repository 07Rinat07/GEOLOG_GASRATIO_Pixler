"""Verified profile navigation into the main tablet, never a derived curve."""

from dataclasses import replace

import numpy as np
import pytest
from PySide6.QtWidgets import QDialog, QMessageBox

from geoworkbench.domain.models import (
    DatasetIndex, IndexRole, IndexType, Project, Well,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.gis_reference_calibration import evaluate_gis_reference_profile
from geoworkbench.services.localization import AppLanguage
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.ui.gis_reference_dialog import GisReferenceDialog
from geoworkbench.ui.gis_reference_profile_dialog import GisProfileTabletRequest, GisReferenceProfileDialog
from geoworkbench.ui.main_window import MainWindow
from test_gis_reference_calibration import _calibration, _dataset
from test_gis_reference_dialog import _fill


def _profile(dataset):
    curve_key = next(iter(dataset.curves))
    return evaluate_gis_reference_profile(
        dataset, _calibration(dataset, curve_key=curve_key), md_top_m=100, md_base_m=102,
    )


@pytest.mark.parametrize("language", tuple(AppLanguage))
def test_tablet_request_requires_explicit_row_and_enabled_context(qapp, language):
    dataset = _dataset()
    profile = _profile(dataset)
    preview = GisReferenceProfileDialog(profile, language=language, allow_tablet_navigation=True)
    disabled = GisReferenceProfileDialog(profile, language=language)
    try:
        assert not preview.open_tablet.isEnabled()
        preview.table.setCurrentIndex(preview.model.index(1, 2))
        assert preview.open_tablet.isEnabled()
        preview.open_tablet.click()
        assert preview.result() == QDialog.DialogCode.Accepted
        assert preview.tablet_request == GisProfileTabletRequest(profile, 1)
        disabled.table.setCurrentIndex(disabled.model.index(1, 2))
        assert disabled.open_tablet.isHidden() and not disabled.open_tablet.isEnabled()
        disabled._request_tablet()
        assert disabled.tablet_request is None
    finally:
        preview.close()
        disabled.close()


@pytest.mark.parametrize("change", ("none", "curve", "draft", "cancel"))
def test_reference_only_hands_off_current_explicit_accepted_profile(qapp, monkeypatch, change):
    dataset = _dataset()
    dialog = GisReferenceDialog(dataset, allow_tablet_navigation=True)
    try:
        _fill(dialog)
        def inspect(preview):
            preview.table.setCurrentIndex(preview.model.index(1, 1))
            preview.open_tablet.click()
            if change == "curve":
                dataset.curves["selected"].values[0] += 1.0
            elif change == "draft":
                dialog.fields["reviewer"].setText("Changed")
            return QDialog.DialogCode.Rejected if change == "cancel" else QDialog.DialogCode.Accepted
        monkeypatch.setattr(GisReferenceProfileDialog, "exec", inspect)
        dialog.calculate_profile.click()
        if change == "none":
            assert dialog.result() == QDialog.DialogCode.Accepted
            assert dialog.tablet_request is not None
            assert dialog.tablet_request.row_index == 1
        else:
            assert dialog.tablet_request is None
    finally:
        dialog.close()


def _window(qapp):
    dataset = _dataset()
    # The service fixture deliberately uses an alias to test source identity.
    # Real LAS imports and project curves are keyed by their metadata curve ID.
    # Exercise the full main-window path with that actual storage contract.
    curve = dataset.curves.pop("selected")
    dataset.curves[curve.metadata.curve_id] = curve
    well = Well("well", "GIS well", datasets={dataset.dataset_id: dataset})
    layout = TabletLayout([
        TrackDefinition("depth", "MD", TrackKind.DEPTH, width=100),
        TrackDefinition("gr", "GR", TrackKind.CURVE, width=240, curve_mnemonics=["GR"]),
    ], visible_depth_top=100, visible_depth_bottom=101)
    session = ProjectSession(
        project=Project("project", "GIS", wells={well.well_id: well}),
        current_well_id=well.well_id, current_dataset_id=dataset.dataset_id,
        tablet_layouts={dataset.dataset_id: layout},
    )
    window = MainWindow()
    window.project_controller.session = session
    window._bind_project_session()
    window._show_current_dataset()
    qapp.processEvents()
    return window, session, dataset


def test_main_tablet_navigates_exact_missing_row_without_source_edits(qapp, monkeypatch):
    window, session, dataset = _window(qapp)
    values, depths = dataset.curves["curve-1"].values.copy(), dataset.active_index.values.copy()
    try:
        profile = _profile(dataset)
        layout = session.current_tablet_layout
        tracks = tuple(layout.tracks)
        assert window.curve_view.selection.curve_ids == ("curve-1",)
        assert window.tablet_view.visible_depth_range == pytest.approx((100, 101))
        def inspect(dialog):
            dialog.tablet_request = GisProfileTabletRequest(profile, 1)
            return QDialog.DialogCode.Accepted
        monkeypatch.setattr(GisReferenceDialog, "exec", inspect)
        window.show_gis_reference_dialog()
        assert window.tablet_view.visible_depth_range == pytest.approx((100, 102))
        assert window.tablet_view.cursor_depth == 101
        assert (layout.visible_depth_top, layout.visible_depth_bottom) == pytest.approx((100, 102))
        assert session.dirty
        assert window.cursor_line_action.isChecked()
        assert tuple(layout.tracks) == tracks and set(dataset.curves) == {"curve-1"}
        np.testing.assert_array_equal(dataset.curves["curve-1"].values, values)
        np.testing.assert_array_equal(dataset.active_index.values, depths)
    finally:
        window.close()


@pytest.mark.parametrize("change", ("curve", "axis", "row", "dataset", "well"))
def test_main_rejects_stale_or_foreign_handoff_before_viewport_change(qapp, monkeypatch, change):
    window, session, dataset = _window(qapp)
    try:
        profile = _profile(dataset)
        request = GisProfileTabletRequest(profile, 1)
        if change == "curve":
            dataset.curves["curve-1"].values[0] += 1
        elif change == "axis":
            axis = DatasetIndex(
                index_id="tvd", mnemonic="TVD", index_type=IndexType.TVD, role=IndexRole.DEPTH,
                unit="m", values=np.array([90.0, 91.0, 92.0]),
            )
            dataset.add_index(axis)
            window.tablet_view.set_vertical_index("tvd")
        elif change == "row":
            request = replace(request, row_index=99)
        before = (window.tablet_view.visible_depth_range, window.tablet_view.cursor_depth)
        if change in {"dataset", "well"}:
            messages = []
            def inspect(dialog):
                dialog.tablet_request = request
                if change == "dataset":
                    session.current_dataset_id = None
                else:
                    session.current_well_id = None
                return QDialog.DialogCode.Accepted
            monkeypatch.setattr(GisReferenceDialog, "exec", inspect)
            monkeypatch.setattr(QMessageBox, "information", lambda *args: messages.append(args[2]))
            window.show_gis_reference_dialog()
            assert messages == [window._t("petro_reference.profile_tablet_unavailable")]
        else:
            assert not window._navigate_gis_profile(dataset, request)
        assert (window.tablet_view.visible_depth_range, window.tablet_view.cursor_depth) == before
        assert set(dataset.curves) == {"curve-1"}
    finally:
        window.close()


def test_singleton_navigation_keeps_scale_and_moves_to_actual_row(qapp):
    window, session, dataset = _window(qapp)
    try:
        profile = evaluate_gis_reference_profile(
            dataset, _calibration(dataset, curve_key="curve-1"), md_top_m=102, md_base_m=102,
        )
        assert profile.sample_count == 1 and profile.rows[0].sample_index == 2
        assert window._navigate_gis_profile(dataset, GisProfileTabletRequest(profile, 0))
        assert window.tablet_view.visible_depth_range == pytest.approx((101, 102))
        assert window.tablet_view.cursor_depth == 102
        assert session.current_tablet_layout.visible_depth_bottom == 102
    finally:
        window.close()



@pytest.mark.parametrize("language", tuple(AppLanguage))
def test_explicit_panel_request_is_distinct_from_navigation(qapp, language):
    dataset = _dataset()
    profile = _profile(dataset)
    dialog = GisReferenceProfileDialog(profile, language=language, allow_tablet_navigation=True)
    try:
        assert not dialog.show_in_tablet.isEnabled()
        dialog.table.setCurrentIndex(dialog.model.index(1, 2))
        assert dialog.show_in_tablet.isEnabled()
        dialog.show_in_tablet.click()
        assert dialog.tablet_request == GisProfileTabletRequest(profile, 1, True)
    finally:
        dialog.close()


def test_panel_syncs_md_and_cursor_without_persistent_tracks(qapp, monkeypatch):
    window, session, dataset = _window(qapp)
    values, depths = dataset.curves["curve-1"].values.copy(), dataset.active_index.values.copy()
    try:
        layout = session.current_tablet_layout
        tracks = tuple(layout.tracks)
        profile = _profile(dataset)
        view = window.tablet_view
        def inspect(dialog):
            dialog.tablet_request = GisProfileTabletRequest(profile, 1, True)
            return QDialog.DialogCode.Accepted
        monkeypatch.setattr(GisReferenceDialog, "exec", inspect)
        window.show_gis_reference_dialog()
        panel = view.gis_profile_track
        assert panel is not None and panel.profile is profile
        assert panel.selected_row == 1
        assert panel.projection.points[1].value_fraction is None
        view.set_visible_depth(101, 102)
        assert tuple(point.row_index for point in panel.projection.points) == (1, 2)
        view.set_cursor_depth(102)
        assert panel.selected_row == 2
        view.set_cursor_enabled(False)
        assert panel.selected_row is None
        assert not panel.grab().toImage().isNull()
        assert tuple(layout.tracks) == tracks and set(dataset.curves) == {"curve-1"}
        np.testing.assert_array_equal(dataset.curves["curve-1"].values, values)
        np.testing.assert_array_equal(dataset.active_index.values, depths)
        view._gis_profile_close.click()
        assert view.gis_profile_track is None
        assert not view._gis_profile_timer.isActive()
    finally:
        window.close()


@pytest.mark.parametrize("change", ("source", "axis", "well", "rebuild"))
def test_panel_discards_stale_context(qapp, change):
    window, session, dataset = _window(qapp)
    try:
        view = window.tablet_view
        assert window._navigate_gis_profile(dataset, GisProfileTabletRequest(_profile(dataset), 1, True))
        assert view.gis_profile_track is not None
        if change == "source":
            dataset.curves["curve-1"].values[0] += 1
            view._sync_gis_profile_panel()
        elif change == "axis":
            dataset.add_index(DatasetIndex(
                index_id="tvd", mnemonic="TVD", index_type=IndexType.TVD, role=IndexRole.DEPTH,
                unit="m", values=np.array([90., 91., 92.]),
            ))
            view.set_vertical_index("tvd")
        elif change == "well":
            session.current_well_id = None
            view._sync_gis_profile_panel()
        else:
            view.refresh_view()
        assert view.gis_profile_track is None
        assert not view._gis_profile_timer.isActive()
    finally:
        window.close()
