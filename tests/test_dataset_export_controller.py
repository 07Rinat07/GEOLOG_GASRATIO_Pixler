from pathlib import Path

import numpy as np
import pytest

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
    ExportProfile,
    Project,
    Well,
)
from geoworkbench.data.lossless_las import parse_lossless_las
from geoworkbench.data.las_export_plan import LasExportVersion
from geoworkbench.data.las_import_report import LasImportReport, LasSourceSnapshot
from geoworkbench.project.dataset_export_controller import DatasetExportController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.depth_axis import DepthAxisReport, DepthDirection


def test_export_controller_uses_current_dataset(tmp_path, monkeypatch) -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([1.0]),
    )
    well = Well("well-1", "Well", datasets={dataset.dataset_id: dataset})
    session = ProjectSession(
        project=Project("project-1", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=dataset.dataset_id,
        source_documents={dataset.dataset_id: parse_lossless_las(b"~A\n1\n")},
    )
    captured: list[tuple[Dataset, Path, bool, object]] = []

    def fake_export(selected, target, *, overwrite=False, source_document=None, plan=None):
        assert plan is None
        captured.append((selected, target, overwrite, source_document))
        return target

    monkeypatch.setattr(
        "geoworkbench.project.dataset_export_controller.export_las",
        fake_export,
    )
    target = tmp_path / "result.las"

    result = DatasetExportController(session).export_current_las(target, overwrite=True)

    assert result == target
    assert captured == [(dataset, target, True, session.source_documents[dataset.dataset_id])]


def test_export_controller_requires_current_dataset(tmp_path) -> None:
    with pytest.raises(RuntimeError, match="набор данных"):
        DatasetExportController(ProjectSession()).export_current_las(tmp_path / "result.las")


def test_export_controller_exports_current_selection_to_csv_and_excel(tmp_path) -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0, 102.0]),
    )
    dataset.curves["rop"] = CurveData(
        CurveMetadata("rop", "ROP", "ROP", "m/h", None, dataset.dataset_id),
        np.array([10.0, 20.0, 30.0]),
    )
    well = Well("well-1", "Well", datasets={dataset.dataset_id: dataset})
    session = ProjectSession(
        project=Project("project-1", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=dataset.dataset_id,
    )
    controller = DatasetExportController(session)

    csv_target = controller.export_current_selection_text(
        tmp_path / "selection.csv", ["rop"], 101.0, 102.0
    )
    excel_target = controller.export_current_selection_excel(
        tmp_path / "selection.xlsx", ["rop"], 101.0, 102.0
    )

    assert csv_target.read_text(encoding="utf-8").splitlines() == [
        "DEPTH [m],ROP [m/h]",
        "101,20",
        "102,30",
    ]
    assert excel_target.read_bytes().startswith(b"PK")


def test_export_controller_saves_resolves_and_deletes_curve_profile() -> None:
    dataset = Dataset("dataset-1", "Dataset", DatasetKind.GTI, DepthDomain.MD, np.array([1.0]))
    dataset.curves["curve-c1"] = CurveData(
        CurveMetadata("curve-c1", "C1", "C1", "%", None, dataset.dataset_id),
        np.array([10.0]),
    )
    well = Well("well-1", "Well", datasets={dataset.dataset_id: dataset})
    session = ProjectSession(
        project=Project("project-1", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=dataset.dataset_id,
    )
    controller = DatasetExportController(session)

    profile = controller.save_selection_profile(" Gas ", ["curve-c1"])

    assert profile.name == "Gas"
    assert profile.curve_mnemonics == ("C1",)
    assert controller.resolve_profile_curve_ids(profile.profile_id) == ("curve-c1",)
    assert session.dirty is True
    controller.delete_selection_profile(profile.profile_id)
    assert session.project.export_profiles == {}


def test_export_controller_exports_current_dataset_to_json(tmp_path) -> None:
    dataset = Dataset("dataset-1", "Dataset", DatasetKind.GTI, DepthDomain.MD, np.array([1.0]))
    well = Well("well-1", "Well", datasets={dataset.dataset_id: dataset})
    session = ProjectSession(
        project=Project("project-1", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=dataset.dataset_id,
    )

    target = DatasetExportController(session).export_current_json(tmp_path / "dataset.json")

    assert '"dataset_id": "dataset-1"' in target.read_text(encoding="utf-8")


def test_export_profile_reports_missing_mnemonics() -> None:
    dataset = Dataset("dataset-1", "Dataset", DatasetKind.GTI, DepthDomain.MD, np.array([1.0]))
    well = Well("well-1", "Well", datasets={dataset.dataset_id: dataset})
    session = ProjectSession(
        project=Project("project-1", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=dataset.dataset_id,
    )
    session.project.export_profiles["gas"] = ExportProfile("gas", "Gas", ("C1",))

    with pytest.raises(ValueError, match="C1"):
        DatasetExportController(session).resolve_profile_curve_ids("gas")


def test_default_export_plan_uses_typed_header_null() -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([1.0]),
        headers={"NULL": "-999.25"},
    )
    well = Well("well-1", "Well", datasets={dataset.dataset_id: dataset})
    session = ProjectSession(
        project=Project("project-1", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=dataset.dataset_id,
    )

    plan = DatasetExportController(session).default_las_plan()

    assert plan.null_value == pytest.approx(-999.25)


def test_default_export_plan_preserves_source_version_wrap_and_null() -> None:
    dataset = Dataset("dataset-1", "Dataset", DatasetKind.GTI, DepthDomain.MD, np.array([1.0]))
    well = Well("well-1", "Well", datasets={dataset.dataset_id: dataset})
    report = LasImportReport(
        LasSourceSnapshot(
            Path("source.las"),
            1,
            "0" * 64,
            "utf-8",
            "lf",
            ("version", "well", "curve", "ascii"),
            "1.2",
            "YES",
            -999.25,
        ),
        DepthAxisReport(DepthDirection.UNKNOWN, 1.0, 1.0, None, True, 0, 0, 0),
        (),
    )
    session = ProjectSession(
        project=Project("project-1", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=dataset.dataset_id,
        import_reports={dataset.dataset_id: report},
    )

    plan = DatasetExportController(session).default_las_plan()

    assert plan.version is LasExportVersion.V1_2
    assert plan.wrap is True
    assert plan.null_value == pytest.approx(-999.25)


def test_default_export_plan_uses_declared_headers_without_source_report() -> None:
    dataset = Dataset(
        "dataset-1",
        "New LAS",
        DatasetKind.USER,
        DepthDomain.MD,
        np.array([0.0, 1.0]),
        headers={"NULL": "-999.0"},
        version_headers={"VERS": "1.2", "WRAP": "YES"},
    )
    well = Well("well-1", "Well", datasets={dataset.dataset_id: dataset})
    session = ProjectSession(
        project=Project("project-1", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=dataset.dataset_id,
    )

    plan = DatasetExportController(session).default_las_plan()

    assert plan.version is LasExportVersion.V1_2
    assert plan.wrap is True
    assert plan.null_value == pytest.approx(-999.0)
