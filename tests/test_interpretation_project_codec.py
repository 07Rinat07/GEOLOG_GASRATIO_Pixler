from geoworkbench.domain.models import (
    InterpretationInterval,
    Project,
    Well,
    WellInterpretation,
)
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.project_codec import load_project_document


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
    )
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
