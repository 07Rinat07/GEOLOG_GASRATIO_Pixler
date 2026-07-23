import json

from geoworkbench.domain.acquisition import (
    AcquisitionCurveSchema,
    AcquisitionDataRowPayload,
    AcquisitionDatasetSchema,
    AcquisitionIndexSchema,
    AcquisitionRecord,
    AcquisitionRecordKind,
    AcquisitionSession,
)
from geoworkbench.domain.models import (
    CurveMetadata,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
    Project,
    Well,
)
from geoworkbench.services.acquisition import AcquisitionController
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.project_codec import (
    PROJECT_FORMAT_VERSION,
    ProjectFormatError,
    load_project,
    project_document_from_dict,
)


def make_schema() -> AcquisitionDatasetSchema:
    return AcquisitionDatasetSchema(
        dataset_id="live-dataset",
        name="Live",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        indexes=(
            AcquisitionIndexSchema(
                "depth-index", "DEPT", IndexType.MD, IndexRole.DEPTH, "m"
            ),
        ),
        active_index_id="depth-index",
        curves=(
            AcquisitionCurveSchema(
                CurveMetadata(
                    "gas",
                    "TG",
                    "TG",
                    "%",
                    "Total gas",
                    "live-dataset",
                    "acquisition",
                )
            ),
        ),
    )


def make_project() -> Project:
    well = Well("well-1", "Well 1")
    session = AcquisitionSession("session-1", well.well_id, make_schema())
    controller = AcquisitionController(well, session)
    controller.append(
        AcquisitionRecord(
            "row-1",
            1,
            AcquisitionRecordKind.DATA_ROW,
            AcquisitionDataRowPayload(
                (("depth-index", 100.0),),
                (("gas", 1.5),),
            ),
            "2026-07-23T10:00:00+05:00",
            "fixture",
        )
    )
    controller.close(
        checkpoint_id="checkpoint-final",
        closed_at="2026-07-23T10:01:00+05:00",
    )
    return Project("project-1", "Project", wells={well.well_id: well})


def test_project_v18_round_trip_preserves_acquisition_source_and_checkpoint(tmp_path) -> None:
    target = tmp_path / "acquisition.geolog.json"
    save_project(make_project(), target)

    restored = load_project(target)
    well = restored.wells["well-1"]
    session = well.acquisition_sessions["session-1"]

    assert PROJECT_FORMAT_VERSION == 20
    assert json.loads(target.read_text(encoding="utf-8"))["format_version"] == 20
    assert session.records[0].payload.index_values == (("depth-index", 100.0),)
    assert session.checkpoints[-1].row_count == 1
    assert well.datasets["live-dataset"].depth.tolist() == [100.0]


def test_project_v17_migration_adds_empty_acquisition_sessions() -> None:
    payload = {
        "format_version": 17,
        "project": {
            "project_id": "project-1",
            "name": "Project",
            "wells": {
                "well-1": {
                    "well_id": "well-1",
                    "name": "Well 1",
                    "datasets": {},
                    "operational_events": {},
                }
            },
        },
        "tablet_layouts": {},
        "tablet_presets": {},
        "source_artifacts": {},
        "image_assets": {},
        "import_reports": {},
    }

    document = project_document_from_dict(payload)

    assert document.project.wells["well-1"].acquisition_sessions == {}


def test_codec_rejects_unknown_acquisition_fields(tmp_path) -> None:
    target = tmp_path / "acquisition.geolog.json"
    save_project(make_project(), target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["project"]["wells"]["well-1"]["acquisition_sessions"]["session-1"][
        "unexpected"
    ] = True

    try:
        project_document_from_dict(payload)
    except ProjectFormatError as exc:
        assert "неизвестные поля" in str(exc)
    else:
        raise AssertionError("Unknown acquisition field must be rejected")


def test_codec_rejects_non_contiguous_acquisition_sequence(tmp_path) -> None:
    target = tmp_path / "acquisition.geolog.json"
    save_project(make_project(), target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["project"]["wells"]["well-1"]["acquisition_sessions"]["session-1"][
        "records"
    ][0]["sequence"] = 2

    try:
        project_document_from_dict(payload)
    except ProjectFormatError as exc:
        assert "acquisition session" in str(exc)
    else:
        raise AssertionError("Non-contiguous acquisition sequence must be rejected")


def test_codec_rejects_tampered_acquisition_dataset_projection(tmp_path) -> None:
    target = tmp_path / "acquisition.geolog.json"
    save_project(make_project(), target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["project"]["wells"]["well-1"]["datasets"]["live-dataset"]["curves"][
        "gas"
    ]["values"][0] = 99.0

    try:
        project_document_from_dict(payload)
    except ProjectFormatError as exc:
        assert "persisted projection" in str(exc)
    else:
        raise AssertionError("Tampered acquisition projection must be rejected")


def test_codec_rejects_tampered_acquisition_curve_metadata(tmp_path) -> None:
    target = tmp_path / "acquisition.geolog.json"
    save_project(make_project(), target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["project"]["wells"]["well-1"]["datasets"]["live-dataset"]["curves"][
        "gas"
    ]["metadata"]["unit"] = "ppm"

    try:
        project_document_from_dict(payload)
    except ProjectFormatError as exc:
        assert "persisted projection" in str(exc)
    else:
        raise AssertionError("Tampered acquisition metadata must be rejected")
