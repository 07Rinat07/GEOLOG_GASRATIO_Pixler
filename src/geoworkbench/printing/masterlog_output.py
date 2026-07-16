from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from geoworkbench.services.localization import AppLanguage


@dataclass(frozen=True, slots=True)
class MasterlogOutputSettings:
    depth_top: float
    depth_bottom: float
    language: AppLanguage = AppLanguage.RU

    def __post_init__(self) -> None:
        if (
            isinstance(self.depth_top, bool)
            or isinstance(self.depth_bottom, bool)
            or not isinstance(self.depth_top, (int, float))
            or not isinstance(self.depth_bottom, (int, float))
            or not isfinite(self.depth_top)
            or not isfinite(self.depth_bottom)
            or self.depth_bottom <= self.depth_top
        ):
            raise ValueError("Интервал masterlog должен иметь конечные top < bottom")
        if not isinstance(self.language, AppLanguage):
            raise ValueError("Язык masterlog должен быть RU, KK или EN")

    @property
    def depth_range(self) -> tuple[float, float]:
        return float(self.depth_top), float(self.depth_bottom)
