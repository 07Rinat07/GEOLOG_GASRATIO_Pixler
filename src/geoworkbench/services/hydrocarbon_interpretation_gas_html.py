from __future__ import annotations

from html import escape
import re

from geoworkbench.domain.models import Dataset
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
    fluid_hypothesis_basis,
)
from geoworkbench.services.interval_gas_statistics import (
    absolute_gas_components_summary,
    build_candidate_interval_statistics,
    enhanced_fluid_hypothesis_basis,
)
from geoworkbench.services.localization import AppLanguage


def inject_interval_gas_statistics_html(
    html: str,
    report: HydrocarbonInterpretationReport,
    dataset: Dataset,
    language: AppLanguage = AppLanguage.RU,
) -> str:
    """Add interval min/mean/max gas statistics to the standard report HTML."""

    if dataset.dataset_id != report.dataset_id or not report.candidates:
        return html
    enriched = html
    for index, candidate in enumerate(report.candidates):
        statistics = build_candidate_interval_statistics(dataset, candidate)
        old_basis = fluid_hypothesis_basis(candidate, language)
        new_basis = enhanced_fluid_hypothesis_basis(
            old_basis,
            candidate,
            statistics,
            language,
        )
        enriched = enriched.replace(
            f"<p>{escape(old_basis)}</p>",
            f"<p>{escape(new_basis)}</p>",
            1,
        )
        component_text = absolute_gas_components_summary(
            statistics.components,
            language,
        )
        component_html = re.sub(
            r"; (?=(?:I|N)?C[1-5](?: \[|:))",
            "<br>",
            escape(component_text),
        )
        enriched = enriched.replace(
            f"<td data-absolute-gas='{index}'>—</td>",
            f"<td data-absolute-gas='{index}'>{component_html}</td>",
            1,
        )
    return enriched


__all__ = ["inject_interval_gas_statistics_html"]
