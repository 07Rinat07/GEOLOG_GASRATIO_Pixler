from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PySide6.QtCore import QRectF

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart_enhanced as chart
from geoworkbench.printing.hydrocarbon_interpretation_report_range import ReportDepthRange
from geoworkbench.services.localization import AppLanguage


def _dataset() -> Dataset:
    return Dataset(
        dataset_id="dataset-chart-range",
        name="Chart range",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.asarray([47.0, 1980.0, 2016.2, 2200.0], dtype=np.float64),
    )


def test_chart_page_planner_uses_selected_report_depth_range(monkeypatch) -> None:
    observed: list[tuple[float, float, float]] = []

    monkeypatch.setattr(
        chart.base_chart,
        "_panel_curves",
        lambda report, dataset: (("gas", (object(),)),),
    )
    monkeypatch.setattr(chart.base_chart, "_curve_ranges", lambda panels, dataset: {})

    def _plan(top: float, bottom: float, available: float):
        observed.append((top, bottom, available))
        return ()

    monkeypatch.setattr(chart, "plan_depth_pages", _plan)
    canvas = SimpleNamespace(content_rect=QRectF(0.0, 0.0, 842.0, 560.0))
    report = SimpleNamespace(depth_unit="m")

    chart.render_chart_pages(
        canvas,
        report,  # type: ignore[arg-type]
        _dataset(),
        AppLanguage.RU,
        depth_range=ReportDepthRange(1980.0, 2016.2),
    )

    assert len(observed) == 1
    assert observed[0][0:2] == (1980.0, 2016.2)
    assert observed[0][2] > 0.0


def test_enhanced_chart_uses_compact_markers_not_text_callout_stack() -> None:
    source = Path(
        "src/geoworkbench/printing/hydrocarbon_interpretation_pdf_chart_enhanced.py"
    ).read_text(encoding="utf-8")

    assert "_draw_fluid_callouts" not in source
    assert "_fluid_callout_interval_text" not in source
    assert "_stagger_callout_centers" not in source
    assert "_draw_fluid_markers(" in source
    assert "fluid_marker_legend_specs" in source
    assert "marker_lane_offsets" in source
    assert "minimum_gap=badge_height + 1.0" in source
    assert "len(visible) <= 12" not in source
    assert "marker_lanes" in source
