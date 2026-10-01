from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from PySide6.QtCore import QRectF

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart_enhanced as pdf_chart
from geoworkbench.printing.geology_track_rendering import (
    FrozenCuttingsComponent,
    FrozenCuttingsSample,
)
from geoworkbench.printing.hydrocarbon_interpretation_chart import (
    hydrocarbon_interpretation_chart_data_uri,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology import (
    InterpretationGeologySnapshot,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology_settings import (
    GeologyTrackVisibility,
    InterpretationGeologyTrackSettings,
)
from geoworkbench.services.localization import AppLanguage


def _dataset(*, depth_span: float = 20.0, samples: int = 41) -> Dataset:
    depth = np.linspace(1000.0, 1000.0 + depth_span, samples)
    dataset = Dataset(
        "preview-dataset",
        "Preview",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    dataset.curves["tg"] = CurveData(
        CurveMetadata(
            "tg",
            "TG_CALC",
            "TG_CALC",
            "%",
            "Total gas",
            dataset.dataset_id,
        ),
        np.linspace(0.1, 1.0, samples),
    )
    return dataset


def _report():
    return SimpleNamespace(
        report_profile="standard",
        primary_mnemonic="TG_CALC",
        methods=(),
        candidates=(),
        depth_unit="m",
    )


def _geology() -> InterpretationGeologySnapshot:
    return InterpretationGeologySnapshot(
        samples=(
            FrozenCuttingsSample(
                sample_id="sample-1",
                top_depth=1002.0,
                bottom_depth=1006.0,
                components=(FrozenCuttingsComponent("sandstone", 100.0),),
                lba_group=2,
                lba_intensity=3,
                lba_color="yellow",
            ),
        ),
        lithotypes=(),
    )


def test_screen_preview_uses_same_auto_hide_show_geology_composition(qapp) -> None:
    dataset = _dataset()
    report = _report()
    geology = _geology()

    auto_uri = hydrocarbon_interpretation_chart_data_uri(
        report,
        dataset,
        AppLanguage.RU,
        geology=geology,
        geology_track_settings=InterpretationGeologyTrackSettings(),
    )
    hidden_uri = hydrocarbon_interpretation_chart_data_uri(
        report,
        dataset,
        AppLanguage.RU,
        geology=geology,
        geology_track_settings=InterpretationGeologyTrackSettings(
            cuttings=GeologyTrackVisibility.HIDE,
            lba=GeologyTrackVisibility.HIDE,
        ),
    )
    forced_empty_uri = hydrocarbon_interpretation_chart_data_uri(
        report,
        dataset,
        AppLanguage.EN,
        geology=None,
        geology_track_settings=InterpretationGeologyTrackSettings(
            cuttings=GeologyTrackVisibility.SHOW,
            lba=GeologyTrackVisibility.SHOW,
        ),
    )

    assert auto_uri.startswith("data:image/png;base64,")
    assert hidden_uri.startswith("data:image/png;base64,")
    assert forced_empty_uri.startswith("data:image/png;base64,")
    assert auto_uri != hidden_uri
    assert forced_empty_uri != hidden_uri


class _CanvasProbe:
    def __init__(self) -> None:
        self.content_rect = QRectF(0.0, 0.0, 800.0, 700.0)
        self.painter = object()
        self.y = 0.0
        self.pages = 0

    def new_page(self) -> None:
        self.pages += 1


def test_multi_page_partial_geology_keeps_page_gaps_empty(monkeypatch) -> None:
    dataset = _dataset(depth_span=2500.0, samples=501)
    report = _report()
    geology = _geology()
    settings = InterpretationGeologyTrackSettings(
        cuttings=GeologyTrackVisibility.SHOW,
        lba=GeologyTrackVisibility.SHOW,
    )
    observed: list[tuple[float, float, tuple[str, ...], tuple[str, ...]]] = []

    def capture_page(
        _painter,
        _geometry,
        page,
        _page_index,
        _page_count,
        _report,
        _dataset,
        _panels,
        _ranges,
        _percentiles,
        _language,
        _geology,
        geology_tracks,
        empty_state_tracks,
    ) -> None:
        observed.append(
            (
                page.top_depth,
                page.bottom_depth,
                geology_tracks,
                empty_state_tracks,
            )
        )

    monkeypatch.setattr(pdf_chart, "_draw_chart_page", capture_page)
    canvas = _CanvasProbe()
    pdf_chart.render_chart_pages(
        canvas,  # type: ignore[arg-type]
        report,  # type: ignore[arg-type]
        dataset,
        AppLanguage.RU,
        geology=geology,
        geology_track_settings=settings,
    )

    assert canvas.pages > 1
    assert len(observed) == canvas.pages
    assert all(item[2] == ("cuttings", "lba") for item in observed)
    assert all(item[3] == () for item in observed)
    assert any(top > 1006.0 for top, _bottom, _tracks, _empty in observed)


def test_multi_page_forced_empty_tracks_keep_one_report_level_empty_state(monkeypatch) -> None:
    dataset = _dataset(depth_span=2500.0, samples=501)
    report = _report()
    settings = InterpretationGeologyTrackSettings(
        cuttings=GeologyTrackVisibility.SHOW,
        lba=GeologyTrackVisibility.SHOW,
    )
    observed: list[tuple[str, ...]] = []

    def capture_page(
        _painter,
        _geometry,
        _page,
        _page_index,
        _page_count,
        _report,
        _dataset,
        _panels,
        _ranges,
        _percentiles,
        _language,
        _geology,
        _geology_tracks,
        empty_state_tracks,
    ) -> None:
        observed.append(empty_state_tracks)

    monkeypatch.setattr(pdf_chart, "_draw_chart_page", capture_page)
    canvas = _CanvasProbe()
    pdf_chart.render_chart_pages(
        canvas,  # type: ignore[arg-type]
        report,  # type: ignore[arg-type]
        dataset,
        AppLanguage.EN,
        geology=None,
        geology_track_settings=settings,
    )

    assert canvas.pages > 1
    assert observed
    assert all(item == ("cuttings", "lba") for item in observed)
