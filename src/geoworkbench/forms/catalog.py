from __future__ import annotations

from collections.abc import Sequence

from geoworkbench.domain.models import Dataset
from geoworkbench.forms.materialize import materialized_factory_templates
from geoworkbench.forms.models import FormDocument
from geoworkbench.forms.repository import FormRepository
from geoworkbench.forms.templates import (
    CURATED_FACTORY_TEMPLATE_IDS,
    curated_factory_templates,
)

# Legacy presets are retained in ``factory_templates`` for old projects and JSON
# imports, but only the compact production catalog is shown in create/save/print
# workflows.
HIDDEN_FACTORY_TEMPLATE_IDS: frozenset[str] = frozenset(
    {
        "factory-depth-basic",
        "factory-time-basic",
        "factory-gas-components",
        "factory-gas-ratio",
        "factory-pixler",
        "factory-interpretation",
        "factory-normalized-gas-qc",
        "factory-c1-c5-detailed",
        "factory-d-exponent",
        "factory-calcimetry",
        "factory-lba",
        "factory-geotech-integrated",
        "factory-masterlog-geological-geochemical",
    }
)


def visible_factory_forms(
    dataset: Dataset | None,
    language: str = "ru",
) -> tuple[FormDocument, ...]:
    """Return the compact visible factory catalog used by every form dialog.

    Materialized forms are preferred when a dataset is available because their
    bindings and details can reflect the active LAS. Legacy factory IDs remain
    resolvable outside this visible catalog so saved projects keep opening.
    """

    try:
        materialized = materialized_factory_templates(dataset, language)
        forms: Sequence[FormDocument] = tuple(
            materialized[form_id] for form_id in CURATED_FACTORY_TEMPLATE_IDS
        )
    except (KeyError, RuntimeError, ValueError):
        forms = tuple(curated_factory_templates(language).values())
    return tuple(forms)


def complete_form_catalog(
    repository: FormRepository,
    dataset: Dataset | None,
    language: str = "ru",
) -> tuple[FormDocument, ...]:
    """Return the one authoritative catalog for browse/create/save workflows."""

    return (*visible_factory_forms(dataset, language), *repository.list_forms())
