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
from geoworkbench.tablet.controller import TabletController
from geoworkbench.tablet.models import TrackKind


def make_session() -> ProjectSession:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([1.0, 2.0]),
    )
    for mnemonic in ("C1", "C2", "ROP"):
        curve_id = f"curve-{mnemonic}"
        dataset.curves[curve_id] = CurveData(
            CurveMetadata(
                curve_id,
                mnemonic,
                mnemonic,
                None,
                None,
                dataset.dataset_id,
            ),
            np.array([1.0, 2.0]),
        )
    well = Well("well-1", "Well", datasets={dataset.dataset_id: dataset})
    return ProjectSession(
        project=Project("project-1", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=dataset.dataset_id,
    )


def test_build_default_layout_registers_it_in_session() -> None:
    session = make_session()
    controller = TabletController(session)

    layout = controller.build_default_layout()

    assert session.current_tablet_layout is layout
    assert [track.kind for track in layout.tracks] == [
        TrackKind.DEPTH,
        TrackKind.GAS,
        TrackKind.CURVE,
    ]
    assert layout.tracks[1].curve_mnemonics == ["C1", "C2"]
    assert session.dirty is True


def test_track_commands_update_layout_and_dirty_state() -> None:
    session = make_session()
    controller = TabletController(session)
    layout = controller.build_default_layout()
    session.dirty = False

    track = controller.add_track(TrackKind.CURVE, ["C1", "ROP"])
    controller.set_track_width(track.track_id, 440)
    assert controller.move_track(track.track_id, -1) is True
    controller.hide_track(track.track_id)

    assert layout.track_by_id(track.track_id).width == 440
    assert layout.track_by_id(track.track_id).visible is False
    assert controller.show_all_tracks() == 1
    assert controller.remove_track(track.track_id) is track
    assert session.dirty is True


def test_move_at_layout_boundary_does_not_mark_session_dirty() -> None:
    session = make_session()
    controller = TabletController(session)
    layout = controller.build_default_layout()
    session.dirty = False

    assert controller.move_track(layout.tracks[0].track_id, -1) is False
    assert session.dirty is False


def test_add_curve_track_rejects_unknown_mnemonic() -> None:
    session = make_session()
    controller = TabletController(session)
    controller.build_default_layout()

    with pytest.raises(ValueError, match="UNKNOWN"):
        controller.add_track(TrackKind.CURVE, ["UNKNOWN"])


def test_commands_require_selected_dataset() -> None:
    controller = TabletController(ProjectSession())

    with pytest.raises(RuntimeError, match="набор данных"):
        controller.build_default_layout()
