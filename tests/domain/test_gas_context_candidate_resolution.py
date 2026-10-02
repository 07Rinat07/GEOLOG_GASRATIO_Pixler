from geoworkbench.domain.gas_context_events import (
    GasContextEvent,
    GasContextEventType,
    GasContextRegistry,
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


def test_registry_resolves_negative_tvdss_interval() -> None:
    event = GasContextEvent(
        event_id="negative-tvdss",
        event_type=GasContextEventType.CONNECTION_GAS,
        top_depth=-61.0,
        bottom_depth=-57.0,
        depth_domain=DepthDomain.TVDSS,
    )
    registry = GasContextRegistry((event,))

    assert event.contains_depth(-59.0) is True
    assert registry.resolve_for_interval(
        -60.0,
        -58.0,
        depth_domain=DepthDomain.TVDSS,
    ) is event
