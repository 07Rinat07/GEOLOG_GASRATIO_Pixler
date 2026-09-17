from __future__ import annotations

import pytest

from geoworkbench.forms.a4_factory_templates import A4_FACTORY_TEMPLATE_IDS
from geoworkbench.forms.catalog import (
    resolve_form_family_member,
    visible_factory_forms,
)
from geoworkbench.forms.codec import FORM_SCHEMA_VERSION, form_from_dict, form_to_dict
from geoworkbench.forms.models import (
    FormAxisKind,
    FormDocument,
    FormPageOrientation,
)


def test_factory_a4_forms_have_explicit_portrait_landscape_families() -> None:
    forms = visible_factory_forms(None, "ru")

    assert {form.form_id for form in forms} == set(A4_FACTORY_TEMPLATE_IDS)
    families: dict[str, list[FormDocument]] = {}
    for form in forms:
        families.setdefault(form.family_id, []).append(form)

    assert families
    assert all(len(members) == 2 for members in families.values())
    for family_id, members in families.items():
        assert {
            member.preferred_page_orientation for member in members
        } == {
            FormPageOrientation.PORTRAIT,
            FormPageOrientation.LANDSCAPE,
        }
        for orientation in FormPageOrientation:
            resolved = resolve_form_family_member(
                forms,
                family_id=family_id,
                orientation=orientation,
            )
            assert resolved is not None
            assert resolved.family_id == family_id
            assert resolved.preferred_page_orientation is orientation


def test_editable_copy_starts_new_singleton_family() -> None:
    forms = visible_factory_forms(None, "en")
    source = forms[0]
    copy = source.editable_copy(name="Customer form")

    assert copy.family_id == copy.form_id
    assert copy.family_id != source.family_id
    assert (
        resolve_form_family_member(
            forms,
            family_id=copy.family_id,
            orientation=FormPageOrientation.LANDSCAPE,
        )
        is None
    )


def test_form_family_id_round_trips_in_schema_v18() -> None:
    form = FormDocument.create(
        "Customer family member",
        FormAxisKind.DEPTH,
        preferred_page_orientation=FormPageOrientation.LANDSCAPE,
    )
    form.family_id = "customer-family"

    payload = form_to_dict(form)
    restored = form_from_dict(payload)

    assert FORM_SCHEMA_VERSION == 18
    assert payload["family_id"] == "customer-family"
    assert restored.family_id == "customer-family"
    assert restored.preferred_page_orientation is FormPageOrientation.LANDSCAPE


def test_v17_form_migrates_to_safe_singleton_family() -> None:
    form = FormDocument.create("Legacy", FormAxisKind.DEPTH)
    payload = form_to_dict(form)
    payload["schema_version"] = 17
    payload.pop("family_id")

    restored = form_from_dict(payload)

    assert restored.family_id == restored.form_id
    assert form_to_dict(restored)["family_id"] == restored.form_id


def test_family_resolver_returns_none_when_requested_pair_is_missing() -> None:
    form = FormDocument.create("Portrait only", FormAxisKind.DEPTH)
    form.family_id = "customer-family"
    form.preferred_page_orientation = FormPageOrientation.PORTRAIT

    assert (
        resolve_form_family_member(
            (form,),
            family_id="customer-family",
            orientation=FormPageOrientation.LANDSCAPE,
        )
        is None
    )


def test_family_resolver_rejects_duplicate_orientation_members() -> None:
    first = FormDocument.create("First", FormAxisKind.DEPTH)
    second = FormDocument.create("Second", FormAxisKind.DEPTH)
    first.family_id = "ambiguous-family"
    second.family_id = "ambiguous-family"

    with pytest.raises(
        ValueError,
        match="несколько макетов одной ориентации",
    ):
        resolve_form_family_member(
            (first, second),
            family_id="ambiguous-family",
            orientation=FormPageOrientation.PORTRAIT,
        )
