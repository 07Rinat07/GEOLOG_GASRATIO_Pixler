from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Protocol

from geoworkbench.project.session import ProjectSession


class SessionBound(Protocol):
    """Application controller whose active project is exposed as ``session``."""

    session: ProjectSession


ResetHook = Callable[[], None]


@dataclass(frozen=True, slots=True)
class SessionBinding:
    """One controller binding and the transient state that must be reset with it."""

    target: SessionBound
    reset_hooks: tuple[ResetHook, ...] = ()
    name: str = ""

    def bind(self, session: ProjectSession) -> int:
        self.target.session = session
        for reset in self.reset_hooks:
            reset()
        return len(self.reset_hooks)


@dataclass(frozen=True, slots=True)
class SessionBindingReport:
    bound_controllers: int
    executed_reset_hooks: int


@dataclass(slots=True)
class SessionBindingController:
    """Rebind all session-aware application controllers as one coordinated workflow.

    The class deliberately knows nothing about Qt or ``MainWindow``.  A project-open
    workflow registers long-lived controllers once, then supplies the newly loaded
    :class:`ProjectSession`.  Histories and selections are reset immediately after
    every target receives the new session, preventing commands from retaining
    references to objects from the previous project.
    """

    _bindings: list[SessionBinding] = field(default_factory=list)

    def register(
        self,
        target: SessionBound,
        *,
        reset_hooks: Iterable[ResetHook] = (),
        name: str = "",
    ) -> SessionBinding:
        binding = SessionBinding(target, tuple(reset_hooks), name.strip())
        self._bindings.append(binding)
        return binding

    @property
    def binding_names(self) -> tuple[str, ...]:
        return tuple(binding.name for binding in self._bindings if binding.name)

    def bind(self, session: ProjectSession) -> SessionBindingReport:
        if not isinstance(session, ProjectSession):
            raise TypeError("Ожидалась сессия проекта")
        reset_count = 0
        for binding in self._bindings:
            reset_count += binding.bind(session)
        return SessionBindingReport(len(self._bindings), reset_count)
