from __future__ import annotations

from dataclasses import replace

import pytest

from geoworkbench.domain.analysis_update import AnalysisField
from geoworkbench.domain.models import CuttingsSample, Project, Well
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.well_analysis_update_controller import WellAnalysisUpdateController
from geoworkbench.services.well_analysis_update import (
    AnalysisSourceSample,
    AnalysisSourceValue,
    AnalysisUpdateError,
)


_SOURCE_SHA = "a" * 64


def _session(*, calcite: float | None = None) -> ProjectSession:
    well = Well(
        well_id="well-1",
        name="Well 1",
        cuttings=[CuttingsSample("sample-1", 100.0, 101.0, calcite_percent=calcite)],
    )
    return ProjectSession(
        project=Project("project-1", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
    )


def _source(
    *,
    calcite: float = 37.5,
    interpretation: str = "oil show",
) -> tuple[AnalysisSourceSample, ...]:
    return (
        AnalysisSourceSample(
            100.0,
            101.0,
            (
                AnalysisSourceValue(AnalysisField.CALCITE_PERCENT, calcite),
                AnalysisSourceValue(AnalysisField.ANALYSIS_INTERPRETATION, interpretation),
            ),
            "sample-1",
        ),
    )


def test_controller_commits_only_selected_changes_and_appends_audit() -> None:
    session = _session()
    controller = WellAnalysisUpdateController(session)
    plan = controller.analyze(
        _source(),
        selected_fields=(
            AnalysisField.CALCITE_PERCENT,
            AnalysisField.ANALYSIS_INTERPRETATION,
        ),
        source_name="late.csv",
        source_sha256=_SOURCE_SHA,
    )
    calcite_change = next(
        change for change in plan.changes if change.field is AnalysisField.CALCITE_PERCENT
    )

    outcome = controller.apply(plan, selected_changes=(calcite_change,))

    well = session.current_well
    assert well is not None
    assert well.cuttings[0].calcite_percent == 37.5
    assert well.cuttings[0].analysis_interpretation is None
    assert well.content_revision == 2
    assert outcome.record is not None
    assert outcome.record.changes == (calcite_change,)
    assert well.analysis_update_history == [outcome.record]
    assert session.dirty


def test_controller_no_selection_is_noop_and_consumes_preview() -> None:
    session = _session()
    controller = WellAnalysisUpdateController(session)
    plan = controller.analyze(
        _source(),
        selected_fields=(AnalysisField.CALCITE_PERCENT,),
        source_name="late.csv",
        source_sha256=_SOURCE_SHA,
    )
    well = session.current_well
    assert well is not None
    original_cuttings = well.cuttings

    outcome = controller.apply(plan, selected_changes=())

    assert outcome.record is None
    assert well.cuttings is original_cuttings
    assert well.content_revision == 1
    assert not well.analysis_update_history
    assert not session.dirty
    with pytest.raises(AnalysisUpdateError, match="повторно просмотрите"):
        controller.apply(plan, selected_changes=())


def test_controller_rejects_stale_preview_without_partial_mutation() -> None:
    session = _session()
    controller = WellAnalysisUpdateController(session)
    plan = controller.analyze(
        _source(),
        selected_fields=(AnalysisField.CALCITE_PERCENT,),
        source_name="late.csv",
        source_sha256=_SOURCE_SHA,
    )
    well = session.current_well
    assert well is not None
    well.cuttings[0] = replace(well.cuttings[0], lba_description="manual change")
    before = list(well.cuttings)

    with pytest.raises(AnalysisUpdateError, match="повторите просмотр"):
        controller.apply(plan, selected_changes=plan.changes)

    assert well.cuttings == before
    assert well.content_revision == 1
    assert not well.analysis_update_history
    assert not session.dirty


def test_controller_preserves_existing_manual_value_as_conflict() -> None:
    session = _session(calcite=12.0)
    controller = WellAnalysisUpdateController(session)

    plan = controller.analyze(
        _source(calcite=37.5),
        selected_fields=(AnalysisField.CALCITE_PERCENT,),
        source_name="late.csv",
        source_sha256=_SOURCE_SHA,
    )

    assert not plan.changes
    assert plan.conflict_count == 1
    assert plan.conflicts[0].existing_value == 12.0
    outcome = controller.apply(plan, selected_changes=())
    well = session.current_well
    assert well is not None
    assert outcome.record is None
    assert well.cuttings[0].calcite_percent == 12.0
    assert not well.analysis_update_history
    assert not session.dirty


def test_controller_does_not_dirty_session_when_atomic_service_fails(monkeypatch) -> None:
    session = _session()
    controller = WellAnalysisUpdateController(session)
    plan = controller.analyze(
        _source(),
        selected_fields=(AnalysisField.CALCITE_PERCENT,),
        source_name="late.csv",
        source_sha256=_SOURCE_SHA,
    )
    well = session.current_well
    assert well is not None
    original_cuttings = well.cuttings

    def fail_apply(*args, **kwargs):
        raise AnalysisUpdateError("simulated atomic apply failure")

    monkeypatch.setattr(
        "geoworkbench.project.well_analysis_update_controller.apply_prepared_analysis_update",
        fail_apply,
    )

    with pytest.raises(AnalysisUpdateError, match="simulated atomic apply failure"):
        controller.apply(plan, selected_changes=plan.changes)

    assert well.cuttings is original_cuttings
    assert well.cuttings[0].calcite_percent is None
    assert well.content_revision == 1
    assert not well.analysis_update_history
    assert not session.dirty
    with pytest.raises(AnalysisUpdateError, match="повторно просмотрите"):
        controller.apply(plan, selected_changes=plan.changes)
