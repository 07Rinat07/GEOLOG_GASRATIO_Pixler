"""Gas-context MD events are not automatically aligned to another lag MD axis."""

from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.domain.depth_interval import DepthInterval
from geoworkbench.domain.gas_context_events import GasContextEvent, GasContextEventType
from geoworkbench.domain.lag_correction import (
    ConstantTimeLagParameters,
    LagCorrectionAxisMode,
    LagCorrectionMethod,
    LagCorrectionTarget,
)
from geoworkbench.domain.models import (
    Dataset, DatasetIndex, DatasetKind, DepthDomain, IndexType, IndexRole,
    TimeDepthAggregationPolicy,
)
from geoworkbench.project.lag_correction_controller import LagCorrectionProjectController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.hydrocarbon_interpretation import (
    build_hydrocarbon_interpretation_report,
    build_opus_interpretation_report,
)


def _lagged_session() -> tuple[ProjectSession, LagCorrectionProjectController, str, np.ndarray]:
    source_depth = np.arange(1000.0, 1100.0)
    dataset = Dataset("source", "Raw measured gas", DatasetKind.GTI, DepthDomain.MD, source_depth)
    dataset.add_index(DatasetIndex(
        "time", "TIME", IndexType.RELATIVE_TIME, IndexRole.TIME, "s",
        np.arange(source_depth.size, dtype=np.float64),
    ))
    measured = 0.02 + 0.001 * np.sin(np.arange(source_depth.size) * 0.13)
    measured[51:54] = (0.16, 0.20, 0.18)
    curve = dataset.upsert_curve(
        "TGAS", measured, unit="%vol", provenance="source:las",
    )
    session = ProjectSession()
    session.add_dataset(dataset, "Well")
    well = session.current_well
    assert well is not None
    # A confirmed source-coordinate technological event at 1041-1043 m
    # coincides numerically with a *different* gas peak after a 10 s lag shift.
    well.gas_context_events.append(GasContextEvent(
        event_id="original-md-technical",
        event_type=GasContextEventType.CONNECTION_GAS,
        top_depth=1041.0,
        bottom_depth=1043.0,
        depth_domain=DepthDomain.MD,
        confirmed=True,
    ))
    controller = LagCorrectionProjectController(session)
    profile = controller.create_profile(
        name="Gas lag", target=LagCorrectionTarget.GAS,
        source_time_index_id="time",
        source_depth_index_id="source:primary-index",
        target_curve_ids=(curve.metadata.curve_id,),
        method=LagCorrectionMethod.CONSTANT_TIME,
        parameters=ConstantTimeLagParameters(10.0),
        aggregation_policy=TimeDepthAggregationPolicy.ERROR,
        created_at="2026-10-17T08:00:00Z",
        created_by="Geologist",
    )
    return session, controller, profile.profile_id, measured.copy()


@pytest.mark.parametrize("is_opus", [False, True])
def test_corrected_lag_axis_does_not_apply_source_md_events_to_different_rows(
    is_opus: bool,
) -> None:
    session, controller, profile_id, original = _lagged_session()
    selection = controller.select_projection(profile_id, LagCorrectionAxisMode.CORRECTED)
    assert selection.dataset.active_index.mnemonic.endswith("_LAG_CORR")
    np.testing.assert_array_equal(selection.dataset.curve_by_mnemonic("TGAS").values, original)
    builder = build_opus_interpretation_report if is_opus else build_hydrocarbon_interpretation_report
    report = builder(session, threshold=3.0)
    assert report.gas_context_events == ()
    assert report.suppressed_candidates == ()
    assert any("не применены к скорректированной" in w for w in report.warnings)
    if not is_opus:
        assert len(report.candidates) == 1
        assert report.candidates[0].top_depth <= 1041.0
        assert report.candidates[0].bottom_depth >= 1043.0
    well = session.current_well
    assert well is not None
    assert well.gas_context_events[0].top_depth == 1041.0
    source = well.datasets["source"]
    np.testing.assert_array_equal(source.curve_by_mnemonic("TGAS").values, original)


def test_source_lag_axis_keeps_legacy_md_events_and_no_false_lag_warning() -> None:
    session, controller, profile_id, _ = _lagged_session()
    controller.select_projection(profile_id, LagCorrectionAxisMode.SOURCE)
    report = build_hydrocarbon_interpretation_report(session, threshold=3.0)
    assert not any("не применены к скорректированной" in w for w in report.warnings)
    assert len(report.candidates) == 1
    assert report.candidates[0].top_depth <= 1051.0
    assert report.candidates[0].bottom_depth >= 1053.0


def test_scoped_corrected_lag_report_does_not_rebind_md_event_by_number() -> None:
    session, controller, profile_id, _ = _lagged_session()
    controller.select_projection(profile_id, LagCorrectionAxisMode.CORRECTED)
    report = build_hydrocarbon_interpretation_report(
        session, threshold=3.0,
        depth_interval=DepthInterval(1035.0, 1048.0),
    )
    assert report.suppressed_candidates == ()
    assert report.gas_context_events == ()
    assert any("не применены к скорректированной" in w for w in report.warnings)
