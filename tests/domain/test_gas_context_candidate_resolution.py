import pytest

from geoworkbench.domain.gas_context_events import (
    GasContextEvent,
    GasContextEventType,
    GasContextRegistry,
    InterpretationImpact,
)
from geoworkbench.domain.models import DepthDomain


def test_registry_resolves_confirmed_overlap_for_candidate_interval() -> None:
    registry = GasContextRegistry(
        (
            GasContextEvent(
                event_id="formation",
                event_type=GasContextEventType.FORMATION_SHOW,
                top_depth=1000.0,
                bottom_depth=1010.0,
            ),
            GasContextEvent(
                event_id="trip",
                event_type=GasContextEventType.TRIP_GAS,
                top_depth=1005.0,
                bottom_depth=1006.0,
            ),
        )
    )

    resolved = registry.resolve_for_interval(1004.5, 1006.5)

    assert resolved is not None
    assert resolved.event_id == "trip"


def test_registry_ignores_draft_overlap_for_candidate_interval() -> None:
    registry = GasContextRegistry(
        (
            GasContextEvent(
                event_id="draft-test",
                event_type=GasContextEventType.GAS_LINE_TEST_GAS,
                top_depth=1000.0,
                bottom_depth=1010.0,
                confirmed=False,
            ),
            GasContextEvent(
                event_id="formation",
                event_type=GasContextEventType.FORMATION_SHOW,
                top_depth=1005.0,
                bottom_depth=1006.0,
            ),
        )
    )

    resolved = registry.resolve_for_interval(1005.2, 1005.8)

    assert resolved is not None
    assert resolved.event_id == "formation"


@pytest.mark.parametrize(
    ("event_type", "expected"),
    (
        (GasContextEventType.CHROMATOGRAPH_TEST_GAS, InterpretationImpact.EXCLUDE_GEOLOGICAL),
        (GasContextEventType.GAS_LINE_TEST_GAS, InterpretationImpact.EXCLUDE_GEOLOGICAL),
        (GasContextEventType.LAG_TRACER_GAS, InterpretationImpact.EXCLUDE_GEOLOGICAL),
        (GasContextEventType.CALIBRATION_GAS, InterpretationImpact.EXCLUDE_GEOLOGICAL),
        (GasContextEventType.SWAB_GAS, InterpretationImpact.TECHNOLOGICAL_GAS),
        (GasContextEventType.TRIP_GAS, InterpretationImpact.TECHNOLOGICAL_GAS),
        (GasContextEventType.CONNECTION_GAS, InterpretationImpact.TECHNOLOGICAL_GAS),
        (GasContextEventType.CIRCULATED_GAS, InterpretationImpact.TECHNOLOGICAL_GAS),
        (GasContextEventType.RECYCLED_GAS, InterpretationImpact.TECHNOLOGICAL_GAS),
        (GasContextEventType.OTHER_TECHNOLOGICAL, InterpretationImpact.TECHNOLOGICAL_GAS),
        (GasContextEventType.FORMATION_SHOW, InterpretationImpact.FORMATION_GAS),
        (GasContextEventType.BACKGROUND, InterpretationImpact.REVIEW_REQUIRED),
        (GasContextEventType.ELEVATED_UNCLASSIFIED, InterpretationImpact.REVIEW_REQUIRED),
    ),
)
def test_every_gas_context_type_has_deterministic_default_impact(
    event_type: GasContextEventType,
    expected: InterpretationImpact,
) -> None:
    event = GasContextEvent(
        event_id=event_type.value,
        event_type=event_type,
        top_depth=1000.0,
        bottom_depth=1001.0,
        depth_domain=DepthDomain.MD,
    )

    assert event.effective_impact is expected


def test_qc_test_context_wins_overlap_over_operational_and_formation_context() -> None:
    registry = GasContextRegistry(
        (
            GasContextEvent(
                "formation",
                GasContextEventType.FORMATION_SHOW,
                1000.0,
                1010.0,
                DepthDomain.MD,
            ),
            GasContextEvent(
                "trip",
                GasContextEventType.TRIP_GAS,
                1002.0,
                1008.0,
                DepthDomain.MD,
            ),
            GasContextEvent(
                "calibration",
                GasContextEventType.CALIBRATION_GAS,
                1004.0,
                1006.0,
                DepthDomain.MD,
            ),
        )
    )

    resolved = registry.resolve_for_interval(
        1004.5,
        1005.5,
        depth_domain=DepthDomain.MD,
    )

    assert resolved is not None
    assert resolved.event_id == "calibration"
    assert resolved.effective_impact is InterpretationImpact.EXCLUDE_GEOLOGICAL


def test_registry_filters_overlaps_by_depth_domain() -> None:
    registry = GasContextRegistry(
        (
            GasContextEvent(
                "md-test",
                GasContextEventType.GAS_LINE_TEST_GAS,
                1000.0,
                1010.0,
                DepthDomain.MD,
            ),
            GasContextEvent(
                "tvd-formation",
                GasContextEventType.FORMATION_SHOW,
                1000.0,
                1010.0,
                DepthDomain.TVD,
            ),
        )
    )

    md = registry.resolve_for_interval(1002.0, 1003.0, depth_domain=DepthDomain.MD)
    tvd = registry.resolve_for_interval(1002.0, 1003.0, depth_domain=DepthDomain.TVD)

    assert md is not None and md.event_id == "md-test"
    assert tvd is not None and tvd.event_id == "tvd-formation"
