from __future__ import annotations

import json

import pytest

from geoworkbench.forms.models import FormTemplateOrigin
from geoworkbench.forms.repository import FormRepository


@pytest.mark.parametrize(
    ("legacy_name", "polished_name"),
    [
        (
            "GEO_TECH_GAS_A4_albom",
            "Геология, технология и газ — A4, альбомная",
        ),
        (
            "Geo_Tech_Gas_Logging_form A4 albom",
            "Геолого-технологический газовый каротаж — A4, альбомная",
        ),
        ("Геология_plus_под A4 книжная", "Геология Plus — A4, книжная"),
        ("Форма Мастерлога под A4 книга", "Мастерлог — A4, книжная"),
    ],
)
def test_confirmed_local_forms_are_promoted_and_renamed_atomically(
    tmp_path, legacy_name: str, polished_name: str
) -> None:
    root = tmp_path / "forms"
    legacy_path = root / "depth" / "ready-source.json"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text(
        json.dumps(
            {
                "schema_version": 7,
                "form_id": "ready-source",
                "name": legacy_name,
                "description": "",
                "axis_kind": "depth",
                "origin": "user",
                "read_only": False,
                "columns": [
                    {
                        "column_id": "depth-column",
                        "title": "Глубина",
                        "width": 120,
                        "tracks": [
                            {
                                "track_id": "depth-track",
                                "title": "Глубина",
                                "kind": "depth",
                            }
                        ],
                    },
                    {
                        "column_id": "curve-column",
                        "title": "Газ",
                        "width": 300,
                        "tracks": [
                            {
                                "track_id": "curve-track",
                                "title": "Газ",
                                "kind": "curve",
                            }
                        ],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    repository = FormRepository(root)
    forms = repository.list_forms()

    assert len(forms) == 1
    form = forms[0]
    assert form.name == polished_name
    assert form.read_only is True
    assert form.origin is FormTemplateOrigin.FACTORY
    assert form.revision == 2
    assert form.columns[0].width == 60
    assert form.columns[1].width == 300
    assert repository.upgraded_ready_names == (polished_name,)

    ready_path = root / "ready" / "ready-source.json"
    assert ready_path.exists()
    assert not legacy_path.exists()
    payload = json.loads(ready_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 11
    assert payload["name"] == polished_name
    assert payload["read_only"] is True
    assert payload["origin"] == "factory"
    assert payload["columns"][0]["width"] == 60
    assert payload["columns"][0]["tracks"][0]["title_orientation"] == "vertical_bottom_to_top"

    # A second process/startup sees the same protected template and does not
    # increment the revision or reduce the width again.
    second = FormRepository(root).list_forms()[0]
    assert second.revision == 2
    assert second.columns[0].width == 60


def test_unrelated_user_form_keeps_its_name_and_editable_status(tmp_path) -> None:
    root = tmp_path / "forms"
    source = root / "legacy.json"
    root.mkdir(parents=True)
    source.write_text(
        json.dumps(
            {
                "schema_version": 7,
                "form_id": "ordinary",
                "name": "Моя форма скважины 42",
                "axis_kind": "depth",
                "columns": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    form = FormRepository(root).list_forms()[0]

    assert form.name == "Моя форма скважины 42"
    assert form.read_only is False
    assert (root / "depth" / "ordinary.json").exists()
    assert not source.exists()
