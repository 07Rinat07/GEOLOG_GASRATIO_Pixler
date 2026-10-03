from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.domain.report_composition import ReportLegendMode
from geoworkbench.printing import hydrocarbon_interpretation_pdf_renderer as renderer
from geoworkbench.printing.hydrocarbon_interpretation_pdf_chart import (
    _curve_percentiles,
    _curve_ranges,
)
from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import DepthPage
from geoworkbench.printing.hydrocarbon_interpretation_geology_legend import (
    GeologyLegendItem,
    InterpretationGeologyLegend,
)
from geoworkbench.services.gas_curve_presentation import (
    gas_report_scatter_point_budget,
    gas_scatter_point_budget,
    select_report_gas_scatter_samples,
)
from geoworkbench.services.localization import AppLanguage


def test_report_gas_ratio_sampler_is_dense_uniform_and_source_factual() -> None:
    depth = np.linspace(1000.0, 1100.0, 10_001, dtype=np.float64)
    values = 3.0 + np.sin(depth * 0.7) + 0.15 * np.cos(depth * 2.1)
    budget = gas_report_scatter_point_budget(360.0)

    selected_values, selected_depth = select_report_gas_scatter_samples(
        depth,
        values,
        float(depth[0]),
        float(depth[-1]),
        max_points=budget,
    )

    assert budget > gas_scatter_point_budget(360.0)
    assert 0 < selected_depth.size <= budget
    assert selected_depth.size == selected_values.size
    assert np.all(np.diff(selected_depth) > 0.0)

    normalized = (selected_depth - depth[0]) / (depth[-1] - depth[0])
    buckets = np.minimum(
        budget - 1,
        np.floor(normalized * budget).astype(np.int64),
    )
    assert np.unique(buckets).size == buckets.size

    source_positions = np.searchsorted(depth, selected_depth)
    assert np.all(depth[source_positions] == selected_depth)
    assert np.all(values[source_positions] == selected_values)


def test_ratio_display_range_uses_visible_minmax_without_changing_p5_p95() -> None:
    depth = np.linspace(100.0, 110.0, 101, dtype=np.float64)
    values = np.linspace(10.0, 20.0, depth.size, dtype=np.float64)
    values[0] = -50.0
    values[-1] = 90.0
    dataset = Dataset(
        dataset_id="ratio-range-contract",
        name="Ratio range",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=depth,
    )
    curve = CurveData(
        CurveMetadata(
            "ratio",
            "C1_C2",
            "C1_C2",
            "ratio",
            None,
            dataset.dataset_id,
        ),
        values,
    )
    dataset.curves[curve.metadata.curve_id] = curve
    panels = (("ratios", (curve,)),)
    page = DepthPage(100.0, 110.0, 100, 300.0)

    percentiles = _curve_percentiles(panels, dataset, page=page)
    display = _curve_ranges(panels, dataset, page=page)

    assert percentiles[curve.metadata.curve_id][0] > float(np.min(values))
    assert percentiles[curve.metadata.curve_id][1] < float(np.max(values))
    assert display[curve.metadata.curve_id] == (
        float(np.min(values)),
        float(np.max(values)),
    )


def test_report_methodology_starts_after_dedicated_geology_legend_page(
    qapp,
    monkeypatch,
) -> None:
    events: list[tuple[str, int, str]] = []

    class CanvasProbe:
        last: "CanvasProbe | None" = None

        def __init__(self, device, painter, language, *, layout_profile) -> None:
            del device, language, layout_profile
            self.painter = painter
            self.content_rect = QRectF(0.0, 0.0, 500.0, 700.0)
            self.y = self.content_rect.top()
            self.page = 0
            CanvasProbe.last = self

        def new_page(self) -> None:
            self.page += 1
            self.y = self.content_rect.top()

    dataset = Dataset(
        dataset_id="report-visual-contract",
        name="Dataset",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.asarray([1000.0, 1010.0], dtype=np.float64),
    )
    report = SimpleNamespace(analysis_depth_interval=None)
    legend = InterpretationGeologyLegend(
        (
            GeologyLegendItem(
                "lithology",
                "limestone",
                "LS",
                "Известняк",
            ),
        )
    )

    monkeypatch.setattr(renderer, "PageCanvas", CanvasProbe)
    monkeypatch.setattr(renderer, "hydrocarbon_interpretation_html", lambda *args: "<body/>")
    monkeypatch.setattr(
        renderer,
        "inject_interval_gas_statistics_html",
        lambda html, *args: html,
    )
    monkeypatch.setattr(
        renderer,
        "inject_report_optional_sections_html",
        lambda html, *args: html,
    )
    monkeypatch.setattr(renderer, "scope_dataset", lambda *args: dataset)
    monkeypatch.setattr(
        renderer,
        "interpretation_chart_key_html",
        lambda *args: "<h2>METHOD</h2>",
    )
    monkeypatch.setattr(renderer, "resolve_geology_track_kinds", lambda *args: ("cuttings",))
    monkeypatch.setattr(renderer, "build_interpretation_geology_legend", lambda *args, **kwargs: legend)
    monkeypatch.setattr(renderer, "paginate_geology_legend", lambda *args, **kwargs: (legend,))
    monkeypatch.setattr(renderer, "geology_legend_height", lambda *args, **kwargs: 80.0)

    def paint_legend(*args, **kwargs) -> None:
        del args, kwargs
        canvas = CanvasProbe.last
        assert canvas is not None
        events.append(("legend", canvas.page, ""))

    def render_html(canvas, html, **kwargs) -> None:
        del kwargs
        events.append(("html", canvas.page, html))

    monkeypatch.setattr(renderer, "paint_geology_legend", paint_legend)
    monkeypatch.setattr(renderer, "render_report_html", render_html)
    monkeypatch.setattr(renderer, "render_report_cover", lambda *args, **kwargs: None)
    monkeypatch.setattr(renderer, "render_chart_pages", lambda *args, **kwargs: None)

    image = QImage(900, 1200, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0xFFFFFFFF)
    renderer.render_hydrocarbon_interpretation_report(
        image,
        report,  # type: ignore[arg-type]
        language=AppLanguage.RU,
        dataset=dataset,
        include_chart=True,
        legend_mode=ReportLegendMode.FULL,
    )

    legend_pages = [page for kind, page, _ in events if kind == "legend"]
    method_pages = [
        page
        for kind, page, html in events
        if kind == "html" and "METHOD" in html
    ]
    assert legend_pages
    assert method_pages
    assert max(legend_pages) < min(method_pages)
    assert set(legend_pages).isdisjoint(method_pages)
