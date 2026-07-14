from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DepthViewport:
    minimum_depth: float = 0.0
    maximum_depth: float = 100.0
    visible_top: float = 0.0
    visible_bottom: float = 100.0

    def set_domain(self, minimum: float, maximum: float) -> None:
        if maximum <= minimum:
            raise ValueError("Максимальная глубина должна быть больше минимальной")
        self.minimum_depth = float(minimum)
        self.maximum_depth = float(maximum)
        self.visible_top = max(self.minimum_depth, min(self.visible_top, self.maximum_depth))
        self.visible_bottom = max(self.visible_top, min(self.visible_bottom, self.maximum_depth))
        if self.visible_bottom <= self.visible_top:
            self.visible_top = self.minimum_depth
            self.visible_bottom = self.maximum_depth

    def set_visible_range(self, top: float, bottom: float) -> None:
        if bottom <= top:
            raise ValueError("Нижняя граница должна быть глубже верхней")
        span = bottom - top
        domain_span = self.maximum_depth - self.minimum_depth
        if span >= domain_span:
            self.visible_top = self.minimum_depth
            self.visible_bottom = self.maximum_depth
            return
        top = max(self.minimum_depth, min(top, self.maximum_depth - span))
        self.visible_top = top
        self.visible_bottom = top + span

    def pan(self, delta_depth: float) -> None:
        self.set_visible_range(
            self.visible_top + delta_depth,
            self.visible_bottom + delta_depth,
        )

    def zoom(self, factor: float, anchor_depth: float | None = None) -> None:
        if factor <= 0:
            raise ValueError("Коэффициент масштаба должен быть положительным")
        anchor = (
            (self.visible_top + self.visible_bottom) / 2.0
            if anchor_depth is None
            else float(anchor_depth)
        )
        old_span = self.visible_bottom - self.visible_top
        new_span = max((self.maximum_depth - self.minimum_depth) / 10000.0, old_span / factor)
        new_span = min(new_span, self.maximum_depth - self.minimum_depth)
        relative = 0.5 if old_span == 0 else (anchor - self.visible_top) / old_span
        top = anchor - relative * new_span
        self.set_visible_range(top, top + new_span)
