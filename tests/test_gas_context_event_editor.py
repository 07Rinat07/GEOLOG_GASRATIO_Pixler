import numpy as np

from geoworkbench.domain.gas_context_events import (
    GasContextEventType,
    InterpretationImpact,
)
from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.gas_context_event_editor import (
    GasContextEventEditorController,
)


def _session() -> ProjectSession:
    session = ProjectSession()
    session.add_dataset(
        Dataset(
            dataset_id="dataset",
            name="Well",
            kind=DatasetKind.GTI,
            depth_domain=DepthDomain.MD,
            depth=np.array([100.0, 150.0, 200.0]),
        )
    )
    session.dirty = False
    return session


def test_editor_keeps_mutations_transactional_until_commit() -> None:
    session = _session()
    well = session.current_well
    assert well is not None

    controller = GasContextEventEditorController(session)
    first = controller.add(
        event_type=GasContextEventType.CONNECTION_GAS,
        top_depth=120.0,
        bottom_depth=121.5,
        confirmed=True,
        reported_total_gas=4.2,
        reported_unit="%",
        comment="connection",
    )
    duplicate = controller.duplicate(first.event_id)
    controller.update(
        duplicate.event_id,
        event_type=GasContextEventType.TRIP_GAS,
        top_depth=140.0,
        bottom_depth=143.0,
        impact=InterpretationImpact.TECHNOLOGICAL_GAS,
        confirmed=False,
        reported_total_gas=None,
        reported_unit=None,
        comment="draft trip gas",
    )

    assert controller.changed is True
    assert well.gas_context_events == []
    assert session.dirty is False

    assert controller.commit() is True

    assert session.dirty is True
    assert len(well.gas_context_events) == 2
    assert len({event.event_id for event in well.gas_context_events}) == 2
    assert {event.event_type for event in well.gas_context_events} == {
        GasContextEventType.CONNECTION_GAS,
        GasContextEventType.TRIP_GAS,
    }
    draft = next(
        event
        for event in well.gas_context_events
        if event.event_type is GasContextEventType.TRIP_GAS
    )
    assert draft.confirmed is False


def test_editor_reset_and_uncommitted_changes_do_not_touch_well() -> None:
    session = _session()
    well = session.current_well
    assert well is not None

    controller = GasContextEventEditorController(session)
    controller.add(
        event_type=GasContextEventType.FORMATION_SHOW,
        top_depth=150.0,
        bottom_depth=155.0,
    )
    controller.reset()

    assert controller.changed is False
    assert controller.list_events() == ()
    assert well.gas_context_events == []
    assert session.dirty is False
