from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import isclose, isfinite

from geoworkbench.tablet.camera import TabletCamera, recommended_initial_span


class NavigationCommand(StrEnum):
    """Platform-neutral vertical navigation commands."""

    HOME = "home"
    END = "end"
    PAGE_UP = "page_up"
    PAGE_DOWN = "page_down"
    LINE_UP = "line_up"
    LINE_DOWN = "line_down"


@dataclass(slots=True)
class TabletNavigationCoordinator:
    """Coordinate tablet pan, zoom and keyboard movement without Qt widgets.

    ``TabletCamera`` owns range arithmetic. This coordinator owns user-command
    semantics, including the first wheel movement from a fully visible well.
    Keeping both concerns outside ``TabletView`` makes navigation independently
    testable and leaves the view responsible only for reading and applying Qt
    state.
    """

    camera: TabletCamera = field(default_factory=TabletCamera)

    def scroll(
        self,
        bounds: tuple[float, float],
        current: tuple[float, float],
        steps: float,
        *,
        is_time: bool = False,
        is_datetime: bool = False,
        unit: str = "",
    ) -> tuple[float, float]:
        if not isfinite(steps) or steps == 0:
            raise ValueError("Navigation steps must be finite and non-zero")
        domain, visible = self._synchronize(bounds, current)
        domain_span = domain[1] - domain[0]
        visible_span = visible[1] - visible[0]
        if isclose(
            visible_span,
            domain_span,
            rel_tol=0.0,
            abs_tol=max(domain_span, 1.0) * 1e-9,
        ):
            initial_span = recommended_initial_span(
                domain_span,
                is_time=is_time,
                is_datetime=is_datetime,
                unit=unit,
            )
            if initial_span < domain_span:
                if steps > 0:
                    visible = (domain[0], domain[0] + initial_span)
                else:
                    visible = (domain[1] - initial_span, domain[1])
                self._synchronize(domain, visible)
        return self.camera.pan_fraction(0.10 * float(steps))

    def zoom(
        self,
        bounds: tuple[float, float],
        current: tuple[float, float],
        factor: float,
        *,
        anchor: float | None = None,
    ) -> tuple[float, float]:
        if not isfinite(factor) or factor <= 0:
            raise ValueError("Navigation zoom factor must be finite and positive")
        self._synchronize(bounds, current)
        return self.camera.zoom(float(factor), anchor=anchor)

    def pan(
        self,
        bounds: tuple[float, float],
        current: tuple[float, float],
        delta: float,
    ) -> tuple[float, float]:
        if not isfinite(delta):
            raise ValueError("Navigation delta must be finite")
        self._synchronize(bounds, current)
        return self.camera.pan(float(delta))

    def navigate(
        self,
        bounds: tuple[float, float],
        current: tuple[float, float],
        command: NavigationCommand | str,
    ) -> tuple[float, float]:
        self._synchronize(bounds, current)
        normalized = (
            command
            if isinstance(command, NavigationCommand)
            else NavigationCommand(str(command))
        )
        if normalized is NavigationCommand.HOME:
            return self.camera.home()
        if normalized is NavigationCommand.END:
            return self.camera.end()
        fraction = {
            NavigationCommand.PAGE_UP: -0.9,
            NavigationCommand.PAGE_DOWN: 0.9,
            NavigationCommand.LINE_UP: -0.1,
            NavigationCommand.LINE_DOWN: 0.1,
        }[normalized]
        return self.camera.pan_fraction(fraction)

    def _synchronize(
        self,
        bounds: tuple[float, float],
        current: tuple[float, float],
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        if not all(isfinite(value) for value in (*bounds, *current)):
            raise ValueError("Navigation ranges must contain finite values")
        domain_values = sorted((float(bounds[0]), float(bounds[1])))
        visible_values = sorted((float(current[0]), float(current[1])))
        domain = (domain_values[0], domain_values[1])
        visible = (visible_values[0], visible_values[1])
        if domain[0] == domain[1] or visible[0] == visible[1]:
            raise ValueError("Navigation ranges must have a positive span")
        self.camera.set_domain(*domain, preserve_window=False)
        self.camera.set_visible_range(*visible)
        return domain, self.camera.range
