from __future__ import annotations

from pathlib import Path

import pytest

from geoworkbench.domain.analysis_update import AnalysisField
from geoworkbench.domain.models import CuttingsSample, Project, Well
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.well_analysis_update_controller import WellAnalysisUpdateController
from geoworkbench.project.well_analysis_update_workflow import (
    LateAnalysisPersistenceError,
    WellAnalysisUpdateWorkflow,
)
from geoworkbench.services.well_analysis_update import AnalysisSourceSample, AnalysisSourceValue
from geoworkbench.storage.project_file_safety import SaveMode


_SOURCE_SHA = "a" * 64


class _RecordingProjectSaver:
    def __init__(self, session: ProjectSession, *, error: Exception | None = None) -> None:
        self._session = session
        self._error = error
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
        if self._error is not None:
            raise self._error
        self._session.dirty = False
        return Path("project.gprj")


def _session() -> ProjectSession:
    well = Well(
        well_id="well-1",
        name="Well 1",
        cuttings=[CuttingsSample("sample-1", 100.0, 101.0)],
    )
    return ProjectSession(
        project=Project("project-1", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
    )


def _source() -> tuple[AnalysisSourceSample, ...]:
    return (
        AnalysisSourceSample(
            100.0,
            101.0,
            (AnalysisSourceValue(AnalysisField.CALCITE_PERCENT, 37.5),),
            "sample-1",
        ),
    )


def _workflow(
    session: ProjectSession,
    saver: _RecordingProjectSaver,
) -> WellAnalysisUpdateWorkflow:
    return WellAnalysisUpdateWorkflow(
        session,
        WellAnalysisUpdateController(session),
        saver,
    )


def _preview(workflow: WellAnalysisUpdateWorkflow):
    return workflow.analyze(
        _source(),
        selected_fields=(AnalysisField.CALCITE_PERCENT,),
        source_name="late.csv",
        source_sha256=_SOURCE_SHA,
    )


def test_workflow_material_autosaves_confirmed_analysis_update() -> None:
    session = _session()
    saver = _RecordingProjectSaver(session)
    workflow = _workflow(session, saver)
    plan = _preview(workflow)

    outcome = workflow.apply(plan, selected_changes=plan.changes)

    well = session.current_well
    assert well is not None
    assert outcome.record is not None
    assert well.cuttings[0].calcite_percent == 37.5
    assert well.content_revision == 2
    assert well.analysis_update_history == [outcome.record]
    assert saver.modes == [SaveMode.MATERIAL_AUTOSAVE]
    assert not session.dirty


def test_workflow_rolls_back_well_and_dirty_state_when_autosave_fails() -> None:
    session = _session()
    session.dirty = True
    saver = _RecordingProjectSaver(session, error=OSError("disk full"))
    workflow = _workflow(session, saver)
    plan = _preview(workflow)
    well = session.current_well
    assert well is not None
    original_cuttings = list(well.cuttings)
    original_history = list(well.analysis_update_history)
    original_revision = well.content_revision

    with pytest.raises(LateAnalysisPersistenceError, match="изменения полностью отменены"):
        workflow.apply(plan, selected_changes=plan.changes)

    assert well.cuttings == original_cuttings
    assert well.cuttings[0].calcite_percent is None
    assert well.analysis_update_history == original_history
    assert well.content_revision == original_revision
    assert session.dirty
    assert saver.modes == [SaveMode.MATERIAL_AUTOSAVE]


def test_workflow_skips_autosave_for_noop_confirmation() -> None:
    session = _session()
    saver = _RecordingProjectSaver(session)
    workflow = _workflow(session, saver)
    plan = _preview(workflow)

    outcome = workflow.apply(plan, selected_changes=())

    well = session.current_well
    assert well is not None
    assert outcome.record is None
    assert well.cuttings[0].calcite_percent is None
    assert well.content_revision == 1
    assert not well.analysis_update_history
    assert not saver.modes
    assert not session.dirty


def test_workflow_restores_snapshot_when_controller_apply_raises(monkeypatch) -> None:
    session = _session()
    saver = _RecordingProjectSaver(session)
    controller = WellAnalysisUpdateController(session)
    workflow = WellAnalysisUpdateWorkflow(session, controller, saver)
    plan = _preview(workflow)
    well = session.current_well
    assert well is not None
    original_cuttings = list(well.cuttings)

    def fail_after_mutation(*args, **kwargs):
        del args, kwargs
        well.cuttings = [CuttingsSample("sample-1", 100.0, 101.0, calcite_percent=99.0)]
        well.content_revision = 2
        session.dirty = True
        raise RuntimeError("simulated controller failure")

    monkeypatch.setattr(controller, "apply", fail_after_mutation)

    with pytest.raises(RuntimeError, match="simulated controller failure"):
        workflow.apply(plan, selected_changes=plan.changes)

    assert well.cuttings == original_cuttings
    assert well.cuttings[0].calcite_percent is None
    assert well.content_revision == 1
    assert not well.analysis_update_history
    assert not session.dirty
    assert not saver.modes
