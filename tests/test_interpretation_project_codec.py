import json

import pytest

from geoworkbench.domain.models import (
    InterpretationInterval,
    Project,
    Well,
    WellInterpretation,
)
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.project_codec import ProjectFormatError, load_project_document


def test_project_round_trip_preserves_well_interpretations(tmp_path) -> None:
    interpretation = WellInterpretation(
        "interpretation-1",
        "Primary",
        "Main interpretation",
        [
            InterpretationInterval(
                "interval-1",
                100.0,
                120.0,
                "Reservoir",
                "Sand A",
                "#fde68a",
                "Gas response",
            )
        ],
        name_i18n={"ru": "Основная", "kk": "Негізгі", "en": "Primary"},
        description_i18n={"ru": "Описание", "kk": "Сипаттама", "en": "Description"},
    )
    interpretation.intervals[0].label_i18n = {
        "ru": "Пласт А",
        "kk": "А қабаты",
        "en": "Sand A",
    }
    interpretation.intervals[0].comment_i18n = {
        "ru": "Газопоказания",
        "kk": "Газ белгісі",
        "en": "Gas response",
    }
    well = Well(
        "well-1",
        "Well 1",
        interpretations={interpretation.interpretation_id: interpretation},
    )
    project = Project("project-1", "Project", wells={well.well_id: well})
    target = tmp_path / "interpretations.geolog.json"

    save_project(project, target)
    loaded = load_project_document(target)

    restored = loaded.project.wells["well-1"].interpretations["interpretation-1"]
    assert restored.name == "Primary"
    assert restored.description == "Main interpretation"
    assert restored.intervals[0].label == "Sand A"
    assert restored.intervals[0].color == "#fde68a"
    assert restored.name_i18n["kk"] == "Негізгі"
    assert restored.description_i18n["en"] == "Description"
    assert restored.intervals[0].label_i18n["ru"] == "Пласт А"
    assert restored.intervals[0].comment_i18n["kk"] == "Газ белгісі"


def test_project_v31_rejects_unknown_interpretation_language(tmp_path) -> None:
    project = Project(
        "project-1",
        "Project",
        wells={
            "well-1": Well(
                "well-1",
                "Well 1",
                interpretations={
                    "interpretation-1": WellInterpretation("interpretation-1", "Primary")
                },
            )
        },
    )
    target = tmp_path / "invalid-language.geolog.json"
    save_project(project, target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["project"]["wells"]["well-1"]["interpretations"]["interpretation-1"]["name_i18n"] = {
        "invalid": "Broken"
    }
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProjectFormatError, match="локализованное поле"):
        load_project_document(target)
