from __future__ import annotations

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
        assert (
            dialog.order_combo.currentData()
            is InterpretationPrintOrder.LAST_TO_FIRST
        )
        assert dialog.cuttings_visibility_combo.currentData() is GeologyTrackVisibility.SHOW
        assert dialog.lba_visibility_combo.currentData() is GeologyTrackVisibility.HIDE
        assert dialog.selected_composition() == _composition()
    finally:
        dialog.close()
