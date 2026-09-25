from geoworkbench.domain.gas_context_events import (
    GasContextEvent,
    GasContextEventType,
    GasContextRegistry,
)


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
