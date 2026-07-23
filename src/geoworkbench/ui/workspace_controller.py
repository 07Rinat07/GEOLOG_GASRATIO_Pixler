from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class WorkspaceSurface(StrEnum):
    HOME = "home"
    WORKSPACE = "workspace"


@dataclass(frozen=True, slots=True)
class WorkspaceState:
    surface: WorkspaceSurface
    dataset_name: str | None

    @property
    def workspace_available(self) -> bool:
        return self.dataset_name is not None


class WorkspacePort(Protocol):
    """UI operations required by the headless workspace controller."""

    def set_workspace_available(
        self,
        available: bool,
        dataset_name: str | None,
    ) -> None: ...

    def show_home(self) -> None: ...

    def show_workspace(self, target: object | None) -> None: ...

    def show_navigation_status(self, surface: WorkspaceSurface) -> None: ...


class WorkspaceController:
    """Own home/workspace navigation rules independently from Qt widgets."""

    def __init__(self, port: WorkspacePort) -> None:
        self._port = port
        self._surface = WorkspaceSurface.HOME
        self._dataset_name: str | None = None

    @property
    def state(self) -> WorkspaceState:
        return WorkspaceState(self._surface, self._dataset_name)

    def set_dataset(self, dataset_name: str | None) -> WorkspaceState:
        normalized = dataset_name.strip() if isinstance(dataset_name, str) else ""
        self._dataset_name = normalized or None
        self._port.set_workspace_available(
            self._dataset_name is not None,
            self._dataset_name,
        )
        if self._dataset_name is None:
            return self.show_home()
        return self.state

    def show_home(self) -> WorkspaceState:
        self._surface = WorkspaceSurface.HOME
        self._port.show_home()
        self._port.show_navigation_status(self._surface)
        return self.state

    def show_workspace(self, target: object | None = None) -> bool:
        if self._dataset_name is None:
            return False
        self._surface = WorkspaceSurface.WORKSPACE
        self._port.show_workspace(target)
        self._port.show_navigation_status(self._surface)
        return True
