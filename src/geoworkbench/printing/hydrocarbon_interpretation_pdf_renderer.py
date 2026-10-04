from __future__ import annotations

import re
from typing import Any

import numpy as np

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter

from geoworkbench.domain.models import Dataset
from geoworkbench.domain.report_composition import ReportLayoutProfile, ReportLegendMode
from geoworkbench.domain.report_annotations import ReportAnnotationRecord
from geoworkbench.domain.depth_interval import scope_dataset
from geoworkbench.printing.interpretation_chart_key import interpretation_chart_key_html
from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.printing.hydrocarbon_interpretation_pdf_chart_enhanced import (
    render_chart_pages,
)
from geoworkbench.printing.hydrocarbon_interpretation_pdf_cover import (
    render_report_cover,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology import (
    InterpretationGeologySnapshot,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology_legend import (
    build_interpretation_geology_legend,
    geology_legend_height,
    paint_geology_legend,
    paginate_geology_legend,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology_settings import (
    DEFAULT_INTERPRETATION_GEOLOGY_TRACK_SETTINGS,
    InterpretationGeologyTrackSettings,
    resolve_geology_track_kinds,
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
) -> None:
    """Render one controlled multi-page report to QPdfWriter or QPrinter."""

    html = hydrocarbon_interpretation_html(report, language)
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
    )
    try:
        canvas.new_page()
        render_report_cover(canvas, report, language, identity)

        if include_chart and dataset is not None:
            scoped = scope_dataset(dataset, report.analysis_depth_interval)
            key_html = interpretation_chart_key_html(
                report, scoped, language,
            )
            if key_html and legend_mode is not ReportLegendMode.HIDE:
                top = float(np.nanmin(scoped.depth))
                bottom = float(np.nanmax(scoped.depth))
                bounds = report.analysis_depth_interval or depth_range
                if bounds is not None:
                    top, bottom = bounds.top_depth, bounds.bottom_depth
                tracks = resolve_geology_track_kinds(
                    geology, top, bottom, geology_track_settings,
                )

                # Reference geology and methodology are separate document
                # sections. Never let the full geology/LBA legend share a page
                # with "Пояснения к графикам" or calculation formulas.
                if legend_mode is ReportLegendMode.FULL:
                    legend = build_interpretation_geology_legend(
                        geology,
                        top,
                        bottom,
                        language,
                        include_cuttings="cuttings" in tracks,
                        include_lba="lba" in tracks,
                    )
                    for legend_page in paginate_geology_legend(
                        canvas.content_rect.width(),
                        legend,
                        canvas.content_rect.height(),
                        compact=False,
                        paint_device=device,
                    ):
                        height = geology_legend_height(
                            canvas.content_rect.width(),
                            legend_page,
                            paint_device=device,
                        )
                        if height <= 0.0:
                            continue
                        canvas.new_page()
                        paint_geology_legend(
                            painter,
                            QRectF(
                                canvas.content_rect.left(),
                                canvas.content_rect.top(),
                                canvas.content_rect.width(),
                                height,
                            ),
                            legend_page,
                            language,
                        )
                        canvas.y = canvas.content_rect.bottom()

                # Methodology/key always starts on its own clean page, even when
                # the geology legend is empty or hidden by data availability.
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
                legend_mode=legend_mode,
                annotations=annotations,
            )

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
