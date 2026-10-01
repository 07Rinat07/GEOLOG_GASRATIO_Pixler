from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from PySide6.QtCore import QRectF

from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart_enhanced as chart
from geoworkbench.printing.geology_track_rendering import (
    FrozenCuttingsComponent,
    FrozenCuttingsSample,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology import (
    InterpretationGeologySnapshot,
)
from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import DepthPage
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


class _RecordingPainter:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def fillRect(self, *_args: object) -> None:
        return None

    def setFont(self, *_args: object) -> None:
        return None

    def setPen(self, *_args: object) -> None:
        return None

    def drawText(self, *args: object) -> None:
        if args and isinstance(args[-1], str):
            self.texts.append(args[-1])

    def drawLine(self, *_args: object) -> None:
        return None


def _snapshot_before_second_page() -> InterpretationGeologySnapshot:
    return InterpretationGeologySnapshot(
        samples=(
            FrozenCuttingsSample(
                sample_id="sample-first-page",
                top_depth=1000.0,
                bottom_depth=1004.0,
                components=(FrozenCuttingsComponent("sandstone", 100.0),),
                lba_group=2,
            ),
        ),
        lithotypes=(),
    )


def test_forced_show_without_snapshot_draws_headings_and_localized_empty_state(qapp) -> None:
    page = DepthPage(1000.0, 1010.0, 100, 300.0)
    geometry = chart.chart_geometry(
        QRectF(0.0, 0.0, 800.0, 500.0),
        page,
        1,
        geology_track_count=2,
    )
    painter = _RecordingPainter()

    chart._draw_geology_tracks(
        painter,  # type: ignore[arg-type]
        geometry,
        page,
        None,
        ("cuttings", "lba"),
        ("cuttings", "lba"),
        AppLanguage.RU,
    )

    assert "Шламограмма" in painter.texts
    assert "ЛБА" in painter.texts
    assert painter.texts.count("Нет данных") == 2


def test_partial_auto_page_gap_stays_empty_without_false_no_data_label(
    qapp,
    monkeypatch,
) -> None:
    page = DepthPage(1005.0, 1010.0, 100, 300.0)
    geometry = chart.chart_geometry(
        QRectF(0.0, 0.0, 800.0, 500.0),
        page,
        1,
        geology_track_count=2,
    )
    painter = _RecordingPainter()
    painted_samples: list[tuple[str, int]] = []

    monkeypatch.setattr(
        chart,
        "paint_cuttings_track",
        lambda _p, _r, samples, _depth_range, _lithotypes: painted_samples.append(
            ("cuttings", len(samples))
        ),
    )
    monkeypatch.setattr(
        chart,
        "paint_lba_track",
        lambda _p, _r, samples, _depth_range: painted_samples.append(
            ("lba", len(samples))
        ),
    )

    chart._draw_geology_tracks(
        painter,  # type: ignore[arg-type]
        geometry,
        page,
        _snapshot_before_second_page(),
        ("cuttings", "lba"),
        (),
        AppLanguage.RU,
    )

    assert "Нет данных" not in painter.texts
    assert painted_samples == [("cuttings", 0), ("lba", 0)]


def test_multi_page_auto_keeps_global_tracks_without_page_local_empty_state(
    monkeypatch,
) -> None:
    pages = (
        DepthPage(1000.0, 1005.0, 100, 300.0),
        DepthPage(1005.0, 1010.0, 100, 300.0),
    )
    observed: list[tuple[float, tuple[str, ...], tuple[str, ...]]] = []

    monkeypatch.setattr(
        chart.base_chart,
        "_panel_curves",
        lambda _report, _dataset: (("gas", (object(),)),),
    )
    monkeypatch.setattr(
        chart.base_chart,
        "_curve_percentiles",
        lambda _panels, _dataset, *, page: {},
    )
    monkeypatch.setattr(chart.base_chart, "_display_curve_ranges", lambda _values: {})
    monkeypatch.setattr(chart, "plan_depth_pages", lambda *_args: pages)

    def capture_page(*args: object) -> None:
        page = args[2]
        assert isinstance(page, DepthPage)
        geology_tracks = args[-2]
        empty_state_tracks = args[-1]
        assert isinstance(geology_tracks, tuple)
        assert isinstance(empty_state_tracks, tuple)
        observed.append((page.top_depth, geology_tracks, empty_state_tracks))

    monkeypatch.setattr(chart, "_draw_chart_page", capture_page)

    canvas = SimpleNamespace(
        content_rect=QRectF(0.0, 0.0, 800.0, 500.0),
        painter=object(),
        y=0.0,
        new_page=lambda: None,
    )
    dataset = SimpleNamespace(depth=np.asarray([1000.0, 1010.0], dtype=np.float64))
    report = SimpleNamespace(depth_unit="m")

    chart.render_chart_pages(
        canvas,  # type: ignore[arg-type]
        report,  # type: ignore[arg-type]
        dataset,  # type: ignore[arg-type]
        AppLanguage.RU,
        geology=_snapshot_before_second_page(),
        geology_track_settings=InterpretationGeologyTrackSettings(),
    )

    assert observed == [
        (1000.0, ("cuttings", "lba"), ()),
        (1005.0, ("cuttings", "lba"), ()),
    ]
