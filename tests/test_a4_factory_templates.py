from geoworkbench.forms.a4_factory_templates import (
    A4_FACTORY_TEMPLATE_IDS,
    a4_factory_templates,
)
from geoworkbench.forms.catalog import HIDDEN_FACTORY_TEMPLATE_IDS, visible_factory_forms
from geoworkbench.forms.models import FormTemplateOrigin
from geoworkbench.forms.templates import factory_templates
from geoworkbench.printing.form_width_advisor import FormWidthLevel, audit_form_width

PORTRAIT_IDS = {
    "factory-masterlog-a4-portrait",
    "factory-technology-a4-portrait",
    "factory-daily-a4-portrait",
    "factory-complex-gas-a4-portrait",
}
LANDSCAPE_IDS = set(A4_FACTORY_TEMPLATE_IDS) - PORTRAIT_IDS


def test_visible_factory_catalog_contains_only_new_a4_pairs() -> None:
    forms = a4_factory_templates("ru")

    assert tuple(forms) == A4_FACTORY_TEMPLATE_IDS
    assert set(forms) == PORTRAIT_IDS | LANDSCAPE_IDS
    assert set(forms).isdisjoint(HIDDEN_FACTORY_TEMPLATE_IDS)
    assert tuple(form.form_id for form in visible_factory_forms(None, "ru")) == (
        A4_FACTORY_TEMPLATE_IDS
    )


def test_every_a4_factory_fits_its_named_orientation_without_hidden_scaling() -> None:
    for form_id, form in a4_factory_templates("ru").items():
        audit = audit_form_width(column.width for column in form.columns if column.visible)
        assert form.read_only is True
        assert form.origin is FormTemplateOrigin.FACTORY
        if form_id in PORTRAIT_IDS:
            assert audit.level is FormWidthLevel.FITS_PORTRAIT
            assert audit.total_width_px <= audit.portrait_capacity_px
            assert form.print_header_template_id == form.print_header_template_ids["portrait"]
        else:
            assert audit.level in {
                FormWidthLevel.FITS_PORTRAIT,
                FormWidthLevel.FITS_LANDSCAPE,
            }
            assert audit.total_width_px <= audit.landscape_capacity_px
            assert form.print_header_template_id == form.print_header_template_ids["landscape"]


def test_complex_gas_factory_contains_all_requested_gas_groups() -> None:
    form = a4_factory_templates("ru")["factory-complex-gas-a4-landscape"]
    graph_columns = form.columns[1::2]
    canonical_ids = {
        binding.canonical_parameter_id
        for column in form.columns
        for track in column.tracks
        for binding in track.bindings
    }

    assert len(form.columns) == 10
    assert all(
        form.columns[index].tracks[0].kind.value == "depth"
        and form.columns[index + 1].tracks[0].kind.value == "curve"
        for index in range(0, len(form.columns), 2)
    )
    assert [column.title for column in graph_columns] == [
        "Абсолютные компоненты",
        "Нормализованные компоненты",
        "Относительный газ",
        "Wetness, Balance, Character и изомеры",
        "Коэффициенты Pixler",
    ]
    assert {
        "TG_CALC",
        "C1",
        "C2",
        "C3",
        "IC4",
        "NC4",
        "IC5",
        "NC5",
        "TG_NORM",
        "C1_NORM_REF",
        "C2_NORM",
        "C3_NORM",
        "IC4_NORM",
        "NC4_NORM",
        "IC5_NORM",
        "NC5_NORM",
        "C1_REL",
        "C2_REL",
        "C3_REL",
        "IC4_REL",
        "NC4_REL",
        "IC5_REL",
        "NC5_REL",
        "WETNESS",
        "BALANCE",
        "CHARACTER",
        "IC4_NC4",
        "IC5_NC5",
        "PIXLER_C1_C2",
        "PIXLER_C1_C3",
        "PIXLER_C1_C4",
        "PIXLER_C1_C5",
    } <= canonical_ids

def test_legacy_forms_remain_resolvable_but_are_hidden() -> None:
    all_templates = factory_templates("ru")
    assert HIDDEN_FACTORY_TEMPLATE_IDS <= set(all_templates)
    assert "factory-gas-ratio-pixler-depth" in all_templates
    assert "factory-masterlog-geological-geochemical" in all_templates
