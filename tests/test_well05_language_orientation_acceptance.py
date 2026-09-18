from __future__ import annotations

import re

import pytest

from geoworkbench.forms.a4_factory_templates import a4_factory_templates
from geoworkbench.printing.header_catalog import factory_header_preset
from geoworkbench.services.localization import AppLanguage


@pytest.mark.parametrize("language", ("ru", "kk", "en"))
@pytest.mark.parametrize("orientation", ("portrait", "landscape"))
def test_well05_a4_family_header_contract_covers_six_language_orientation_modes(
    language: str,
    orientation: str,
) -> None:
    forms = a4_factory_templates(language)
    canonical = a4_factory_templates("ru")

    selected = [
        form
        for form in forms.values()
        if form.preferred_page_orientation.value == orientation
    ]
    assert selected

    for form in selected:
        canonical_form = canonical[form.form_id]
        assert form.family_id == canonical_form.family_id
        assert form.family_id
        assert form.print_header_template_id == form.print_header_template_ids[orientation]

        paired_id = form.print_header_template_ids[orientation]
        preset = factory_header_preset(paired_id)
        assert preset.preferred_orientation == orientation
        assert preset.name(AppLanguage(language)).strip()
        assert preset.description(AppLanguage(language)).strip()


@pytest.mark.parametrize("language", (AppLanguage.RU, AppLanguage.KK, AppLanguage.EN))
@pytest.mark.parametrize("orientation", ("portrait", "landscape"))
def test_well05_curated_a4_header_labels_are_complete_and_wrappable(
    language: AppLanguage,
    orientation: str,
) -> None:
    form = a4_factory_templates(language.value)[f"factory-technology-a4-{orientation}"]
    preset = factory_header_preset(form.print_header_template_ids[orientation])

    localized_key = {
        AppLanguage.RU: "text_ru",
        AppLanguage.KK: "text_kk",
        AppLanguage.EN: "text_en",
    }[language]
    labels = [
        element
        for element in preset.elements
        if element.element_type == "text"
        and element.element_id.endswith("_label")
    ]

    assert labels
    localized_texts = [str(element.properties.get(localized_key, "")).strip() for element in labels]
    assert all(localized_texts)
    assert all(element.properties.get("word_wrap") is True for element in labels)

    if language is AppLanguage.KK:
        assert "ТАПСЫРЫС БЕРУШІ" in localized_texts
        assert "БҰРҒЫЛАУ ҚОНДЫРҒЫСЫ" in localized_texts
    if language is AppLanguage.EN:
        assert not any(re.search(r"[А-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі]", text) for text in localized_texts)


def test_well05_portrait_landscape_members_share_family_in_every_language() -> None:
    for language in ("ru", "kk", "en"):
        forms = a4_factory_templates(language)
        families: dict[str, set[str]] = {}
        for form in forms.values():
            families.setdefault(form.family_id, set()).add(
                form.preferred_page_orientation.value
            )

        assert families
        assert all(members == {"portrait", "landscape"} for members in families.values())
