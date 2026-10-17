"""Optional method-comparison evidence survives both chart HTML layouts unchanged."""

from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.domain.report_composition import ReportLegendMode
from geoworkbench.printing import hydrocarbon_interpretation_chart as chart
from geoworkbench.printing import hydrocarbon_interpretation_chart_front as front
from geoworkbench.services.fluid_phase_contract import FluidPhaseContract
from geoworkbench.services.hydrocarbon_interpretation import HydrocarbonInterpretationReport
from geoworkbench.services.interpretation_method_comparison import (
    MethodComparisonInterval,
    MethodComparisonStatus,
)
from geoworkbench.services.interpretation_method_comparison_html import (
    method_comparison_html,
)
from geoworkbench.services.localization import AppLanguage


def _report() -> HydrocarbonInterpretationReport:
    return HydrocarbonInterpretationReport(
        project_name="Project",
        well_name="Well",
        dataset_id="source-dataset",
        dataset_name="Gas dataset",
        generated_at="2026-10-17T12:00:00Z",
        depth_unit="m",
        threshold=4.0,
        primary_mnemonic=None,
        baseline_median=None,
        robust_scale=None,
        methods=(),
        candidates=(),
        manual_intervals=(),
        warnings=(),
    )


def _comparison() -> MethodComparisonInterval:
    return MethodComparisonInterval(
        standard_bounds=(100.0, 104.0),
        opus_bounds=(100.0, 104.0),
        status=MethodComparisonStatus.AGREEMENT,
        reason_code="bounded_phase_agreement",
        overlap_depth=4.0,
        standard_overlap_fraction=1.0,
        opus_overlap_fraction=1.0,
        standard_phase=FluidPhaseContract.GAS,
        opus_phase=FluidPhaseContract.GAS,
        standard_wetness_robust_z=3.2,
        standard_pixler_c1_c2=17.0,
        opus_class_code=3,
        opus_support_fraction=0.625,
        opus_valid_rows=8,
    )


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("with_chart", (False, True))
@pytest.mark.parametrize("layout", ("front", "inline"))
def test_chart_layout_forwards_same_opt_in_comparison_and_preserves_default(
    monkeypatch: pytest.MonkeyPatch,
    language: AppLanguage,
    with_chart: bool,
    layout: str,
) -> None:
    report = _report()
    dataset = Dataset(
        "source-dataset", "Gas dataset", DatasetKind.GTI, DepthDomain.MD,
        np.array([100.0, 102.0, 104.0]),
    )
    comparison = _comparison()
    source_values = dataset.depth.copy()
    chart_uri = "data:image/png;base64,AA==" if with_chart else ""
    monkeypatch.setattr(
        chart, "hydrocarbon_interpretation_chart_data_uri",
        lambda *args, **kwargs: chart_uri,
    )
    monkeypatch.setattr(
        front, "hydrocarbon_interpretation_chart_data_uri",
        lambda *args, **kwargs: chart_uri,
    )
    monkeypatch.setattr(
        front, "ratio_reference_summary_uri",
        lambda *args, **kwargs: None,
    )

    def render(**kwargs: object) -> str:
        if layout == "front":
            return front.hydrocarbon_interpretation_html_with_front_chart(
                report, dataset, language,
                legend_mode=ReportLegendMode.HIDE,
                **kwargs,
            )
        return chart.hydrocarbon_interpretation_html_with_chart(
            report, dataset, language, **kwargs,
        )

    baseline = render()
    extended = render(method_comparisons=(comparison,))
    expected_section = method_comparison_html(
        (comparison,), language, depth_unit=report.depth_unit,
    )

    assert "method-comparison-analytics" not in baseline
    assert expected_section in extended
    assert extended.count("method-comparison-analytics") == 1
    assert "data-reason-code=\"bounded_phase_agreement\"" in extended
    assert ("data:image/png;base64,AA==" in extended) is with_chart
    np.testing.assert_array_equal(dataset.depth, source_values)
    assert report == _report()
