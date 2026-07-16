import json
from pathlib import Path

import numpy as np
import pytest

from geoworkbench.domain.models import (
    CanvasObject,
    CurveData,
    CurveMetadata,
    CustomFormulaDefinition,
    ExportProfile,
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
    MasterlogColumnTemplate,
    MasterlogHeaderElement,
    MasterlogTemplate,
    Project,
    ProjectLithotype,
    Well,
)
from geoworkbench.data.lossless_las import parse_lossless_las
from geoworkbench.data.las_import_report import (
    LasImportIssue,
    LasImportReport,
    LasIssueSeverity,
    LasSourceSnapshot,
)
from geoworkbench.services.depth_axis import DepthAxisReport, DepthDirection
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


def make_import_report(raw: bytes) -> LasImportReport:
    source = parse_lossless_las(raw)
    return LasImportReport(
        LasSourceSnapshot(
            path=Path("source.las"),
            size_bytes=source.size_bytes,
            sha256=source.sha256,
            encoding=source.encoding,
            newline_style=source.newline_style.value,
            section_names=tuple(section.name for section in source.sections),
            las_version="2.0",
            wrap="NO",
            null_value=-999.25,
        ),
        DepthAxisReport(DepthDirection.ASCENDING, 100.0, 101.0, 1.0, True, 0, 0, 0),
        (LasImportIssue("test", LasIssueSeverity.WARNING, "Test warning"),),
    )


def test_project_document_round_trip_preserves_layout(tmp_path) -> None:
    target = tmp_path / "test.geolog.json"
    layout = TabletLayout(
        [TrackDefinition("gas", "Газ", TrackKind.GAS, ["C1"], width=420, visible=False)]
    )
    project = make_project()
    project.wells["well-1"].datasets["dataset-1"].version_headers = {
        "VERS": "2.0",
        "WRAP": "NO",
        "DLM": "SPACE",
    }
    project.lithotypes["oil_sand"] = ProjectLithotype(
        "oil_sand", "OS", "Нефтенасыщенный песок", "Oil sand", "sedimentary", "#a07840", "dots"
    )
    project.description_templates["Песчаник"] = "Песчаник серый, мелкозернистый"
    project.custom_formulas["wetness"] = CustomFormulaDefinition(
        "wetness", "Wetness", "100 * (C2 + C3) / (C1 + C2 + C3)", "WH_USER", "%"
    )
    project.export_profiles["gas-profile"] = ExportProfile(
        "gas-profile", "Gas profile", ("C1", "C2")
    )

    preset = TabletLayout(
        [TrackDefinition("preset-depth", "Depth", TrackKind.DEPTH, width=150)]
    )
    save_project(
        project,
        target,
        tablet_layouts={"dataset-1": layout},
        tablet_presets={"Standard": preset},
    )
    document = load_project_document(target)

    assert document.project.name == "Test project"
    assert document.tablet_layouts["dataset-1"] == layout
    assert document.tablet_presets["Standard"] == preset
    assert document.project.lithotypes["oil_sand"].code == "OS"
    assert document.project.description_templates["Песчаник"].startswith("Песчаник")
    assert document.project.custom_formulas["wetness"].output_mnemonic == "WH_USER"
    assert document.project.export_profiles["gas-profile"].curve_mnemonics == (
        "C1",
        "C2",
    )
    assert document.project.wells["well-1"].datasets["dataset-1"].version_headers["DLM"] == "SPACE"
    assert json.loads(target.read_text(encoding="utf-8"))["format_version"] == (
        PROJECT_FORMAT_VERSION
    )


def test_project_round_trip_preserves_masterlog_template_and_anchors(tmp_path) -> None:
    target = tmp_path / "masterlog.geolog.json"
    project = make_project()
    project.masterlog_templates["standard"] = MasterlogTemplate(
        template_id="standard",
        name="Standard Masterlog",
        page_format="A3",
        depth_scale=200,
        properties={
            "custom_width_mm": 250.0,
            "custom_height_mm": 500.0,
            "orientation": "landscape",
        },
        header_elements=[
            MasterlogHeaderElement(
                "logo", "image", 5.0, 5.0, 30.0, 20.0, {"asset_ref": "sha256:logo"}
            )
        ],
        columns=[
            MasterlogColumnTemplate(
                "gas",
                "Gas",
                "curves",
                35.0,
                ["TG", "C1"],
                x_scale="logarithmic",
                x_min=0.1,
                x_max=1000.0,
                show_legend=False,
                line_color="#112233",
                line_width=2.5,
                line_style="dash",
            )
        ],
        version=3,
    )
    project.wells["well-1"].canvas_objects.append(
        CanvasObject(
            "show", "masterlog_symbol", "parameter", 10.0, 20.0, 8.0, 8.0,
            top_depth=1250.0,
            time_value="2026-07-15T10:30:00+05:00",
            parameter_mnemonic="ROP",
            track_id="drilling",
            properties={"symbol_id": "oil_show", "template_id": "standard"},
        )
    )

    save_project(project, target)
    restored = load_project(target)

    template = restored.masterlog_templates["standard"]
    assert template.page_format == "A3"
    assert template.properties["custom_width_mm"] == 250.0
    assert template.properties["custom_height_mm"] == 500.0
    assert template.properties["orientation"] == "landscape"
    assert template.columns[0].curve_mnemonics == ["TG", "C1"]
    assert template.columns[0].x_scale == "logarithmic"
    assert template.columns[0].show_legend is False
    assert template.columns[0].line_color == "#112233"
    assert template.columns[0].line_style == "dash"
    assert template.header_elements[0].properties["asset_ref"] == "sha256:logo"
    assert template.version == 3
    canvas_object = restored.wells["well-1"].canvas_objects[0]
    assert canvas_object.parameter_mnemonic == "ROP"
    assert canvas_object.time_value.endswith("+05:00")
    assert canvas_object.object_type == "masterlog_symbol"
    assert canvas_object.properties["template_id"] == "standard"


def test_project_document_round_trip_preserves_lossless_source(tmp_path) -> None:
    target = tmp_path / "test.geolog.json"
    source = parse_lossless_las(b"~V\r\nVERS. 2.0\r\n~A\r\n100 1\r\n")

    save_project(make_project(), target, source_documents={"dataset-1": source})
    document = load_project_document(target)

    assert document.source_documents["dataset-1"].to_bytes() == source.to_bytes()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["source_artifacts"]["dataset-1"]["sha256"] == source.sha256
    assert "raw_bytes" not in target.read_text(encoding="utf-8")


def test_project_document_round_trip_preserves_png_asset(tmp_path) -> None:
    from geoworkbench.printing.image_assets import create_png_asset

    target = tmp_path / "image.geolog.json"
    source = tmp_path / "logo.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\nproject-logo")
    asset = create_png_asset(source)

    save_project(make_project(), target, image_assets={asset.asset_id: asset})
    restored = load_project_document(target)

    assert restored.image_assets[asset.asset_id].payload == asset.payload
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["format_version"] == PROJECT_FORMAT_VERSION
    assert payload["image_assets"][asset.asset_id]["media_type"] == "image/png"


def test_project_document_round_trip_preserves_import_report(tmp_path) -> None:
    target = tmp_path / "report.geolog.json"
    raw = b"~V\nVERS. 2.0\n~W\nNULL. -999.25\n~C\nDEPT.M\n~A\n100\n101\n"
    source = parse_lossless_las(raw)
    report = make_import_report(raw)

    save_project(
        make_project(),
        target,
        source_documents={"dataset-1": source},
        import_reports={"dataset-1": report},
    )
    restored = load_project_document(target)

    restored_report = restored.import_reports["dataset-1"]
    assert restored_report.source.sha256 == source.sha256
    assert restored_report.depth_axis.direction is DepthDirection.ASCENDING
    assert restored_report.issues[0].code == "test"


def test_project_load_rejects_report_artifact_fingerprint_mismatch(tmp_path) -> None:
    target = tmp_path / "mismatch.geolog.json"
    raw = b"~V\nVERS. 2.0\n~W\nNULL. -999.25\n~C\nDEPT.M\n~A\n100\n101\n"
    save_project(
        make_project(),
        target,
        source_documents={"dataset-1": parse_lossless_las(raw)},
        import_reports={"dataset-1": make_import_report(raw)},
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["import_reports"]["dataset-1"]["source"]["sha256"] = "0" * 64
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProjectFormatError, match="не соответствует source artifact"):
        load_project_document(target)


def test_project_document_round_trip_preserves_multiple_indexes(tmp_path) -> None:
    target = tmp_path / "indexes.geolog.json"
    project = make_project()
    dataset = project.wells["well-1"].datasets["dataset-1"]
    dataset.add_index(
        DatasetIndex(
            "record-time",
            "DATETIME",
            IndexType.DATETIME,
            IndexRole.TIME,
            None,
            np.array(["2026-01-01", "2026-01-02"], dtype="datetime64[D]"),
            confidence=0.95,
            evidence=("test datetime",),
            timezone="UTC",
        ),
        make_active=True,
    )

    save_project(project, target)
    restored = load_project_document(target).project.wells["well-1"].datasets["dataset-1"]

    assert restored.active_index_id == "record-time"
    assert restored.active_index.index_type is IndexType.DATETIME
    assert restored.active_index.timezone == "UTC"
    assert restored.active_index.values.dtype == np.dtype("datetime64[ns]")
    np.testing.assert_array_equal(
        restored.active_index.values,
        np.array(["2026-01-01", "2026-01-02"], dtype="datetime64[ns]"),
    )


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


def test_v5_project_migrates_depth_to_primary_index(tmp_path) -> None:
    target = tmp_path / "v5.geolog.json"
    save_project(make_project(), target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["format_version"] = 5
    dataset_payload = payload["project"]["wells"]["well-1"]["datasets"]["dataset-1"]
    dataset_payload.pop("indexes")
    dataset_payload.pop("active_index_id")

    restored = project_document_from_dict(payload).project.wells["well-1"].datasets["dataset-1"]

    assert restored.active_index.index_type is IndexType.MD
    np.testing.assert_array_equal(restored.active_index.values, restored.depth)


def test_v6_project_migrates_with_empty_import_reports(tmp_path) -> None:
    target = tmp_path / "v6.geolog.json"
    save_project(make_project(), target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["format_version"] = 6
    payload.pop("import_reports")

    document = project_document_from_dict(payload)

    assert document.import_reports == {}


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
