from __future__ import annotations

from pathlib import Path

import numpy as np

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, new_id
from geoworkbench.project.interpretation_controller import InterpretationController
from geoworkbench.project.interpretation_feature_coordinator import (
    InterpretationFeatureCoordinator,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.tablet.controller import TabletController
from geoworkbench.tablet.models import TabletLayout, TrackKind


def _feature() -> tuple[
    ProjectSession,
    InterpretationController,
    InterpretationFeatureCoordinator,
]:
    session = ProjectSession()
    dataset = Dataset(
        dataset_id=new_id(),
        name="Interpretation test",
        kind=DatasetKind.USER,
        depth_domain=DepthDomain.MD,
        depth=np.asarray([1000.0, 1001.0, 1002.0], dtype=np.float64),
    )
    session.add_dataset(dataset, create_new_well=True)
    session.set_current_tablet_layout(TabletLayout())
    interpretation = InterpretationController(session)
    coordinator = InterpretationFeatureCoordinator(
        session,
        interpretation,
        TabletController(session),
    )
    return session, interpretation, coordinator


def test_sync_adds_interpretation_track_once() -> None:
    session, interpretation, coordinator = _feature()
    created = interpretation.add_interpretation("Primary")

    first = coordinator.sync_after_change()
    second = coordinator.sync_after_change()

    assert first.selected_interpretation_id == created.interpretation_id
    assert first.interpretation_track_created is True
    assert second.interpretation_track_created is False
    layout = session.current_tablet_layout
    assert layout is not None
    assert [track.kind for track in layout.tracks].count(TrackKind.INTERPRETATION) == 1


def test_clear_interval_selection_is_owned_by_coordinator() -> None:
    _session, interpretation, coordinator = _feature()
    current = interpretation.add_interpretation("Primary")
    interval = interpretation.add_interval(
        1000.0,
        1001.0,
        "pay",
        "Interval 1",
    )
    assert interpretation.selected_interval_id == interval.interval_id

    state = coordinator.clear_interval_selection()

    assert interpretation.selected_interval_id is None
    assert state.selected_interpretation_id == current.interpretation_id
    assert state.selected_interval_id is None


def test_sync_without_well_returns_empty_presentation_state() -> None:
    session = ProjectSession()
    interpretation = InterpretationController(session)
    coordinator = InterpretationFeatureCoordinator(
        session,
        interpretation,
        TabletController(session),
    )
    interpretation.selected_interpretation_id = "stale"
    interpretation.selected_interval_id = "stale-interval"

    state = coordinator.sync_after_change()

    assert state.interpretations == ()
    assert state.selected_interpretation_id is None
    assert state.selected_interval_id is None
    assert state.interpretation_track_created is False


def test_production_window_does_not_mutate_interpretation_selection_or_layout_directly() -> None:
    source = Path("src/geoworkbench/ui/main_window_drilling.py").read_text(encoding="utf-8")

    forbidden = (
        "self.interpretation_controller.selected_interval_id = None",
        "self.interpretation_controller.normalize_selection()",
        "self.tablet_controller.add_track(TrackKind.INTERPRETATION)",
    )
    for token in forbidden:
        assert token not in source
