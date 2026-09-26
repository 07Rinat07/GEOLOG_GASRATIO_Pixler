from __future__ import annotations

import json
from pathlib import Path

import pytest

from geoworkbench.domain.models import Project, Well
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.project_codec import (
    PROJECT_FORMAT_VERSION,
    ProjectFormatError,
    load_project,
    project_document_from_dict,
)


FIELD_ID = "lithology/interval-1/description"


def _project() -> Project:
    well = Well("well-1", "Well 1")
    return Project("project-1", "Project", wells={well.well_id: well})


def test_current_round_trip_preserves_authored_field_source_languages(tmp_path: Path) -> None:
    project = _project()
    project.wells["well-1"].authored_field_source_languages = {
        FIELD_ID: "ru",
        "stratigraphy/interval-2/name": "kk",
    }
    target = tmp_path / "source-languages.geologpkg"

    save_project(project, target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    loaded = load_project(target)

    assert PROJECT_FORMAT_VERSION == 36
    assert payload["format_version"] == 36
    assert payload["project"]["wells"]["well-1"]["authored_field_source_languages"] == {
        FIELD_ID: "ru",
        "stratigraphy/interval-2/name": "kk",
    }
    assert loaded.wells["well-1"].authored_field_source_languages == {
        FIELD_ID: "ru",
        "stratigraphy/interval-2/name": "kk",
    }


def test_v33_loads_without_guessing_source_language(tmp_path: Path) -> None:
    project = _project()
    project.wells["well-1"].authored_field_source_languages = {FIELD_ID: "ru"}
    target = tmp_path / "legacy-v33.geologpkg"
    save_project(project, target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["format_version"] = 33
    payload["project"]["wells"]["well-1"].pop("authored_field_source_languages")

    loaded = project_document_from_dict(payload).project.wells["well-1"]

    assert loaded.authored_field_source_languages == {}


@pytest.mark.parametrize(
    ("source_languages", "message"),
    [
        ({"   ": "ru"}, "ID авторского поля"),
        ({FIELD_ID: "de"}, "Некорректный язык оригинала"),
        ({FIELD_ID: "und"}, "Некорректный язык оригинала"),
    ],
)
def test_v34_rejects_invalid_source_language_metadata(
    tmp_path: Path,
    source_languages: dict[str, str],
    message: str,
) -> None:
    target = tmp_path / "invalid-source-languages.geologpkg"
    save_project(_project(), target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["project"]["wells"]["well-1"]["authored_field_source_languages"] = source_languages

    with pytest.raises(ProjectFormatError, match=message):
        project_document_from_dict(payload)


def test_v34_normalizes_field_id_but_does_not_infer_language(tmp_path: Path) -> None:
    target = tmp_path / "normalized-source-languages.geologpkg"
    save_project(_project(), target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["project"]["wells"]["well-1"]["authored_field_source_languages"] = {
        f"  {FIELD_ID}  ": " EN "
    }

    loaded = project_document_from_dict(payload).project.wells["well-1"]

    assert loaded.authored_field_source_languages == {FIELD_ID: "en"}
