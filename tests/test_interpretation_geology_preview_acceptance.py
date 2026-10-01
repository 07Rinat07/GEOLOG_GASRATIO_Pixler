from __future__ import annotations

import base64
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPageLayout, QPageSize, QPainter, QPdfWriter

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart_enhanced as pdf_chart
from geoworkbench.printing import hydrocarbon_interpretation_chart as preview_chart
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
    DEFAULT_INTERPRETATION_GEOLOGY_TRACK_SETTINGS,
    GeologyTrackVisibility,
    InterpretationGeologyTrackSettings,
)
from geoworkbench.printing.hydrocarbon_interpretation_report_range import (
    ReportDepthRange,
)
from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.project.lithotype_catalog_models import CatalogLithotype
from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_workspace_final import (
    InterpretationReportWorkspace,
)


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


def test_large_preview_legend_grows_canvas_and_preserves_plot_height(qapp, monkeypatch):
    geology = InterpretationGeologySnapshot(
        samples=(FrozenCuttingsSample(
            sample_id="preview-catalog", top_depth=1000.0, bottom_depth=1020.0,
            components=tuple(
                FrozenCuttingsComponent(f"{index}: " + "Известняк с пиритом " * 30, 0.5)
                for index in range(200)
            ),
        ),),
        lithotypes=(),
    )
    plot_heights: list[float] = []
    draw_panel = preview_chart._draw_panel

    def record_panel(painter, rect, *args, **kwargs):
        plot_heights.append(rect.height())
        return draw_panel(painter, rect, *args, **kwargs)

    monkeypatch.setattr(preview_chart, "_draw_panel", record_panel)
    sizes = []
    for visibility in (GeologyTrackVisibility.HIDE, GeologyTrackVisibility.SHOW):
        uri = hydrocarbon_interpretation_chart_data_uri(
            _report(), _dataset(), AppLanguage.RU, geology=geology,
            geology_track_settings=InterpretationGeologyTrackSettings(
                cuttings=visibility, lba=GeologyTrackVisibility.HIDE,
            ),
        )
        image = QImage()
        assert image.loadFromData(base64.b64decode(uri.split(",", 1)[1]), "PNG")
        sizes.append((image.width(), image.height()))
    assert sizes[0] == (2000, 1280)
    assert sizes[1][0] == 2000
    assert sizes[1][1] > 2000
    assert plot_heights == [881.0, 881.0]


class _CanvasProbe:
    def __init__(self) -> None:
        self.content_rect = QRectF(0.0, 0.0, 800.0, 700.0)
        self.painter = SimpleNamespace(device=lambda: None)
        self.y = 0.0
        self.pages = 0

    def new_page(self) -> None:
        self.pages += 1


@pytest.mark.parametrize("count", [1, 60, 220])
@pytest.mark.parametrize("language", [AppLanguage.RU, AppLanguage.KK, AppLanguage.EN])
def test_landscape_pdf_exports_extreme_labels_and_catalogs(qapp, tmp_path, count, language):
    import fitz

    dataset = _dataset(depth_span=350.0, samples=351)
    report = _report()
    lithotypes = tuple(
        CatalogLithotype(
            str(index), f"R{index}", "Известняк с пиритом " * 200,
            "Limestone with pyrite " * 200, "sedimentary", "#c8c8b8", "carbonate", True,
            name_kk="Пирит түйіршіктері бар әктас " * 200,
        )
        for index in range(count)
    )
    geology = InterpretationGeologySnapshot(
        samples=(FrozenCuttingsSample(
            sample_id="many-rocks", top_depth=1000.0, bottom_depth=1350.0,
            components=tuple(FrozenCuttingsComponent(str(index), 100.0 / count)
                             for index in range(count)),
        ),),
        lithotypes=lithotypes,
    )
    output = tmp_path / "overflow.pdf"
    writer = QPdfWriter(str(output))
    writer.setResolution(72)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QPageLayout.Orientation.Landscape)
    painter = QPainter(writer)
    canvas = PageCanvas(writer, painter, language)
    try:
        pdf_chart.render_chart_pages(
            canvas, report, dataset, language, geology=geology,
        )
    finally:
        painter.end()
    with fitz.open(output) as document:
        text = "\n".join(page.get_text() for page in document)
        assert len(document) >= 3
        assert "R0" in text
        assert f"R{count - 1}" in text
        assert "…" in text
        assert "1000.00" in text
        assert "1350.00" in text
        assert all(page.rect.width > page.rect.height for page in document)
    assert dataset.depth[0] == 1000.0
    assert geology.lithotypes == lithotypes


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
        _geology_legend,
        _continuation_legend,
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
        _geology_legend,
        _continuation_legend,
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



def test_screen_preview_auto_ignores_geology_outside_selected_interval(qapp) -> None:
    dataset = _dataset()
    report = _report()
    geology = InterpretationGeologySnapshot(
        samples=(
            FrozenCuttingsSample(
                sample_id="outside",
                top_depth=1015.0,
                bottom_depth=1018.0,
                components=(FrozenCuttingsComponent("sandstone", 100.0),),
                lba_group=2,
            ),
        ),
        lithotypes=(),
    )
    depth_range = ReportDepthRange(1000.0, 1010.0)

    auto_uri = hydrocarbon_interpretation_chart_data_uri(
        report,
        dataset,
        AppLanguage.RU,
        geology=geology,
        geology_track_settings=InterpretationGeologyTrackSettings(),
        depth_range=depth_range,
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
        depth_range=depth_range,
    )

    assert auto_uri == hidden_uri


def test_preview_geology_state_does_not_leak_between_report_identities(
    qapp,
    monkeypatch,
) -> None:
    session = ProjectSession()
    session.add_dataset(_dataset(), "Well Preview")
    workspace = InterpretationReportWorkspace(
        InterpretationCalculationController(session),
        language=AppLanguage.RU,
    )
    first = SimpleNamespace(
        project_name="Project",
        well_name="Well Preview",
        dataset_id="preview-dataset",
        report_profile="standard",
    )
    second = SimpleNamespace(
        project_name="Project",
        well_name="Well Preview",
        dataset_id="another-dataset",
        report_profile="opus",
    )
    captured: list[tuple[InterpretationGeologyTrackSettings, ReportDepthRange | None]] = []

    monkeypatch.setattr(
        "geoworkbench.ui.interpretation_report_workspace_final."
        "interpretation_geology_snapshot",
        lambda _session: None,
    )

    def capture_html(_report, _dataset, _language, **kwargs):
        captured.append(
            (
                kwargs["geology_track_settings"],
                kwargs["depth_range"],
            )
        )
        return "<p>preview</p>"

    monkeypatch.setattr(
        "geoworkbench.ui.interpretation_report_workspace_final."
        "hydrocarbon_interpretation_html_with_front_chart",
        capture_html,
    )

    hidden = InterpretationGeologyTrackSettings(
        cuttings=GeologyTrackVisibility.HIDE,
        lba=GeologyTrackVisibility.HIDE,
    )
    workspace.report = first  # type: ignore[assignment]
    workspace._preview_geology_report_key = workspace._preview_report_key(first)  # type: ignore[arg-type]
    workspace._preview_geology_track_settings = hidden
    workspace._preview_depth_range = ReportDepthRange(1000.0, 1010.0)
    workspace._apply_chart_preview()

    workspace.report = second  # type: ignore[assignment]
    workspace._apply_chart_preview()

    assert captured[0] == (hidden, ReportDepthRange(1000.0, 1010.0))
    assert captured[1] == (DEFAULT_INTERPRETATION_GEOLOGY_TRACK_SETTINGS, None)
    workspace.close()


def test_opus_refresh_applies_chart_preview(qapp) -> None:
    workspace = InterpretationReportWorkspace(
        InterpretationCalculationController(ProjectSession()),
        language=AppLanguage.RU,
    )
    calls: list[bool] = []
    workspace._apply_chart_preview = lambda: calls.append(True)  # type: ignore[method-assign]
    opus_index = workspace.report_mode.findData("opus_text")
    assert opus_index >= 0
    workspace.report_mode.blockSignals(True)
    workspace.report_mode.setCurrentIndex(opus_index)
    workspace.report_mode.blockSignals(False)

    workspace.refresh()

    assert calls == [True]
    workspace.close()
