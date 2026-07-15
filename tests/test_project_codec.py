import json

import numpy as np
import pytest

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
    Project,
    ProjectLithotype,
    Well,
)
from geoworkbench.data.lossless_las import parse_lossless_las
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.project_codec import (
    PROJECT_FORMAT_VERSION,
    ProjectFormatError,
    load_project,
    load_project_document,
    project_document_from_dict,
)
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind


def make_project() -> Project:
    dataset = Dataset(
        dataset_id="dataset-1",
        name="Test LAS",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.array([100.0, 101.0]),
    )
    dataset.curves["curve-1"] = CurveData(
        metadata=CurveMetadata(
            curve_id="curve-1",
            original_mnemonic="C1",
            canonical_mnemonic="C1",
            unit="%",
            description="Methane",
            source_dataset_id=dataset.dataset_id,
        ),
        values=np.array([1.0, 2.0]),
    )
    well = Well("well-1", "Well 1", datasets={dataset.dataset_id: dataset})
    return Project("project-1", "Test project", wells={well.well_id: well})


def test_project_document_round_trip_preserves_layout(tmp_path) -> None:
    target = tmp_path / "test.geolog.json"
    layout = TabletLayout(
        [TrackDefinition("gas", "Газ", TrackKind.GAS, ["C1"], width=420, visible=False)]
    )
    project = make_project()
    project.lithotypes["oil_sand"] = ProjectLithotype(
        "oil_sand", "OS", "Нефтенасыщенный песок", "Oil sand", "sedimentary", "#a07840", "dots"
    )
    project.description_templates["Песчаник"] = "Песчаник серый, мелкозернистый"

    save_project(project, target, tablet_layouts={"dataset-1": layout})
    document = load_project_document(target)

    assert document.project.name == "Test project"
    assert document.tablet_layouts["dataset-1"] == layout
    assert document.project.lithotypes["oil_sand"].code == "OS"
    assert document.project.description_templates["Песчаник"].startswith("Песчаник")
    assert json.loads(target.read_text(encoding="utf-8"))["format_version"] == (
        PROJECT_FORMAT_VERSION
    )


def test_project_document_round_trip_preserves_lossless_source(tmp_path) -> None:
    target = tmp_path / "test.geolog.json"
    source = parse_lossless_las(b"~V\r\nVERS. 2.0\r\n~A\r\n100 1\r\n")

    save_project(make_project(), target, source_documents={"dataset-1": source})
    document = load_project_document(target)

    assert document.source_documents["dataset-1"].to_bytes() == source.to_bytes()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["source_artifacts"]["dataset-1"]["sha256"] == source.sha256
    assert "raw_bytes" not in target.read_text(encoding="utf-8")


def test_load_project_keeps_project_only_api_compatible(tmp_path) -> None:
    target = tmp_path / "test.geolog.json"
    save_project(make_project(), target)

    assert load_project(target).project_id == "project-1"


def test_unversioned_project_is_loaded_as_legacy_document() -> None:
    legacy = {
        "project_id": "legacy",
        "name": "Legacy",
        "wells": {},
    }

    document = project_document_from_dict(legacy)

    assert document.project.project_id == "legacy"
    assert document.tablet_layouts == {}


def test_v1_project_is_migrated_to_current_document() -> None:
    document = project_document_from_dict(
        {
            "format_version": 1,
            "project": {"project_id": "p", "name": "P", "wells": {}},
        }
    )

    assert document.project.project_id == "p"
    assert document.tablet_layouts == {}
    assert document.source_documents == {}


def test_v4_project_is_migrated_with_empty_source_artifacts() -> None:
    document = project_document_from_dict(
        {
            "format_version": 4,
            "project": {
                "project_id": "p",
                "name": "P",
                "wells": {},
                "lithotypes": {},
                "description_templates": {},
            },
            "tablet_layouts": {},
        }
    )

    assert document.project.project_id == "p"
    assert document.source_documents == {}


@pytest.mark.parametrize("version", [99, "2", True, -1])
def test_project_document_rejects_unsupported_version(version: object) -> None:
    with pytest.raises(ProjectFormatError):
        project_document_from_dict(
            {
                "format_version": version,
                "project": {"project_id": "p", "name": "P", "wells": {}},
                "tablet_layouts": {},
            }
        )


def test_project_document_rejects_layout_for_unknown_dataset() -> None:
    with pytest.raises(ProjectFormatError, match="неизвестный набор"):
        project_document_from_dict(
            {
                "format_version": PROJECT_FORMAT_VERSION,
                "project": {"project_id": "p", "name": "P", "wells": {}},
                "tablet_layouts": {"missing": {"version": 1, "tracks": []}},
            }
        )


def test_load_project_wraps_invalid_domain_data(tmp_path) -> None:
    target = tmp_path / "invalid.geolog.json"
    target.write_text(
        json.dumps(
            {
                "format_version": PROJECT_FORMAT_VERSION,
                "project": {
                    "project_id": "p",
                    "name": "P",
                    "wells": {
                        "w": {
                            "well_id": "w",
                            "name": "W",
                            "datasets": {
                                "d": {
                                    "dataset_id": "d",
                                    "name": "D",
                                    "kind": "gti",
                                    "depth_domain": "md",
                                    "depth": ["not-a-number"],
                                    "curves": {},
                                }
                            },
                        }
                    },
                },
                "tablet_layouts": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ProjectFormatError, match="некорректные данные"):
        load_project_document(target)
