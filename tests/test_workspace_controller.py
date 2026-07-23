from __future__ import annotations

from dataclasses import dataclass, field

from geoworkbench.ui.workspace_controller import (
    WorkspaceController,
    WorkspaceSurface,
)


@dataclass
class FakeWorkspacePort:
    availability: list[tuple[bool, str | None]] = field(default_factory=list)
    surfaces: list[WorkspaceSurface] = field(default_factory=list)
    targets: list[object | None] = field(default_factory=list)
    statuses: list[WorkspaceSurface] = field(default_factory=list)

    def set_workspace_available(
        self,
        available: bool,
        dataset_name: str | None,
    ) -> None:
        self.availability.append((available, dataset_name))

    def show_home(self) -> None:
        self.surfaces.append(WorkspaceSurface.HOME)

    def show_workspace(self, target: object | None) -> None:
        self.surfaces.append(WorkspaceSurface.WORKSPACE)
        self.targets.append(target)

    def show_navigation_status(self, surface: WorkspaceSurface) -> None:
        self.statuses.append(surface)


def test_workspace_is_unavailable_until_dataset_is_bound() -> None:
    port = FakeWorkspacePort()
    controller = WorkspaceController(port)

    assert controller.show_workspace("tablet") is False
    assert controller.state.workspace_available is False
    assert port.surfaces == []


def test_dataset_enables_workspace_and_preserves_requested_target() -> None:
    port = FakeWorkspacePort()
    controller = WorkspaceController(port)

    state = controller.set_dataset("  Dataset  ")
    opened = controller.show_workspace("tablet")

    assert state.dataset_name == "Dataset"
    assert opened is True
    assert controller.state.surface is WorkspaceSurface.WORKSPACE
    assert port.availability == [(True, "Dataset")]
    assert port.targets == ["tablet"]
    assert port.statuses == [WorkspaceSurface.WORKSPACE]


def test_removing_dataset_returns_to_home_and_disables_workspace() -> None:
    port = FakeWorkspacePort()
    controller = WorkspaceController(port)
    controller.set_dataset("Dataset")
    controller.show_workspace()

    state = controller.set_dataset(None)

    assert state.surface is WorkspaceSurface.HOME
    assert state.workspace_available is False
    assert port.availability[-1] == (False, None)
    assert port.surfaces[-1] is WorkspaceSurface.HOME
    assert port.statuses[-1] is WorkspaceSurface.HOME
