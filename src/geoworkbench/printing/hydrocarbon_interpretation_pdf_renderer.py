from __future__ import annotations

from geoworkbench.printing.hydrocarbon_interpretation_curve_selection import chart_panel_render_options

from geoworkbench.printing.gas_ratio_reference import (
    has_ratio_reference_summary, paint_ratio_reference_summary,
)

import re
from typing import Any

from PySide6.QtGui import QPainter

from geoworkbench.domain.models import Dataset
from geoworkbench.domain.report_composition import (
    DEFAULT_REPORT_CHART_PANELS,
    ReportChartPanelSettings,
    ReportLayoutProfile,
    ReportLegendMode,
)
from geoworkbench.domain.report_annotations import ReportAnnotationRecord
from geoworkbench.domain.depth_interval import scope_dataset
from geoworkbench.printing.interpretation_chart_key import interpretation_chart_key_html
from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.printing.report_document_control import report_document_control, resolved_report_identity
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import report_with_presentation_identity
from geoworkbench.printing.hydrocarbon_interpretation_pdf_chart_enhanced import (
    render_chart_pages,
)
from geoworkbench.printing.hydrocarbon_interpretation_pdf_chart import _panel_curves
from geoworkbench.printing.hydrocarbon_interpretation_pdf_cover import (
    render_report_cover,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology import (
    InterpretationGeologySnapshot,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology_settings import (
    DEFAULT_INTERPRETATION_GEOLOGY_TRACK_SETTINGS,
    InterpretationGeologyTrackSettings,
)
from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import (
    ChartGeometry,
    DepthPage,
    chart_geometry,
    plan_depth_pages,
)
from geoworkbench.printing.hydrocarbon_interpretation_pdf_text import (
    render_report_html,
)
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
    InterpretationReportIdentity,
    inject_report_optional_sections_html,
)
from geoworkbench.printing.hydrocarbon_interpretation_report_range import (
    ReportDepthRange,
)
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
    hydrocarbon_interpretation_html,
)
from geoworkbench.services.hydrocarbon_interpretation_gas_html import (
    inject_interval_gas_statistics_html,
)
from geoworkbench.services.localization import AppLanguage


_FRONT_MATTER_PATTERN = re.compile(
    r"(<body\b[^>]*>)\s*<h1\b[^>]*>.*?</h1>\s*<p\b[^>]*>.*?</p>",
    re.IGNORECASE | re.DOTALL,
)


def render_hydrocarbon_interpretation_report(
    device: Any,
    report: HydrocarbonInterpretationReport,
    *,
    language: AppLanguage = AppLanguage.RU,
    dataset: Dataset | None = None,
    include_chart: bool = False,
    identity: InterpretationReportIdentity | None = None,
    depth_range: ReportDepthRange | None = None,
    geology: InterpretationGeologySnapshot | None = None,
    geology_track_settings: InterpretationGeologyTrackSettings = (
        DEFAULT_INTERPRETATION_GEOLOGY_TRACK_SETTINGS
    ),
    legend_mode: ReportLegendMode = ReportLegendMode.FULL,
    layout_profile: ReportLayoutProfile = ReportLayoutProfile.MODERN_OILFIELD,
    annotations: tuple[ReportAnnotationRecord, ...] = (),
    chart_panels: ReportChartPanelSettings = DEFAULT_REPORT_CHART_PANELS,
    target_depth_per_page: float = 100.0,
) -> None:
    """Render one controlled multi-page report to QPdfWriter or QPrinter."""

    html = hydrocarbon_interpretation_html(
        report_with_presentation_identity(report, identity), language,
    )
    if dataset is not None:
        html = inject_interval_gas_statistics_html(html, report, dataset, language)
    html = inject_report_optional_sections_html(html, identity, language)
    body_html = _FRONT_MATTER_PATTERN.sub(r"\1", html, count=1)

    painter = QPainter(device)
    if not painter.isActive():
        raise RuntimeError("Не удалось запустить движок печати отчёта")
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    painter.scale(
        float(device.logicalDpiX()) / 72.0,
        float(device.logicalDpiY()) / 72.0,
    )
    canvas = PageCanvas(
        device,
        painter,
        language,
        layout_profile=layout_profile,
        document_control=report_document_control(resolved_report_identity(report, identity, language), language),
    )
    try:
        canvas.new_page()
        render_report_cover(canvas, report, language, identity)

        if include_chart and dataset is not None and (
            chart_panels == DEFAULT_REPORT_CHART_PANELS
            or any(curves for _name, curves in _panel_curves(report, dataset, chart_panels))
        ):
            scoped = scope_dataset(dataset, report.analysis_depth_interval)
            key_html = interpretation_chart_key_html(
                report, scoped, language,
                **chart_panel_render_options(chart_panels),
            )
            # Interpretation reports start with the method/formula explanation.
            # A separate geology-catalog page before it is not useful and wastes
            # printable space. FULL therefore means a compact decoded legend on
            # chart sheets; HIDE still suppresses geology legend rendering.
            chart_legend_mode = (
                ReportLegendMode.COMPACT
                if legend_mode is ReportLegendMode.FULL
                else legend_mode
            )
            legend_reference_pages_emitted = True
            if key_html:
                canvas.new_page()
                render_report_html(
                    canvas,
                    key_html,
                    leading_block_count=0,
                    start_body_on_new_page=False,
                )
            render_chart_pages(
                canvas,
                report,
                dataset,
                language,
                depth_range=depth_range,
                geology=geology,
                geology_track_settings=geology_track_settings,
                legend_mode=chart_legend_mode,
                legend_reference_pages_emitted=legend_reference_pages_emitted,
                annotations=annotations,
                target_depth_per_page=target_depth_per_page,
                **chart_panel_render_options(chart_panels),
            )

            reference_dataset = scope_dataset(dataset, report.analysis_depth_interval or depth_range)
            if has_ratio_reference_summary(reference_dataset):
                canvas.new_page()
                paint_ratio_reference_summary(painter, canvas.content_rect, reference_dataset, language)
                canvas.y = canvas.content_rect.bottom()

        render_report_html(
            canvas,
            body_html,
            leading_block_count=0,
        )
    finally:
        painter.end()


__all__ = [
    "ChartGeometry",
    "DepthPage",
    "chart_geometry",
    "plan_depth_pages",
    "render_hydrocarbon_interpretation_report",
]
