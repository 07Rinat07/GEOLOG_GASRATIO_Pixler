from __future__ import annotations

import numpy as np
from typing import TypedDict

from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.domain.report_composition import (
    DEFAULT_REPORT_CHART_PANELS, ReportChartPanelSettings,
)
from geoworkbench.services.hydrocarbon_interpretation import HydrocarbonInterpretationReport


class ReportChartPanelRenderOptions(TypedDict, total=False):
    chart_panels: ReportChartPanelSettings


def chart_panel_render_options(
    settings: ReportChartPanelSettings,
) -> ReportChartPanelRenderOptions:
    """Keep legacy/default renderer hooks compatible while forwarding custom state."""
    return {} if settings == DEFAULT_REPORT_CHART_PANELS else {"chart_panels": settings}


def report_curve_panels(
    report: HydrocarbonInterpretationReport,
    dataset: Dataset,
    marker_groups: tuple[tuple[str, tuple[str, ...]], ...],
    settings: ReportChartPanelSettings = DEFAULT_REPORT_CHART_PANELS,
) -> tuple[tuple[str, tuple[CurveData, ...]], ...]:
    """Match plotted channels to report evidence, including source-only LAS names."""

    primary = tuple(
        part.strip()
        for part in (report.primary_mnemonic or "").split("|")
        if part.strip()
    )
    panels: list[tuple[str, tuple[CurveData, ...]]] = []
    hidden = {panel.value for panel in settings.hidden}
    for panel_name, fallback_order in marker_groups:
        if panel_name in hidden:
            continue
        reported: list[str] = list(primary) if panel_name == "total" else []
        fallback_names = set(fallback_order)
        for method in report.methods:
            supported_panels = sum(
                any(name.upper() in set(markers) for name in method.curve_mnemonics)
                for _name, markers in marker_groups
            )
            if supported_panels == 1 and any(
                name.upper() in fallback_names for name in method.curve_mnemonics
            ):
                reported.extend(method.available_mnemonics)

        minimum_samples = 1 if panel_name in {"ratios", "opus"} else 2
        curves: list[CurveData] = []
        seen: set[str] = set()
        for candidate in (*reported, *fallback_order):
            curve = dataset.curve_by_mnemonic(_strip_source_prefix(candidate))
            if curve is None or curve.metadata.curve_id in seen:
                continue
            names = {
                curve.metadata.original_mnemonic.upper(),
                (curve.metadata.canonical_mnemonic or "").upper(),
            }
            if candidate not in reported and names.isdisjoint(fallback_names):
                continue
            values = np.asarray(curve.values, dtype=np.float64)
            if (
                values.shape != dataset.depth.shape
                or np.count_nonzero(np.isfinite(values)) < minimum_samples
            ):
                continue
            curves.append(curve)
            seen.add(curve.metadata.curve_id)
            if len(curves) >= (3 if panel_name == "total" else 5):
                break
        panels.append((panel_name, tuple(curves)))
    available = dict(panels)
    return tuple(
        (panel.value, available[panel.value])
        for panel in settings.order
        if panel not in settings.hidden and panel.value in available
    )


def _strip_source_prefix(value: str) -> str:
    stripped = value.strip()
    for prefix in ("server:", "local-calculation:"):
        if stripped.casefold().startswith(prefix):
            return stripped[len(prefix) :].strip()
    return stripped
