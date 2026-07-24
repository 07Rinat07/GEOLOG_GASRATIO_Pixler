from __future__ import annotations

from geoworkbench.forms.models import FormAxisKind, FormDocument
from geoworkbench.forms.naming import (
    clean_form_name,
    duplicate_form_names,
    normalized_form_name,
)


def test_clean_form_name_preserves_meaning_and_collapses_accidental_spacing() -> None:
    assert clean_form_name("  MASTERLOG   —   ЛБА  ") == "MASTERLOG — ЛБА"
    assert normalized_form_name("  Gas Ratio  ") == "gas ratio"


def test_duplicate_form_names_ignore_case_and_spacing() -> None:
    forms = [
        FormDocument.create("Газовый каротаж", FormAxisKind.DEPTH),
        FormDocument.create("Временной мониторинг", FormAxisKind.TIME),
    ]

    assert duplicate_form_names("  ГАЗОВЫЙ   КАРОТАЖ ", forms) == ("Газовый каротаж",)
    assert duplicate_form_names("Новая форма", forms) == ()


def test_duplicate_check_can_exclude_form_during_future_rename_workflow() -> None:
    form = FormDocument.create("Рабочая форма", FormAxisKind.DEPTH)
    assert duplicate_form_names("рабочая форма", [form], exclude_form_id=form.form_id) == ()
