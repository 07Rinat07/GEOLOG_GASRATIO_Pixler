from __future__ import annotations

import re
from typing import Any

from PySide6.QtGui import QPainter

from geoworkbench.domain.models import Dataset
from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.printing.hydrocarbon_interpretation_pdf_chart import (
    render_chart_pages,
)
from geoworkbench.printing.hydrocarbon_interpretation_pdf_cover import (
    render_report_cover,
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
) -> None:
    """Render one controlled multi-page report to QPdfWriter or QPrinter."""

    html = hydrocarbon_interpretation_html(report, language)
    if dataset is not None:
        html = inject_interval_gas_statistics_html(html, report, dataset, language)
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
    canvas = PageCanvas(device, painter, language)
    try:
        canvas.new_page()
        render_report_cover(canvas, report, language, identity)

        if include_chart and dataset is not None:
            render_chart_pages(canvas, report, dataset, language)

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
