"""Explicit Archie-to-tablet handoff is gated by the live source seal and UI context."""
from dataclasses import replace

import numpy as np
import pytest
from PySide6.QtWidgets import QDialog, QMessageBox

from geoworkbench.domain.models import DatasetIndex, IndexRole, IndexType, Project, Well
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.gis_archie_handoff import seal_archie_tablet_source
from geoworkbench.services.localization import AppLanguage
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.ui.gis_archie_dialog import GisArchieDialog, GisArchieProfileDialog
from geoworkbench.ui.gis_reference_dialog import GisReferenceDialog
from geoworkbench.ui.main_window import MainWindow
from test_gis_archie_operator_dialog import _fill
from test_gis_archie_source_profile import _dataset, _evaluate


def _seal(dataset, *, row=0, md_top_m=100., md_base_m=103.):
    profile = _evaluate(dataset, md_top_m=md_top_m, md_base_m=md_base_m)
    return seal_archie_tablet_source(
        dataset, profile, porosity_curve_key="phi",
        resistivity_curve_key="rt", row_index=row,
    )


@pytest.mark.parametrize("language", tuple(AppLanguage))
def test_preview_tablet_handoff_requires_visible_explicit_selection(qapp, language):
    dataset = _dataset()
    profile = _evaluate(dataset)
    pairs = tuple(
        (float(dataset.curves["phi"].values[r.sample_index]),
         float(dataset.curves["rt"].values[r.sample_index]))
        for r in profile.rows
    )
    preview = GisArchieProfileDialog(
        profile, pairs, language=language, allow_tablet_navigation=True,
    )
    blocked = GisArchieProfileDialog(profile, pairs, language=language)
    try:
        assert not preview.show_in_tablet.isEnabled()
        assert preview.tablet_row_index is None
        preview._request_tablet()
        assert preview.tablet_row_index is None
        preview.table.setCurrentIndex(preview.model.index(1, 2))
        assert preview.show_in_tablet.isEnabled()
        preview.show_in_tablet.click()
        assert preview.tablet_row_index == 1
        assert preview.result() == QDialog.DialogCode.Accepted
        blocked.table.setCurrentIndex(blocked.model.index(1, 2))
        assert blocked.show_in_tablet.isHidden()
        blocked._request_tablet()
        assert blocked.tablet_row_index is None
    finally:
        preview.close()
        blocked.close()


@pytest.mark.parametrize("change", ("none", "curve", "draft", "cancel"))
def test_nested_archie_handoff_rechecks_source_and_operator_draft(qapp, monkeypatch, change):
    dataset = _dataset()
    dialog = GisArchieDialog(dataset, allow_tablet_navigation=True)
    def inspect(preview):
        preview.table.setCurrentIndex(preview.model.index(1, 2))
        preview.show_in_tablet.click()
        if change == "curve":
            dataset.curves["rt"].values[3] = 99.
        elif change == "draft":
            dialog.fields["reviewer"].setText("Changed review")
        return QDialog.DialogCode.Rejected if change == "cancel" else QDialog.DialogCode.Accepted
    monkeypatch.setattr(GisArchieProfileDialog, "exec", inspect)
    try:
        _fill(dialog)
        dialog.evaluate.click()
        if change == "none":
            seal = dialog.tablet_request
            assert seal is not None and seal.row_index == 1
            assert seal.is_current(dataset)
            assert dialog.result() == QDialog.DialogCode.Accepted
        else:
            assert dialog.tablet_request is None
    finally:
        dialog.close()


def test_parent_reference_dialog_propagates_only_accepted_sealed_archie(qapp, monkeypatch):
    dataset = _dataset()
    seal = _seal(dataset)
    dialog = GisReferenceDialog(dataset, allow_tablet_navigation=True)
    def inspect(nested):
        nested.tablet_request = seal
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(GisArchieDialog, "exec", inspect)
    try:
        dialog.archie_button.click()
        assert dialog.result() == QDialog.DialogCode.Accepted
        assert dialog.tablet_request is seal
    finally:
        dialog.close()


def _window(qapp):
    dataset = _dataset()
    well = Well("well", "Archie well", datasets={dataset.dataset_id: dataset})
    layout = TabletLayout([
        TrackDefinition("depth", "MD", TrackKind.DEPTH, width=100),
        TrackDefinition("rt", "Rt", TrackKind.CURVE, width=240, curve_mnemonics=["RT"]),
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
    return window, session, dataset, layout


def test_main_archie_handoff_shows_transient_unclipped_sw_and_cursor(qapp):
    window, session, dataset, layout = _window(qapp)
    originals = {key: data.values.copy() for key, data in dataset.curves.items()}
    depths = dataset.active_index.values.copy()
    try:
        tracks = tuple(layout.tracks)
        seal = _seal(dataset, row=2)
        assert window._navigate_gis_archie(dataset, seal)
        panel = window.tablet_view.gis_profile_track
        assert panel is not None
        assert panel.profile is seal.profile
        assert panel.selected_row == 2
        assert panel.projection.value_bounds[1] > 1
        assert "archie-water-saturation" in window.tablet_view._gis_profile_context.text()
        assert "0.1" in window.tablet_view._gis_profile_context.text()
        assert window.tablet_view.cursor_depth == 102.
        assert tuple(layout.tracks) == tracks
        for key, values in originals.items():
            np.testing.assert_array_equal(dataset.curves[key].values, values)
        np.testing.assert_array_equal(dataset.active_index.values, depths)
        window.tablet_view._gis_profile_close.click()
        assert window.tablet_view.gis_profile_track is None
    finally:
        window.close()


@pytest.mark.parametrize("change", ("outside_interval", "axis", "dataset", "well", "layout"))
def test_transient_archie_panel_discards_stale_source_or_context(qapp, change):
    window, session, dataset, layout = _window(qapp)
    try:
        seal = _seal(dataset, md_top_m=100., md_base_m=100.)
        assert window._navigate_gis_archie(dataset, seal)
        view = window.tablet_view
        if change == "outside_interval":
            dataset.curves["rt"].values[3] = 55.
        elif change == "axis":
            dataset.add_index(DatasetIndex(
                index_id="tvd", mnemonic="TVD", index_type=IndexType.TVD,
                role=IndexRole.DEPTH, unit="m",
                values=np.array([90., 91., 92., 93.]),
            ))
            view.set_vertical_index("tvd")
        elif change == "dataset":
            session.current_dataset_id = None
        elif change == "well":
            session.current_well_id = None
        else:
            session.tablet_layouts[dataset.dataset_id] = replace(layout, tracks=list(layout.tracks))
        view._sync_gis_profile_panel()
        assert view.gis_profile_track is None
        assert not view._gis_profile_timer.isActive()
    finally:
        window.close()


def _assert_main_rejects_stale_archie_seal_without_navigating(qapp, change):
    window, session, dataset, _layout = _window(qapp)
    try:
        seal = _seal(dataset)
        if change == "source":
            dataset.curves["phi"].values[0] = 0.3
        elif change == "axis":
            dataset.add_index(DatasetIndex(
                index_id="tvd", mnemonic="TVD", index_type=IndexType.TVD,
                role=IndexRole.DEPTH, unit="m",
                values=np.array([90., 91., 92., 93.]),
            ))
            window.tablet_view.set_vertical_index("tvd")
        elif change == "dataset":
            session.current_dataset_id = None
        else:
            session.current_well_id = None
        before = (window.tablet_view.visible_depth_range, window.tablet_view.cursor_depth)
        assert not window._navigate_gis_archie(dataset, seal)
        assert (window.tablet_view.visible_depth_range, window.tablet_view.cursor_depth) == before
        assert window.tablet_view.gis_profile_track is None
    finally:
        window.close()


# Each case creates MainWindow. The Windows runner isolates test functions (#544).
def test_main_rejects_stale_archie_seal_after_source_change(qapp):
    _assert_main_rejects_stale_archie_seal_without_navigating(qapp, "source")


def test_main_rejects_stale_archie_seal_after_axis_change(qapp):
    _assert_main_rejects_stale_archie_seal_without_navigating(qapp, "axis")


def test_main_rejects_stale_archie_seal_after_dataset_change(qapp):
    _assert_main_rejects_stale_archie_seal_without_navigating(qapp, "dataset")


def test_main_rejects_stale_archie_seal_after_well_change(qapp):
    _assert_main_rejects_stale_archie_seal_without_navigating(qapp, "well")


def test_main_reference_entrypoint_rejects_well_change_inside_modal(qapp, monkeypatch):
    window, session, dataset, layout = _window(qapp)
    seal = _seal(dataset)
    messages = []
    def inspect(dialog):
        dialog.tablet_request = seal
        session.current_well_id = None
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(GisReferenceDialog, "exec", inspect)
    monkeypatch.setattr(QMessageBox, "information", lambda *args: messages.append(args[2]))
    try:
        window.show_gis_reference_dialog()
        assert messages == [window._t("petro_reference.profile_tablet_unavailable")]
        assert window.tablet_view.gis_profile_track is None
    finally:
        window.close()
