from __future__ import annotations

import inspect
import json

import numpy as np
import pytest
from PySide6.QtGui import QPageLayout

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, Project, Well
from geoworkbench.printing.hydrocarbon_interpretation_geology_settings import (
    GeologyTrackVisibility,
)
from geoworkbench.domain.report_composition import (
    InterpretationReportComposition,
    ReportPageOrientation,
    ReportPrintOrder,
    ReportTrackVisibility,
)
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.package_project_repository import PackageProjectRepository
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.dataset_merge_controller import DatasetMergeController
from geoworkbench.project.depth_axis_controller import DepthAxisController
from geoworkbench.project.derived_dataset_controller import DerivedDatasetController
from geoworkbench.project.lag_correction_controller import LagCorrectionProjectController
from geoworkbench.project.time_to_depth_controller import TimeToDepthController
from geoworkbench.project.time_depth_aggregation_controller import TimeDepthAggregationController
from geoworkbench.ui import interpretation_report_workspace_final
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.storage.project_codec import (
    PROJECT_FORMAT_VERSION,
    ProjectDocument,
    load_project_document,
)
from geoworkbench.ui.interpretation_print_layout_dialog import (
    InterpretationPrintLayoutDialog,
    InterpretationPrintOrder,
)


def _project() -> Project:
    dataset = Dataset(
        "dataset-report-composition",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.asarray([1000.0, 1001.0], dtype=np.float64),
    )
    well = Well("well-report-composition", "Well", datasets={dataset.dataset_id: dataset})
    return Project("project-report-composition", "Project", wells={well.well_id: well})


def _composition() -> InterpretationReportComposition:
    return InterpretationReportComposition(
        orientation=ReportPageOrientation.LANDSCAPE,
        print_order=ReportPrintOrder.LAST_TO_FIRST,
        cuttings=ReportTrackVisibility.SHOW,
        lba=ReportTrackVisibility.HIDE,
    )


def test_project_v37_json_round_trip_preserves_report_composition(tmp_path) -> None:
    project = _project()
    target = tmp_path / "project.geolog.json"

    save_project(
        project,
        target,
        report_compositions={"dataset-report-composition": _composition()},
    )
    loaded = load_project_document(target)

    assert PROJECT_FORMAT_VERSION == 37
    assert loaded.report_compositions == {
        "dataset-report-composition": _composition()
    }


def test_project_v36_migrates_with_empty_report_compositions(tmp_path) -> None:
    project = _project()
    target = tmp_path / "legacy.geolog.json"
    save_project(project, target)

    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["format_version"] = 36
    payload.pop("report_compositions", None)
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    loaded = load_project_document(target)

    assert loaded.report_compositions == {}


def test_save_rejects_report_composition_for_unknown_dataset(tmp_path) -> None:
    with pytest.raises(ValueError, match="неизвестный набор"):
        save_project(
            _project(),
            tmp_path / "invalid.geolog.json",
            report_compositions={"missing-dataset": _composition()},
        )


def test_package_round_trip_preserves_report_composition(tmp_path) -> None:
    document = ProjectDocument(
        project=_project(),
        report_compositions={"dataset-report-composition": _composition()},
    )
    target = tmp_path / "project.geologpkg"
    repository = PackageProjectRepository()

    repository.save(document, target)
    loaded = repository.load(target)

    assert loaded.report_compositions == document.report_compositions


def test_layout_dialog_restores_and_returns_persisted_composition(qapp) -> None:
    dialog = InterpretationPrintLayoutDialog(
        language=AppLanguage.EN,
        initial=_composition(),
    )
    try:
        assert dialog.orientation_combo.currentData() == QPageLayout.Orientation.Landscape
        layout = dialog.selected_layout()
        assert layout.order is InterpretationPrintOrder.LAST_TO_FIRST
        assert layout.geology_tracks.cuttings is GeologyTrackVisibility.SHOW
        assert layout.geology_tracks.lba is GeologyTrackVisibility.HIDE
        assert dialog.selected_composition() == _composition()
    finally:
        dialog.close()


def test_project_controller_save_reopen_restores_report_composition(tmp_path) -> None:
    project = _project()
    session = ProjectSession(
        project=project,
        current_well_id="well-report-composition",
        current_dataset_id="dataset-report-composition",
        report_compositions={"dataset-report-composition": _composition()},
    )
    controller = ProjectController(session=session)
    target = tmp_path / "controller.geologpkg"

    controller.save_project(target)
    reopened = ProjectController().open_project(target)

    assert reopened.report_compositions == {
        "dataset-report-composition": _composition()
    }
    assert not reopened.dirty


def test_dataset_removal_paths_clear_report_compositions() -> None:
    sources = (
        inspect.getsource(DatasetMergeController._undo_command),
        inspect.getsource(DepthAxisController.undo_ascending_copy),
        inspect.getsource(DepthAxisController.undo_resample),
        inspect.getsource(DerivedDatasetController.rollback),
        inspect.getsource(LagCorrectionProjectController.delete_profile),
        inspect.getsource(TimeToDepthController.undo),
        inspect.getsource(TimeDepthAggregationController.undo),
    )

    assert all("report_compositions" in source for source in sources)
    assert all(".pop(" in source for source in sources)


def test_dataset_rebind_invalidates_preview_composition_cache() -> None:
    workspace_type = interpretation_report_workspace_final.InterpretationReportWorkspace
    source = inspect.getsource(workspace_type._sync_depth_interval_dataset)

    assert "self._preview_geology_report_key = None" in source
