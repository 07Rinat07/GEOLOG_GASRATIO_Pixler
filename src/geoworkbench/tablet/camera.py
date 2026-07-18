from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TabletCamera:
    """Single source of truth for tablet vertical navigation.

    Coordinates are axis values, so the same model works for MD/TVD/TVDSS,
    relative time, and absolute timestamp axes.
    """

    domain_top: float = 0.0
    domain_bottom: float = 100.0
    visible_top: float = 0.0
    visible_bottom: float = 100.0
    minimum_span_ratio: float = 1.0 / 100_000.0

    @property
    def domain_span(self) -> float:
        return self.domain_bottom - self.domain_top

    @property
    def visible_span(self) -> float:
        return self.visible_bottom - self.visible_top

    @property
    def center(self) -> float:
        return (self.visible_top + self.visible_bottom) / 2.0

    def set_domain(self, top: float, bottom: float, *, preserve_window: bool = True) -> None:
        top, bottom = sorted((float(top), float(bottom)))
        if bottom <= top:
            raise ValueError("Camera domain must have a positive span")
        old_top, old_bottom = self.visible_top, self.visible_bottom
        self.domain_top = top
        self.domain_bottom = bottom
        if preserve_window:
            self.set_visible_range(old_top, old_bottom)
        else:
            self.show_all()

    def show_all(self) -> tuple[float, float]:
        self.visible_top = self.domain_top
        self.visible_bottom = self.domain_bottom
        return self.range

    @property
    def range(self) -> tuple[float, float]:
        return self.visible_top, self.visible_bottom

    def set_visible_range(self, top: float, bottom: float) -> tuple[float, float]:
        top, bottom = sorted((float(top), float(bottom)))
        requested_span = bottom - top
        if requested_span <= 0:
            raise ValueError("Camera visible range must have a positive span")
        domain_span = self.domain_span
        if requested_span >= domain_span:
            return self.show_all()
        minimum_span = max(domain_span * self.minimum_span_ratio, 1e-12)
        span = max(requested_span, minimum_span)
        top = max(self.domain_top, min(top, self.domain_bottom - span))
        self.visible_top = top
        self.visible_bottom = top + span
        return self.range

    def pan(self, delta: float) -> tuple[float, float]:
        return self.set_visible_range(
            self.visible_top + float(delta),
            self.visible_bottom + float(delta),
        )

    def pan_fraction(self, fraction: float) -> tuple[float, float]:
        return self.pan(self.visible_span * float(fraction))

    def zoom(self, factor: float, *, anchor: float | None = None) -> tuple[float, float]:
        """Scale visible span by ``factor`` while keeping ``anchor`` stationary.

        ``factor < 1`` zooms in and ``factor > 1`` zooms out.
        """
        factor = float(factor)
        if factor <= 0:
            raise ValueError("Camera zoom factor must be positive")
        anchor_value = self.center if anchor is None else float(anchor)
        old_span = self.visible_span
        relative = 0.5 if old_span <= 0 else (anchor_value - self.visible_top) / old_span
        relative = max(0.0, min(1.0, relative))
        new_span = old_span * factor
        top = anchor_value - relative * new_span
        return self.set_visible_range(top, top + new_span)

    def go_to(self, value: float) -> tuple[float, float]:
        value = float(value)
        half = self.visible_span / 2.0
        return self.set_visible_range(value - half, value + half)

    def home(self) -> tuple[float, float]:
        span = self.visible_span
        return self.set_visible_range(self.domain_top, self.domain_top + span)

    def end(self) -> tuple[float, float]:
        span = self.visible_span
        return self.set_visible_range(self.domain_bottom - span, self.domain_bottom)
