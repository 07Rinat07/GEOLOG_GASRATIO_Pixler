from __future__ import annotations

from dataclasses import replace

from geoworkbench.domain.models import Dataset
from geoworkbench.forms.a4_factory_templates import (
    A4_FACTORY_TEMPLATE_IDS,
    a4_factory_templates,
)
from geoworkbench.forms.models import FormDocument, FormPageOrientation
from geoworkbench.forms.repository import FormRepository
from geoworkbench.tablet.models import COMPACT_TRACK_KINDS, TrackKind, XScale

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

_MASTERLOG_WIDTHS = {
    "portrait": {
        "stratigraphy": 48,
        "lithology": 48,
        "drilling": 100,
        "gas": 100,
        "interpretation": 194,
    },
    "landscape": {
        "stratigraphy": 48,
        "lithology": 48,
        "drilling": 200,
        "gas": 220,
        "interpretation": 249,
    },
}


def visible_factory_forms(
    dataset: Dataset | None,
    language: str = "ru",
) -> tuple[FormDocument, ...]:
    """Return only production-ready A4 portrait/landscape factory forms."""

    del dataset  # Canonical A4 forms are intentionally stable across datasets.
    forms = a4_factory_templates(language)
    for form_id, form in forms.items():
        orientation = "landscape" if form_id.endswith("-landscape") else "portrait"
        form.preferred_page_orientation = FormPageOrientation(orientation)
        _apply_factory_presentation_defaults(form_id, form, orientation)
        form.validate()
    return tuple(forms[form_id] for form_id in A4_FACTORY_TEMPLATE_IDS)


def _apply_factory_presentation_defaults(
    form_id: str,
    form: FormDocument,
    orientation: str,
) -> None:
    """Apply one presentation policy after canonical factory construction.

    The source templates remain semantically stable while production forms get
    customer-facing defaults requested for screen/PDF consistency.
    """

    for column in form.columns:
        for track in column.tracks:
            if track.kind in COMPACT_TRACK_KINDS:
                column.title_orientation = "vertical_top_to_bottom"
                track.title_orientation = "vertical_top_to_bottom"
            if track.kind is TrackKind.LBA:
                track.lba_label_orientation = "vertical_top_to_bottom"
            if track.kind is TrackKind.CALCIMETRY:
                track.calcimetry_label_orientation = "vertical_top_to_bottom"

    if form_id.startswith("factory-masterlog-a4-"):
        widths = _MASTERLOG_WIDTHS[orientation]
        for column in form.columns:
            for key, width in widths.items():
                if column.column_id.endswith(f"-{key}"):
                    column.width = width
                    break
            if column.column_id.endswith("-interpretation"):
                for track in column.tracks:
                    track.show_description_borders = False

    if form_id.startswith("factory-complex-gas-a4-"):
        _configure_integrated_components(form)


def _configure_integrated_components(form: FormDocument) -> None:
    """Use linear per-component auto-range with quiet default presentation."""

    for column in form.columns:
        if column.column_id == "column-complex-depth-absolute":
            # Keep the depth column in the editable factory document so it can
            # be enabled manually, but do not display it by default.
            column.visible = False
            continue
        if column.column_id != "column-complex-absolute":
            continue
        for track in column.tracks:
            track.x_axis_label = ""
            track.grid_x = False
            track.bindings = [
                replace(
                    binding,
                    x_scale=XScale.LINEAR,
                    x_min=None,
                    x_max=None,
                )
                for binding in track.bindings
            ]


def complete_form_catalog(
    repository: FormRepository,
    dataset: Dataset | None,
    language: str = "ru",
) -> tuple[FormDocument, ...]:
    """Return the one authoritative catalog for browse/create/save workflows."""

    return (*visible_factory_forms(dataset, language), *repository.list_forms())
