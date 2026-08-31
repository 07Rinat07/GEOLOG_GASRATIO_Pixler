from __future__ import annotations

import json
from pathlib import Path

from geoworkbench.catalogs.description_templates import load_rock_description_templates


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/geoworkbench/resources/rock_description_templates.json"


def test_factory_rock_description_catalog_contains_all_source_templates() -> None:
    catalog = load_rock_description_templates()

    assert len(catalog.templates) == 19
    assert {template.template_id for template in catalog.templates} == {
        "clay",
        "argillite",
        "siltstone",
        "sand",
        "sandstone",
        "gravelstone",
        "pebble_gravel",
        "coal",
        "marl",
        "argillaceous_limestone",
        "limestone",
        "dolomite",
        "gypsum",
        "anhydrite",
        "halite",
        "schist",
        "gneiss",
        "quartzite",
        "marble",
    }


def test_every_factory_template_has_complete_ru_kk_en_content() -> None:
    catalog = load_rock_description_templates()

    for template in catalog.templates:
        for language in ("ru", "kk", "en"):
            name, text = template.localized(language)
            assert name
            assert text.startswith(name) or template.template_id in {
                "argillaceous_limestone",
                "gneiss",
            }
            assert "[X%]" in text


def test_catalog_guidance_is_available_in_all_languages() -> None:
    catalog = load_rock_description_templates()

    for language in ("ru", "kk", "en"):
        formula, warning = catalog.localized_guidance(language)
        assert "[X%]" in formula
        assert "LCM/NUT PLUG" in warning
        assert "drilling contamination / additives" in warning


def test_catalog_resource_is_valid_json() -> None:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    assert len(payload["templates"]) == 19
