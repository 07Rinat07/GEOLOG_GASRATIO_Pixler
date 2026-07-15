from pathlib import Path

import numpy as np

from geoworkbench.data.las_import_report import (
    LasImportIssue,
    LasImportReport,
    LasIssueSeverity,
    LasSourceSnapshot,
)
from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
)
from geoworkbench.project.data_inspector_controller import DataInspectorController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.depth_axis import DepthAxisReport, DepthDirection


def make_controller() -> DataInspectorController:
    session = ProjectSession()
    dataset = Dataset(
        "dataset-1",
        "Logging",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0]),
        headers={"WELL": "Test Well", "FLD": "Test Field"},
    )
    dataset.curves["c1"] = CurveData(
        CurveMetadata("c1", "C1", "C1", "%", "Methane", dataset.dataset_id),
        np.array([1.0, np.nan]),
    )
    dataset.add_index(
        DatasetIndex(
            "time",
            "TIME",
            IndexType.RELATIVE_TIME,
            IndexRole.TIME,
            "s",
            np.array([0.0, 1.0]),
            confidence=0.9,
            evidence=("мнемоника TIME",),
        )
    )
    report = LasImportReport(
        LasSourceSnapshot(
            Path("test.las"), 4, "0" * 64, "utf-8", "lf", ("v", "a"), "2.0", "NO", -999.25
        ),
        DepthAxisReport(DepthDirection.ASCENDING, 100.0, 101.0, 1.0, True, 0, 0, 0),
        (LasImportIssue("test-warning", LasIssueSeverity.WARNING, "Test warning"),),
    )
    session.add_dataset(dataset, import_report=report)
    session.dirty = False
    return DataInspectorController(session)


def test_data_inspector_exposes_summary_curves_indexes_and_issues() -> None:
    controller = make_controller()

    summary = controller.summary()
    indexes = controller.indexes()
    curves = controller.curves()

    assert summary.well_name == "Test Well"
    assert summary.index_count == 2
    assert len(indexes) == 2
    assert indexes[0].active
    assert curves[0].missing_count == 1
    assert controller.import_issues()[0].code == "test-warning"


def test_data_inspector_changes_active_index_and_marks_session_dirty() -> None:
    controller = make_controller()

    controller.set_active_index("time")

    assert controller.session.current_dataset.active_index_id == "time"  # type: ignore[union-attr]
    assert controller.session.current_dataset.depth_domain is DepthDomain.MD  # type: ignore[union-attr]
    assert controller.session.dirty
