from __future__ import annotations

from collections.abc import Sequence

from geoworkbench.domain.models import Dataset
from geoworkbench.forms.materialize import materialized_factory_templates
from geoworkbench.forms.models import FormDocument
from geoworkbench.forms.repository import FormRepository
from geoworkbench.forms.templates import factory_templates

# This preset is retained for backward compatibility with projects that refer to
# its stable ID, but it is intentionally not exposed as a separate library item:
# the user's ready Masterlog-derived forms already cover this workflow and a
# second visible MASTERLOG entry would be a confusing duplicate.
HIDDEN_FACTORY_TEMPLATE_IDS: frozenset[str] = frozenset(
    {"factory-masterlog-geological-geochemical"}
)


def visible_factory_forms(
    dataset: Dataset | None,
    language: str = "ru",
) -> tuple[FormDocument, ...]:
    """Return the complete visible factory catalog used by every form dialog.

    Materialized forms are preferred when a dataset is available because their
    bindings and details can reflect the active LAS. A stable static catalog is
    used as a fallback. Keeping this logic in one function prevents the Form
    Library and the Save User Form dialog from showing different template sets.
    """

    try:
        forms: Sequence[FormDocument] = tuple(
            materialized_factory_templates(dataset, language).values()
        )
    except (KeyError, RuntimeError, ValueError):
        forms = tuple(factory_templates(language).values())
    return tuple(
        form for form in forms if form.form_id not in HIDDEN_FACTORY_TEMPLATE_IDS
    )


def complete_form_catalog(
    repository: FormRepository,
    dataset: Dataset | None,
    language: str = "ru",
) -> tuple[FormDocument, ...]:
    """Return the one authoritative catalog for browse/create/save workflows."""

    return (*visible_factory_forms(dataset, language), *repository.list_forms())
