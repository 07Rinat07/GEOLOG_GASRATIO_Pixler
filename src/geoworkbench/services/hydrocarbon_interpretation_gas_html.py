from __future__ import annotations

from html import escape

from geoworkbench.domain.models import Dataset
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
    fluid_hypothesis_basis,
)
from geoworkbench.services.interval_gas_statistics import (
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
    """Add explicit gas readings to each existing candidate-interval basis cell."""

    if dataset.dataset_id != report.dataset_id or not report.candidates:
        return html
    enriched = html
    for candidate in report.candidates:
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
    return enriched


__all__ = ["inject_interval_gas_statistics_html"]
