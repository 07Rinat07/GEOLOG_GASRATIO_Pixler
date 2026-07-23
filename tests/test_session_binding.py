from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from geoworkbench.domain.models import Project
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.session_binding import SessionBindingController


@dataclass
class FakeController:
    session: ProjectSession
    reset_events: list[str] = field(default_factory=list)

    def clear_history(self) -> None:
        self.reset_events.append("history")

    def clear_selection(self) -> None:
        self.reset_events.append("selection")


def test_session_binding_updates_every_controller_and_resets_transient_state() -> None:
    old = ProjectSession(project=Project("old", "Old"))
    new = ProjectSession(project=Project("new", "New"))
    first = FakeController(old)
    second = FakeController(old)
    bindings = SessionBindingController()
    bindings.register(
        first,
        reset_hooks=(first.clear_history, first.clear_selection),
        name="first",
    )
    bindings.register(second, reset_hooks=(second.clear_history,), name="second")

    report = bindings.bind(new)

    assert first.session is new
    assert second.session is new
    assert first.reset_events == ["history", "selection"]
    assert second.reset_events == ["history"]
    assert report.bound_controllers == 2
    assert report.executed_reset_hooks == 3
    assert bindings.binding_names == ("first", "second")


def test_session_binding_rejects_non_project_session() -> None:
    controller = FakeController(ProjectSession())
    bindings = SessionBindingController()
    bindings.register(controller)

    with pytest.raises(TypeError, match="сессия"):
        bindings.bind(object())  # type: ignore[arg-type]
