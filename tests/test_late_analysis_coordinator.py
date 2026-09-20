from __future__ import annotations

from pathlib import Path

import pytest

from geoworkbench.data.late_analysis_adapter import LateAnalysisImportResult
from geoworkbench.domain.analysis_update import AnalysisField
from geoworkbench.domain.models import CuttingsSample, Project, Well
from geoworkbench.project.late_analysis_coordinator import LateAnalysisCoordinator
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.session_binding import SessionBindingController
from geoworkbench.services.well_analysis_update import (
    AnalysisSourceSample,
    AnalysisSourceValue,
    AnalysisUpdateError,
)
from geoworkbench.storage.project_file_safety import SaveMode


class _Saver:
    def __init__(self) -> None:
        self.modes: list[SaveMode] = []

    def save_project(
        self,
        target: Path | None = None,
        *,
        mode: SaveMode = SaveMode.EXPLICIT,
        allow_existing_target: bool = False,
    ) -> Path:
        del target, allow_existing_target
        self.modes.append(mode)
        return Path("project.geologpkg")


def _source_result(label: str = "lab.csv") -> LateAnalysisImportResult:
    sample = AnalysisSourceSample(
        1000.0,
        1001.0,
        (
            AnalysisSourceValue(
                AnalysisField.CALCITE_PERCENT,
                25.0,
            ),
        ),
        target_sample_id="sample-1",
    )
    return LateAnalysisImportResult(
        source_samples=(sample,),
        source_name=label,
        source_sha256="a" * 64,
        detected_fields=(AnalysisField.CALCITE_PERCENT,),
    )


def _session(label: str) -> ProjectSession:
    well = Well(
        "well",
        f"{label} well",
        cuttings=[CuttingsSample("sample-1", 1000.0, 1001.0)],
    )
    return ProjectSession(
        project=Project(f"{label}-project", label, wells={well.well_id: well}),
        current_well_id=well.well_id,
    )


def test_late_analysis_coordinator_loads_applies_and_reports_completion() -> None:
    session = _session("first")
    saver = _Saver()
    coordinator = LateAnalysisCoordinator(
        session,
        saver,
        loader=lambda _source: _source_result(),
    )

    review = coordinator.prepare_review(Path("lab.csv"))
    plan = coordinator.analyze(
        review.source_samples,
        selected_fields=(AnalysisField.CALCITE_PERCENT,),
        source_name=review.source_name,
        source_sha256=review.source_sha256,
    )
    outcome = coordinator.apply(plan, selected_changes=plan.changes)
    completion = coordinator.complete_review(review)

    assert outcome.record is not None
    assert session.current_well is not None
    assert session.current_well.cuttings[0].calcite_percent == 25.0
    assert completion.changed
    assert completion.applied_count == 1
    assert saver.modes == [SaveMode.MATERIAL_AUTOSAVE]


def test_late_analysis_coordinator_rebinds_and_invalidates_old_review() -> None:
    first = _session("first")
    second = _session("second")
    coordinator = LateAnalysisCoordinator(
        first,
        _Saver(),
        loader=lambda _source: _source_result(),
    )
    review = coordinator.prepare_review("first.csv")
    stale_plan = coordinator.analyze(
        review.source_samples,
        selected_fields=(AnalysisField.CALCITE_PERCENT,),
        source_name=review.source_name,
        source_sha256=review.source_sha256,
    )
    bindings = SessionBindingController()
    bindings.register(coordinator, name="late_analysis")

    report = bindings.bind(second)

    assert report.bound_controllers == 1
    assert coordinator.session is second
    assert not coordinator.complete_review(review).changed
    with pytest.raises(AnalysisUpdateError, match="повторно просмотрите"):
        coordinator.apply(stale_plan, selected_changes=stale_plan.changes)


def test_main_window_late_analysis_uses_session_bound_coordinator_source_contract() -> None:
    source = Path("src/geoworkbench/ui/main_window_drilling.py").read_text(encoding="utf-8")

    assert "LateAnalysisCoordinator(" in source
    assert 'name="late_analysis"' in source
    assert "self.late_analysis_coordinator.prepare_review(" in source
    assert "self.late_analysis_coordinator.complete_review(" in source
    assert "WellAnalysisUpdateController(self.session)" not in source
    assert "WellAnalysisUpdateWorkflow(" not in source
    assert "load_late_analysis_source(" not in source
