from __future__ import annotations

from geoworkbench.domain.models import Dataset
from geoworkbench.forms.a4_factory_templates import (
    A4_FACTORY_TEMPLATE_IDS,
    a4_factory_templates,
)
from geoworkbench.forms.models import FormDocument, FormPageOrientation
from geoworkbench.forms.repository import FormRepository

# Legacy factory IDs remain resolvable through ``factory_templates`` for old
# projects and JSON imports, but are no longer displayed in form workflows.
# The gas-mixture ramp remains available because it is an interpretation report,
# not a factory form template.
HIDDEN_FACTORY_TEMPLATE_IDS: frozenset[str] = frozenset(
    {
        "factory-depth-basic",
        "factory-time-basic",
        "factory-gas-components",
        "factory-gas-ratio",
        "factory-pixler",
        "factory-interpretation",
        "factory-gas-ratio-pixler-depth",
        "factory-gas-ratio-pixler-time",
        "factory-normalized-gas-qc",
        "factory-c1-c5-detailed",
        "factory-d-exponent",
        "factory-drilling-technology",
        "factory-lithology-cuttings",
        "factory-calcimetry",
        "factory-lba",
        "factory-geotech-integrated",
        "factory-geodata-depth-workspace",
        "factory-engineering-control-time",
        "factory-masterlog-geological-geochemical",
    }
)


def visible_factory_forms(
    dataset: Dataset | None,
    language: str = "ru",
) -> tuple[FormDocument, ...]:
    """Return only production-ready A4 portrait/landscape factory forms."""

    del dataset  # Canonical A4 forms are intentionally stable across datasets.
    forms = a4_factory_templates(language)
    for form_id, form in forms.items():
        form.preferred_page_orientation = (
            FormPageOrientation.LANDSCAPE
            if form_id.endswith("-landscape")
            else FormPageOrientation.PORTRAIT
        )
    return tuple(forms[form_id] for form_id in A4_FACTORY_TEMPLATE_IDS)


def complete_form_catalog(
    repository: FormRepository,
    dataset: Dataset | None,
    language: str = "ru",
) -> tuple[FormDocument, ...]:
    """Return the one authoritative catalog for browse/create/save workflows."""

    return (*visible_factory_forms(dataset, language), *repository.list_forms())
