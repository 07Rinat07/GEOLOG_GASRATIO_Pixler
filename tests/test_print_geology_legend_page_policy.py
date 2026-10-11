"""Geological legend belongs on first chart sheet by default, not every sheet."""

from __future__ import annotations

from dataclasses import replace
import json

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QRectF

from geoworkbench.domain.report_composition import (
    InterpretationReportComposition,
    ReportGeologyLegendPages,
)
from geoworkbench.printing.hydrocarbon_interpretation_pdf_chart_enhanced import (
    _reflow_depth_pages_after_first_legend,
)
from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import (
    DepthPage,
    chart_geometry,
)
from geoworkbench.printing.hydrocarbon_interpretation_report import (
    export_hydrocarbon_interpretation_pdf,
)
from geoworkbench.project.controller import ProjectController
from geoworkbench.services.hydrocarbon_interpretation import build_hydrocarbon_interpretation_report
from geoworkbench.services.localization import AppLanguage
from geoworkbench.storage.project_codec import ProjectFormatError, load_project_document
from geoworkbench.ui.interpretation_print_layout_dialog import InterpretationPrintLayoutDialog
from test_interpretation_geology_legends import _snapshot
from test_interpretation_report_charts import _session_with_report_curves
from test_report_chart_panel_composition import _session


def test_default_and_layout_dialog_can_switch_first_or_every_page(qapp):
    assert (
        InterpretationReportComposition().geology_legend_pages
        is ReportGeologyLegendPages.FIRST_CHART_PAGE
    )
    for language in AppLanguage:
        dialog = InterpretationPrintLayoutDialog(language=language)
        try:
            assert dialog.geology_legend_pages_combo.count() == 2
            assert dialog.selected_layout().geology_legend_pages is ReportGeologyLegendPages.FIRST_CHART_PAGE
            assert dialog.selected_composition().geology_legend_pages is ReportGeologyLegendPages.FIRST_CHART_PAGE
            dialog.geology_legend_pages_combo.setCurrentIndex(1)
            assert dialog.selected_layout().geology_legend_pages is ReportGeologyLegendPages.EVERY_CHART_PAGE
            assert dialog.selected_composition().geology_legend_pages is ReportGeologyLegendPages.EVERY_CHART_PAGE
        finally:
            dialog.close()


@pytest.mark.parametrize("suffix", (".geolog.json", ".geologpkg"))
@pytest.mark.parametrize("scope", tuple(ReportGeologyLegendPages))
def test_scope_persists_for_json_and_package(tmp_path, suffix, scope):
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None
    session.report_compositions[dataset.dataset_id] = InterpretationReportComposition(
        composition_id="rpt-legend-pages", geology_legend_pages=scope,
    )
    destination = tmp_path / ("legend-pages" + suffix)
    ProjectController(session=session).save_project(destination)
    reopened = ProjectController().open_project(destination)
    assert reopened.report_compositions[dataset.dataset_id].geology_legend_pages is scope


def test_old_project_without_scope_defaults_to_first_and_rejects_bad_value(tmp_path):
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None
    session.report_compositions[dataset.dataset_id] = InterpretationReportComposition(
        composition_id="rpt-legacy-scope",
        geology_legend_pages=ReportGeologyLegendPages.EVERY_CHART_PAGE,
    )
    target = tmp_path / "old-v37.geolog.json"
    ProjectController(session=session).save_project(target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    raw = payload["report_compositions"][dataset.dataset_id]
    assert raw.pop("geology_legend_pages") == "every-chart-page"
    target.write_text(json.dumps(payload), encoding="utf-8")
    loaded = load_project_document(target)
    assert loaded.report_compositions[dataset.dataset_id].geology_legend_pages is ReportGeologyLegendPages.FIRST_CHART_PAGE
    raw["geology_legend_pages"] = "sometimes"
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ProjectFormatError, match="Некорректная report composition"):
        load_project_document(target)


def test_page_reflow_preserves_contiguous_depth_scale_and_uses_legend_space():
    pages = tuple(DepthPage(index * 100.0, (index + 1) * 100.0, 1800, 158.0)
                  for index in range(5))
    first_capacity, following_capacity = 175.0, 270.0
    result = _reflow_depth_pages_after_first_legend(
        pages, 0.0, 500.0,
        first_plot_capacity=first_capacity,
        later_plot_capacity=following_capacity,
    )
    assert 2 <= len(result) < len(pages)
    assert result[0].top_depth == 0.0
    assert result[-1].bottom_depth == 500.0
    assert {page.scale_denominator for page in result} == {1800}
    assert all(a.bottom_depth == pytest.approx(b.top_depth) for a, b in zip(result, result[1:]))
    assert result[0].plot_height_points <= first_capacity + 0.01
    assert all(page.plot_height_points <= following_capacity + 0.01 for page in result[1:])
    assert result[1].plot_height_points > result[0].plot_height_points
    content = QRectF(0, 0, 740, 580)
    first = chart_geometry(content, result[0], 3, geology_track_count=2,
                           geology_legend_height=95.0)
    second = chart_geometry(content, result[1], 3, geology_track_count=2,
                            geology_legend_height=0.0)
    assert first.geology_legend_rect is not None
    assert second.geology_legend_rect is None
    assert second.plot_rect.height() > first.plot_rect.height()
    assert second.plot_rect.top() < first.plot_rect.top()


@pytest.mark.parametrize("language", (AppLanguage.RU, AppLanguage.EN))
def test_real_pdf_places_geology_legend_only_on_first_chart_unless_opted_in(
    qapp, tmp_path, language,
):
    session = _session_with_report_curves(
        depth_start=1000.0, depth_span=650.0, samples=651,
    )
    dataset = session.current_dataset
    assert dataset is not None
    original_depth = dataset.depth.copy()
    original_values = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    report = build_hydrocarbon_interpretation_report(session)
    appearances = {}
    for policy in ReportGeologyLegendPages:
        target = tmp_path / f"{language.value}-{policy.value}.pdf"
        export_hydrocarbon_interpretation_pdf(
            report, target, language=language, dataset=dataset,
            include_chart=True, geology=_snapshot(), geology_legend_pages=policy,
        )
        with fitz.open(target) as pdf:
            chart_texts = [
                page.get_text() for page in pdf
                if ("Лист графика" if language is AppLanguage.RU else "Chart sheet") in page.get_text()
            ]
            # Language-dependent page heading may use a different translation.
            if not chart_texts:
                chart_texts = [page.get_text() for page in pdf if "1:" in page.get_text()]
        assert len(chart_texts) >= 2
        legend_text = "Геологическая легенда" if language is AppLanguage.RU else "Geology legend"
        counts = [text.count(legend_text) for text in chart_texts]
        assert counts[0] == 1
        assert all(count == (1 if policy is ReportGeologyLegendPages.EVERY_CHART_PAGE else 0)
                   for count in counts[1:])
        appearances[policy] = len(chart_texts)
    assert appearances[ReportGeologyLegendPages.FIRST_CHART_PAGE] <= appearances[
        ReportGeologyLegendPages.EVERY_CHART_PAGE
    ]
    np.testing.assert_array_equal(dataset.depth, original_depth)
    for key, curve in dataset.curves.items():
        np.testing.assert_array_equal(curve.values, original_values[key])
