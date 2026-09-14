from __future__ import annotations

import json

import pytest

from geoworkbench.domain.models import (
    CuttingsSample,
    DescriptionTemplateBlock,
    Project,
    Well,
)
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.project_codec import (
    PROJECT_FORMAT_VERSION,
    ProjectFormatError,
    load_project,
    project_from_dict,
)


def _project() -> Project:
    sample = CuttingsSample(
        "sample-1",
        100.0,
        101.0,
        description_template_blocks=[
            DescriptionTemplateBlock(
                "block-1",
                "sandstone",
                3,
                {"ru": "Песчаник", "kk": "Құмтас", "en": "Sandstone"},
            )
        ],
    )
    well = Well("well-1", "Well", cuttings=[sample])
    return Project("project-1", "Project", wells={well.well_id: well})


def test_v30_round_trip_preserves_template_snapshot(tmp_path) -> None:
    target = tmp_path / "project.geolog.json"
    save_project(_project(), target)

    loaded = load_project(target)
    block = loaded.wells["well-1"].cuttings[0].description_template_blocks[0]

    assert PROJECT_FORMAT_VERSION == 31
    assert block.template_id == "sandstone"
    assert block.template_version == 3
    assert block.text_i18n["en"] == "Sandstone"


def test_bare_project_decoder_uses_current_template_block_schema() -> None:
    from dataclasses import asdict

    loaded = project_from_dict(asdict(_project()))

    assert loaded.wells["well-1"].cuttings[0].description_template_blocks[0].block_id == "block-1"


def test_v29_project_migrates_with_empty_template_history(tmp_path) -> None:
    target = tmp_path / "legacy.geolog.json"
    project = _project()
    project.wells["well-1"].cuttings[0].description_template_blocks.clear()
    save_project(project, target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["format_version"] = 29
    payload["project"]["wells"]["well-1"]["cuttings"][0].pop("description_template_blocks")
    target.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_project(target)

    assert loaded.wells["well-1"].cuttings[0].description_template_blocks == []


def test_v30_rejects_incomplete_template_snapshot(tmp_path) -> None:
    target = tmp_path / "broken.geolog.json"
    save_project(_project(), target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    block = payload["project"]["wells"]["well-1"]["cuttings"][0]["description_template_blocks"][0]
    block["text_i18n"].pop("kk")
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProjectFormatError, match="RU/KK/EN"):
        load_project(target)
