from __future__ import annotations

from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart_enhanced as chart
from geoworkbench.printing.geology_track_rendering import (
    FrozenCuttingsComponent,
    FrozenCuttingsSample,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology import (
    InterpretationGeologySnapshot,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology_settings import (
    GeologyTrackVisibility,
    InterpretationGeologyTrackSettings,
)


def _snapshot(*, cuttings: bool = True, lba: bool = True) -> InterpretationGeologySnapshot:
    return InterpretationGeologySnapshot(
        samples=(
            FrozenCuttingsSample(
                sample_id="sample-1",
                top_depth=1000.0,
                bottom_depth=1005.0,
                components=(
                    (FrozenCuttingsComponent("sandstone", 100.0),)
                    if cuttings
                    else ()
                ),
                lba_group=2 if lba else None,
            ),
        ),
        lithotypes=(),
    )


def test_geology_tracks_auto_follow_visible_interval_data() -> None:
    settings = InterpretationGeologyTrackSettings()

    assert chart._geology_track_kinds(_snapshot(), 1000.0, 1010.0, settings) == (
        "cuttings",
        "lba",
    )
    assert chart._geology_track_kinds(_snapshot(), 1100.0, 1110.0, settings) == ()


def test_geology_tracks_hide_overrides_populated_data() -> None:
    settings = InterpretationGeologyTrackSettings(
        cuttings=GeologyTrackVisibility.HIDE,
        lba=GeologyTrackVisibility.AUTO,
    )

    assert chart._geology_track_kinds(_snapshot(), 1000.0, 1010.0, settings) == ("lba",)


def test_geology_tracks_show_reserves_empty_tracks_without_snapshot() -> None:
    settings = InterpretationGeologyTrackSettings(
        cuttings=GeologyTrackVisibility.SHOW,
        lba=GeologyTrackVisibility.SHOW,
    )

    assert chart._geology_track_kinds(None, 1000.0, 1010.0, settings) == (
        "cuttings",
        "lba",
    )


def test_geology_track_modes_are_independent() -> None:
    settings = InterpretationGeologyTrackSettings(
        cuttings=GeologyTrackVisibility.SHOW,
        lba=GeologyTrackVisibility.HIDE,
    )

    assert chart._geology_track_kinds(
        _snapshot(cuttings=False, lba=True),
        1000.0,
        1010.0,
        settings,
    ) == ("cuttings",)


def test_forced_show_marks_empty_state_only_when_report_interval_has_no_data() -> None:
    settings = InterpretationGeologyTrackSettings(
        cuttings=GeologyTrackVisibility.SHOW,
        lba=GeologyTrackVisibility.SHOW,
    )

    assert chart._forced_empty_geology_tracks(
        None,
        1000.0,
        1010.0,
        settings,
    ) == ("cuttings", "lba")
    assert chart._forced_empty_geology_tracks(
        _snapshot(cuttings=True, lba=False),
        1000.0,
        1010.0,
        settings,
    ) == ("lba",)


def test_auto_track_with_partial_report_data_does_not_use_empty_state() -> None:
    settings = InterpretationGeologyTrackSettings(
        cuttings=GeologyTrackVisibility.AUTO,
        lba=GeologyTrackVisibility.AUTO,
    )
    geology = _snapshot()

    assert chart._geology_track_kinds(
        geology,
        1000.0,
        1010.0,
        settings,
    ) == ("cuttings", "lba")
    assert chart._forced_empty_geology_tracks(
        geology,
        1000.0,
        1010.0,
        settings,
    ) == ()
