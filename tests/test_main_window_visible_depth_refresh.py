from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
    Project,
    Well,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.ui.main_window import MainWindow


def _session_with_depth_window() -> ProjectSession:
    depth = np.linspace(0.0, 100.0, 101)
    dataset = Dataset(
        "dataset-depth-window",
        "Depth window",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    dataset.curves["curve-rop"] = CurveData(
        CurveMetadata(
            "curve-rop",
            "ROP",
            "ROP",
            "m/h",
            None,
            dataset.dataset_id,
        ),
        np.linspace(10.0, 20.0, depth.size),
    )
    well = Well(
        "well-depth-window",
        "Well",
        datasets={dataset.dataset_id: dataset},
    )
    layout = TabletLayout(
        [
            TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120),
            TrackDefinition(
                "rop",
                "ROP",
                TrackKind.CURVE,
                width=240,
                curve_mnemonics=["ROP"],
            ),
        ],
        visible_depth_top=10.0,
        visible_depth_bottom=90.0,
    )
    return ProjectSession(
        project=Project(
            "project-depth-window",
            "Project",
            wells={well.well_id: well},
        ),
        current_well_id=well.well_id,
        current_dataset_id=dataset.dataset_id,
        tablet_layouts={dataset.dataset_id: layout},
    )


def _window_with_session(qapp) -> tuple[MainWindow, ProjectSession]:
    session = _session_with_depth_window()
    window = MainWindow()
    window.project_controller.session = session
    window._bind_project_session()
    window._show_current_dataset()
    qapp.processEvents()
    return window, session


def test_manual_visible_depth_change_uses_incremental_viewport_refresh(
    qapp,
    monkeypatch,
) -> None:
    window, session = _window_with_session(qapp)
    answers = iter(((20.0, True), (80.0, True)))
    tree_refreshes = 0

    monkeypatch.setattr(
        "geoworkbench.ui.main_window.QInputDialog.getDouble",
        lambda *args, **kwargs: next(answers),
    )

    def count_tree_refresh() -> None:
        nonlocal tree_refreshes
        tree_refreshes += 1

    monkeypatch.setattr(window, "_refresh_tree", count_tree_refresh)
    before = window.tablet_view.dirty_render_stats()

    try:
        window.change_visible_depth_range()
        qapp.processEvents()

        after = window.tablet_view.dirty_render_stats()
        assert after.full_updates == before.full_updates
        assert after.partial_updates == before.partial_updates
        assert window.tablet_view.visible_depth_range == pytest.approx((20.0, 80.0))
        layout = session.current_tablet_layout
        assert layout is not None
        assert (layout.visible_depth_top, layout.visible_depth_bottom) == pytest.approx(
            (20.0, 80.0)
        )
        assert tree_refreshes == 0
        assert session.dirty
    finally:
        window.close()


def test_reset_visible_depth_performs_one_full_rebuild_without_tree_refresh(
    qapp,
    monkeypatch,
) -> None:
    window, session = _window_with_session(qapp)
    tree_refreshes = 0

    def count_tree_refresh() -> None:
        nonlocal tree_refreshes
        tree_refreshes += 1

    monkeypatch.setattr(window, "_refresh_tree", count_tree_refresh)
    before = window.tablet_view.dirty_render_stats()

    try:
        window.reset_visible_depth_range()
        qapp.processEvents()

        after = window.tablet_view.dirty_render_stats()
        assert after.full_updates == before.full_updates + 1
        assert tree_refreshes == 0
        assert session.dirty
    finally:
        window.close()
