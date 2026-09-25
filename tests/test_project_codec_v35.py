from __future__ import annotations

import json
from pathlib import Path

import pytest

from geoworkbench.domain.gas_context_events import (
    GasContextEvent,
    GasContextEventType,
    GasContextRegistry,
    InterpretationImpact,
)
from geoworkbench.domain.models import Project, Well
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.project_codec import (
    PROJECT_FORMAT_VERSION,
    ProjectFormatError,
    load_project,
    project_document_from_dict,
)


def _event(
    event_id: str,
    event_type: GasContextEventType,
    top: float,
    bottom: float,
    *,
    impact: InterpretationImpact | None = None,
    confirmed: bool = True,
    reported_total_gas: float | None = None,
) -> GasContextEvent:
    return GasContextEvent(
        event_id=event_id,
        event_type=event_type,
        top_depth=top,
        bottom_depth=bottom,
        impact=impact,
        confirmed=confirmed,
        reported_total_gas=reported_total_gas,
        reported_unit="%" if reported_total_gas is not None else None,
        comment=f"{event_type.value} interval",
        source="operator",
    )


def test_registry_allows_repeated_event_type_as_independent_rows() -> None:
    first = _event("connection-1", GasContextEventType.CONNECTION_GAS, 1000.0, 1002.0)
    second = _event("connection-2", GasContextEventType.CONNECTION_GAS, 1200.0, 1203.0)

    registry = GasContextRegistry((first, second))

    assert registry.events == (first, second)
    assert registry.resolve_at_depth(1001.0) is first
    assert registry.resolve_at_depth(1201.0) is second


def test_registry_ignores_draft_and_resolves_confirmed_test_over_formation() -> None:
    formation = _event(
        "formation-1",
        GasContextEventType.FORMATION_SHOW,
        2000.0,
        2010.0,
    )
    draft_test = _event(
        "test-draft",
        GasContextEventType.GAS_LINE_TEST_GAS,
        2004.0,
        2006.0,
        confirmed=False,
    )
    confirmed_test = _event(
        "test-confirmed",
        GasContextEventType.GAS_LINE_TEST_GAS,
        2004.0,
        2006.0,
    )
    registry = GasContextRegistry((formation, draft_test, confirmed_test))

    resolved = registry.resolve_at_depth(2005.0)

    assert resolved is confirmed_test
    assert resolved.effective_impact is InterpretationImpact.EXCLUDE_GEOLOGICAL


def test_technological_event_default_impact_preserves_reported_qc_reference() -> None:
    event = _event(
        "swab-1",
        GasContextEventType.SWAB_GAS,
        2500.0,
        2505.0,
        reported_total_gas=8.4,
    )

    assert event.effective_impact is InterpretationImpact.TECHNOLOGICAL_GAS
    assert event.reported_total_gas == 8.4
    assert event.reported_unit == "%"


def test_project_v35_round_trip_preserves_repeating_gas_context_events(
    tmp_path: Path,
) -> None:
    well = Well(
        "well-1",
        "Well 1",
        gas_context_events=[
            _event(
                "connection-1",
                GasContextEventType.CONNECTION_GAS,
                1000.0,
                1002.0,
                reported_total_gas=3.2,
            ),
            _event(
                "connection-2",
                GasContextEventType.CONNECTION_GAS,
                1200.0,
                1203.0,
                reported_total_gas=4.1,
            ),
            _event(
                "gas-line-test-1",
                GasContextEventType.GAS_LINE_TEST_GAS,
                1500.0,
                1501.0,
                impact=InterpretationImpact.EXCLUDE_GEOLOGICAL,
            ),
        ],
    )
    project = Project("project-1", "Project", wells={well.well_id: well})
    target = tmp_path / "gas-context.geologpkg"

    save_project(project, target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    restored = load_project(target).wells["well-1"]

    assert PROJECT_FORMAT_VERSION == 35
    assert payload["format_version"] == 35
    assert len(payload["project"]["wells"]["well-1"]["gas_context_events"]) == 3
    assert [event.event_id for event in restored.gas_context_events] == [
        "connection-1",
        "connection-2",
        "gas-line-test-1",
    ]
    assert restored.gas_context_events[0].reported_total_gas == 3.2
    assert restored.gas_context_events[2].effective_impact is InterpretationImpact.EXCLUDE_GEOLOGICAL


def test_v34_project_loads_with_empty_gas_context_registry(tmp_path: Path) -> None:
    project = Project(
        "project-1",
        "Project",
        wells={"well-1": Well("well-1", "Well 1")},
    )
    target = tmp_path / "legacy-v34.geologpkg"
    save_project(project, target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["format_version"] = 34
    payload["project"]["wells"]["well-1"].pop("gas_context_events", None)

    restored = project_document_from_dict(payload).project.wells["well-1"]

    assert restored.gas_context_events == []


def test_v35_rejects_duplicate_event_ids(tmp_path: Path) -> None:
    project = Project(
        "project-1",
        "Project",
        wells={"well-1": Well("well-1", "Well 1")},
    )
    target = tmp_path / "duplicate.geologpkg"
    save_project(project, target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    duplicate = {
        "event_id": "dup",
        "event_type": "trip_gas",
        "top_depth": 1000.0,
        "bottom_depth": 1001.0,
        "impact": None,
        "confirmed": True,
        "reported_total_gas": None,
        "reported_unit": None,
        "comment": "",
        "source": "manual",
    }
    payload["project"]["wells"]["well-1"]["gas_context_events"] = [
        duplicate,
        dict(duplicate),
    ]

    with pytest.raises(ProjectFormatError, match="не должны повторяться"):
        project_document_from_dict(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("event_type", "unknown"),
        ("impact", "unknown"),
        ("confirmed", "yes"),
        ("bottom_depth", -1.0),
        ("reported_total_gas", -0.1),
    ],
)
def test_v35_rejects_invalid_gas_context_event(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    project = Project(
        "project-1",
        "Project",
        wells={"well-1": Well("well-1", "Well 1")},
    )
    target = tmp_path / "invalid.geologpkg"
    save_project(project, target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    event = {
        "event_id": "event-1",
        "event_type": "trip_gas",
        "top_depth": 1000.0,
        "bottom_depth": 1001.0,
        "impact": None,
        "confirmed": True,
        "reported_total_gas": None,
        "reported_unit": None,
        "comment": "",
        "source": "manual",
    }
    event[field] = value
    payload["project"]["wells"]["well-1"]["gas_context_events"] = [event]

    with pytest.raises(ProjectFormatError, match="gas context event"):
        project_document_from_dict(payload)
