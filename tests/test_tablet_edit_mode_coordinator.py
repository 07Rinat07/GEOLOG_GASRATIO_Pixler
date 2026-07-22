from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.tablet.edit_mode_coordinator import TabletEditModeCoordinator


@dataclass
class FakeAnnotationMode:
    enabled: bool = False
    tool: object | None = None

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def set_creation_tool(self, tool: object | None) -> None:
        self.tool = tool


@dataclass
class FakeTrackMode:
    enabled: bool = False
    suspended: bool = False

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def set_suspended(self, suspended: bool) -> None:
        self.suspended = suspended


def test_f4_enables_annotation_and_track_tools_together() -> None:
    annotation = FakeAnnotationMode()
    track = FakeTrackMode()
    coordinator = TabletEditModeCoordinator(annotation, track)

    state = coordinator.set_form_edit_enabled(True)

    assert state.form_edit_enabled is True
    assert annotation.enabled is True
    assert track.enabled is True
    assert track.suspended is False


def test_creation_tool_temporarily_suspends_only_track_creation_clicks() -> None:
    annotation = FakeAnnotationMode()
    track = FakeTrackMode()
    coordinator = TabletEditModeCoordinator(annotation, track)
    coordinator.set_form_edit_enabled(True)

    state = coordinator.set_annotation_tool("comment")

    assert state.annotation_tool == "comment"
    assert annotation.tool == "comment"
    assert track.enabled is True
    assert track.suspended is True

    restored = coordinator.cancel_annotation_tool()
    assert restored.annotation_tool is None
    assert track.enabled is True
    assert track.suspended is False


def test_disabling_f4_always_disarms_tool_and_restores_invariants() -> None:
    annotation = FakeAnnotationMode()
    track = FakeTrackMode()
    coordinator = TabletEditModeCoordinator(annotation, track)
    coordinator.set_form_edit_enabled(True)
    coordinator.set_annotation_tool("callout")

    state = coordinator.set_form_edit_enabled(False)

    assert state.annotation_tool is None
    assert annotation.enabled is False
    assert annotation.tool is None
    assert track.enabled is False
    assert track.suspended is False


def test_tool_cannot_be_armed_outside_f4() -> None:
    annotation = FakeAnnotationMode()
    track = FakeTrackMode()
    coordinator = TabletEditModeCoordinator(annotation, track)

    state = coordinator.set_annotation_tool("image")

    assert state.annotation_tool is None
    assert annotation.tool is None
    assert track.suspended is False
