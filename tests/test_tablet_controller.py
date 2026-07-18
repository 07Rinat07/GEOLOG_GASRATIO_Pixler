import numpy as np
import pytest

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    CuttingsSample,
    Dataset,
    DatasetKind,
    DepthDomain,
    LithologyInterval,
    Project,
    StratigraphyInterval,
    Well,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.tablet.controller import TabletController
from geoworkbench.tablet.models import CurveLineStyle, CurveStyle, TrackKind, XScale


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
    assert layout.tracks[1].x_scale is XScale.LOGARITHMIC
    assert session.dirty is True


def test_default_layout_groups_tgas_with_gas_curves() -> None:
    session = make_session()
    dataset = session.current_dataset
    assert dataset is not None
    dataset.upsert_curve("TGAS", np.array([3.0, 4.0]), unit="%")
    dataset.upsert_curve("LITH_CODE", np.array([39.0, 60.0]))

    layout = TabletController(session).build_default_layout()

    gas = next(track for track in layout.tracks if track.kind is TrackKind.GAS)
    assert gas.curve_mnemonics == ["TGAS", "C1", "C2"]
    assert gas.x_scale is XScale.LOGARITHMIC
    assert all(
        "TGAS" not in track.curve_mnemonics
        for track in layout.tracks
        if track.kind is TrackKind.CURVE
    )


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


def test_controller_sets_curve_style_and_marks_project_dirty() -> None:
    session = make_session()
    controller = TabletController(session)
    layout = controller.build_default_layout()
    track = next(item for item in layout.tracks if item.kind is TrackKind.GAS)
    session.dirty = False
    style = CurveStyle("#abcdef", 2.0, CurveLineStyle.DOT)

    controller.set_curve_style(track.track_id, "C1", style)

    assert track.curve_style("C1") == style
    assert session.dirty is True


def test_controller_sets_track_grid_and_marks_project_dirty() -> None:
    session = make_session()
    controller = TabletController(session)
    layout = controller.build_default_layout()
    track = next(item for item in layout.tracks if item.kind is TrackKind.GAS)
    session.dirty = False

    controller.set_track_grid(track.track_id, False, True, 0.35)

    assert (track.grid_x, track.grid_y, track.grid_alpha) == (False, True, 0.35)
    assert session.dirty is True


def test_controller_sets_track_x_axis_label() -> None:
    session = make_session()
    controller = TabletController(session)
    layout = controller.build_default_layout()
    track = next(item for item in layout.tracks if item.kind is TrackKind.GAS)
    session.dirty = False

    controller.set_track_x_axis_label(track.track_id, "  Gas, %  ")

    assert track.x_axis_label == "Gas, %"
    assert session.dirty is True


def test_controller_saves_and_applies_independent_preset_copy() -> None:
    session = make_session()
    controller = TabletController(session)
    source = controller.build_default_layout()
    source.tracks[0].width = 180

    controller.save_preset("  Standard  ")
    source.tracks[0].width = 320
    restored = controller.apply_preset("Standard")

    assert restored is session.current_tablet_layout
    assert restored is not session.tablet_presets["Standard"]
    assert restored.tracks[0].width == 180
    restored.tracks[0].width = 400
    assert session.tablet_presets["Standard"].tracks[0].width == 180


def test_controller_deletes_preset_and_rejects_empty_name() -> None:
    session = make_session()
    controller = TabletController(session)
    controller.build_default_layout()

    with pytest.raises(ValueError, match="пустым"):
        controller.save_preset("   ")
    controller.save_preset("Temporary")
    controller.delete_preset("Temporary")

    assert session.tablet_presets == {}


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


def test_dexp_track_collects_available_derived_curves() -> None:
    session = make_session()
    dataset = session.current_dataset
    assert dataset is not None
    dataset.upsert_curve("DEXP", np.array([1.0, 1.1]), unit="dimensionless")
    dataset.upsert_curve("DEXPC", np.array([0.9, 1.0]), unit="dimensionless")
    controller = TabletController(session)
    controller.build_default_layout()
    layout = session.current_tablet_layout
    assert layout is not None

    track = next(item for item in layout.tracks if item.kind is TrackKind.DEXP)

    assert track.title == "DEXP / NCT"
    assert track.curve_mnemonics == ["DEXP", "DEXPC"]
    assert track.width == 320


def test_add_dexp_track_requires_calculated_curves() -> None:
    controller = TabletController(make_session())
    controller.build_default_layout()
    with pytest.raises(ValueError, match="DEXP/NCT"):
        controller.add_track(TrackKind.DEXP)


def test_add_lithology_track_does_not_require_curves() -> None:
    controller = TabletController(make_session())
    controller.build_default_layout()

    track = controller.add_track(TrackKind.LITHOLOGY)

    assert track.kind is TrackKind.LITHOLOGY
    assert track.curve_mnemonics == []
    assert track.title == "Литология"


def test_add_cuttings_track_does_not_require_curves() -> None:
    session = make_session()
    controller = TabletController(session)
    controller.build_default_layout()

    track = controller.add_track(TrackKind.CUTTINGS)

    assert track.title == "Шламограмма"
    assert track.width == 240
    assert track.curve_mnemonics == []


@pytest.mark.parametrize(
    ("kind", "title", "width"),
    [
        (TrackKind.CALCIMETRY, "Кальциметрия", 220),
        (TrackKind.LBA, "ЛБА", 260),
    ],
)
def test_add_sample_analysis_tracks_without_curves(kind, title, width) -> None:
    controller = TabletController(make_session())
    controller.build_default_layout()

    track = controller.add_track(kind)

    assert track.title == title
    assert track.width == width
    assert track.curve_mnemonics == []


def test_default_layout_adds_available_calcimetry_and_lba_tracks() -> None:
    session = make_session()
    assert session.current_well is not None
    session.current_well.cuttings.append(
        CuttingsSample(
            "sample",
            1.0,
            2.0,
            calcite_percent=40.0,
            lba_intensity=2,
        )
    )

    kinds = [track.kind for track in TabletController(session).build_default_layout().tracks]

    assert TrackKind.CUTTINGS not in kinds
    assert TrackKind.CALCIMETRY in kinds
    assert TrackKind.LBA in kinds


def test_default_layout_adds_lithology_and_description_tracks() -> None:
    session = make_session()
    assert session.current_well is not None
    session.current_well.lithology.append(
        LithologyInterval("layer", 1.0, 2.0, "sandstone", "Песчаник")
    )

    layout = TabletController(session).build_default_layout()

    kinds = [track.kind for track in layout.tracks]
    assert TrackKind.LITHOLOGY in kinds
    assert TrackKind.TEXT in kinds


def test_add_description_track_does_not_require_curves() -> None:
    controller = TabletController(make_session())
    controller.build_default_layout()

    track = controller.add_track(TrackKind.TEXT)

    assert track.title == "Описание пород"
    assert track.width == 320
    assert track.curve_mnemonics == []


def test_stratigraphy_track_and_default_layout_do_not_require_curves() -> None:
    session = make_session()
    assert session.current_well is not None
    session.current_well.stratigraphy.append(
        StratigraphyInterval("stage", 1.0, 2.0, "K1a", "Albian", "Stage / Age")
    )
    controller = TabletController(session)

    layout = controller.build_default_layout()
    added = controller.add_track(TrackKind.STRATIGRAPHY)

    assert TrackKind.STRATIGRAPHY in [track.kind for track in layout.tracks]
    assert added.title == "Стратиграфия"
    assert added.width == 220
    assert added.curve_mnemonics == []


def test_controller_updates_track_x_settings() -> None:
    session = make_session()
    controller = TabletController(session)
    layout = controller.build_default_layout()
    track = next(item for item in layout.tracks if item.kind is TrackKind.GAS)
    session.dirty = False

    controller.set_track_x_range(track.track_id, 0.1, 100.0)
    controller.set_track_x_scale(track.track_id, XScale.LOGARITHMIC)

    assert track.x_scale is XScale.LOGARITHMIC
    assert track.x_min == 0.1
    assert track.x_max == 100.0
    assert session.dirty is True


def test_controller_updates_visible_depth_only_when_changed() -> None:
    session = make_session()
    controller = TabletController(session)
    layout = controller.build_default_layout()
    session.dirty = False

    assert controller.set_visible_depth(100.0, 200.0) is True
    assert layout.visible_depth_top == 100.0
    assert layout.visible_depth_bottom == 200.0
    assert session.dirty is True

    session.dirty = False
    assert controller.set_visible_depth(100.0, 200.0) is False

    assert controller.reset_visible_depth() is True
    assert layout.visible_depth_top is None
    assert layout.visible_depth_bottom is None
    assert session.dirty is True
    session.dirty = False
    assert controller.reset_visible_depth() is False
    assert session.dirty is False


def test_controller_persists_cursor_depth_in_current_layout() -> None:
    session = make_session()
    controller = TabletController(session)
    layout = controller.build_default_layout()
    controller.session.dirty = False

    assert controller.set_cursor_depth(150.0) is True
    assert layout.cursor_depth == 150.0
    assert controller.session.dirty is True
    controller.session.dirty = False
    assert controller.set_cursor_depth(150.0) is False
    assert controller.session.dirty is False


def test_update_track_view_settings_is_atomic_on_validation_error() -> None:
    session = make_session()
    controller = TabletController(session)
    layout = controller.build_default_layout()
    track = next(item for item in layout.tracks if item.kind is TrackKind.GAS)
    original = (track.width, track.x_scale, track.x_min, track.x_max)
    session.dirty = False

    with pytest.raises(ValueError, match="положительным"):
        controller.update_track_view_settings(
            track.track_id,
            width=500,
            x_scale=XScale.LOGARITHMIC,
            x_min=-1.0,
            x_max=100.0,
        )

    assert (track.width, track.x_scale, track.x_min, track.x_max) == original
    assert session.dirty is False


def test_commands_require_selected_dataset() -> None:
    controller = TabletController(ProjectSession())

    with pytest.raises(RuntimeError, match="набор данных"):
        controller.build_default_layout()


def test_default_layout_and_manual_track_support_interpretations() -> None:
    from geoworkbench.domain.models import WellInterpretation

    session = make_session()
    well = session.current_well
    assert well is not None
    well.interpretations["primary"] = WellInterpretation("primary", "Primary")
    controller = TabletController(session)

    layout = controller.build_default_layout()
    default_track = next(track for track in layout.tracks if track.kind is TrackKind.INTERPRETATION)
    manual_track = controller.add_track(TrackKind.INTERPRETATION)

    assert default_track.title == "Интерпретация"
    assert default_track.width == 280
    assert manual_track.kind is TrackKind.INTERPRETATION
    assert manual_track.curve_mnemonics == []


def test_layout_separates_incompatible_drilling_families() -> None:
    session = make_session()
    dataset = session.current_dataset
    assert dataset is not None
    dataset.upsert_curve("BIT_RPM", np.array([90.0, 100.0]), unit="rpm")
    dataset.upsert_curve("WOB", np.array([8.0, 9.0]), unit="kN")
    dataset.upsert_curve("SPP", np.array([1200.0, 1250.0]), unit="psi")

    layout = TabletController(session).build_layout_for_curves(["ROP", "BIT_RPM", "WOB", "SPP"])

    graph_tracks = [track for track in layout.tracks if track.kind is TrackKind.CURVE]
    assert [track.title for track in graph_tracks] == ["ROP", "RPM", "WOB", "SPP"]
    assert [track.curve_mnemonics for track in graph_tracks] == [
        ["ROP"],
        ["BIT_RPM"],
        ["WOB"],
        ["SPP"],
    ]


def test_layout_groups_only_compatible_resistivity_curves() -> None:
    session = make_session()
    dataset = session.current_dataset
    assert dataset is not None
    dataset.upsert_curve("ILD", np.array([2.0, 3.0]), unit="ohm.m")
    dataset.upsert_curve("LLD", np.array([4.0, 5.0]), unit="ohm.m")
    dataset.upsert_curve("GR", np.array([70.0, 80.0]), unit="API")

    layout = TabletController(session).build_layout_for_curves(["ILD", "LLD", "GR"])

    resistance = next(track for track in layout.tracks if track.title == "RES")
    gamma = next(track for track in layout.tracks if track.title == "GR")
    assert resistance.curve_mnemonics == ["ILD", "LLD"]
    assert resistance.x_scale is XScale.LOGARITHMIC
    assert gamma.curve_mnemonics == ["GR"]
    assert gamma.x_scale is XScale.LINEAR
