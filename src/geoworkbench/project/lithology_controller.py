from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from geoworkbench.domain.models import LithologyInterval, Well, new_id
from geoworkbench.project.session import ProjectSession


@dataclass(slots=True)
class LithologyController:
    session: ProjectSession

    def available(self) -> tuple[LithologyInterval, ...]:
        return tuple(
            sorted(
                self._require_well().lithology,
                key=lambda item: (item.top_depth, item.bottom_depth, item.interval_id),
            )
        )

    def get(self, interval_id: str) -> LithologyInterval:
        return self._require_interval(interval_id)

    def add(
        self,
        top_depth: float,
        bottom_depth: float,
        lithotype_id: str,
        *,
        description: str | None = None,
    ) -> LithologyInterval:
        top, bottom, lithotype, normalized_description = self._validate(
            top_depth,
            bottom_depth,
            lithotype_id,
            description,
        )
        self._ensure_no_overlap(top, bottom)
        interval = LithologyInterval(
            interval_id=new_id(),
            top_depth=top,
            bottom_depth=bottom,
            lithotype_id=lithotype,
            description=normalized_description,
        )
        self._require_well().lithology.append(interval)
        self.session.dirty = True
        return interval

    def update(
        self,
        interval_id: str,
        *,
        top_depth: float,
        bottom_depth: float,
        lithotype_id: str,
        description: str | None = None,
    ) -> LithologyInterval:
        interval = self._require_interval(interval_id)
        top, bottom, lithotype, normalized_description = self._validate(
            top_depth,
            bottom_depth,
            lithotype_id,
            description,
        )
        self._ensure_no_overlap(top, bottom, excluded_id=interval_id)
        interval.top_depth = top
        interval.bottom_depth = bottom
        interval.lithotype_id = lithotype
        interval.description = normalized_description
        self.session.dirty = True
        return interval

    def remove(self, interval_id: str) -> LithologyInterval:
        well = self._require_well()
        interval = self._require_interval(interval_id)
        well.lithology.remove(interval)
        self.session.dirty = True
        return interval

    def _validate(
        self,
        top_depth: float,
        bottom_depth: float,
        lithotype_id: str,
        description: str | None,
    ) -> tuple[float, float, str, str | None]:
        top = float(top_depth)
        bottom = float(bottom_depth)
        if not np.isfinite(top) or not np.isfinite(bottom):
            raise ValueError("Границы литологического интервала должны быть конечными")
        if top >= bottom:
            raise ValueError("Кровля интервала должна быть меньше подошвы")
        lithotype = lithotype_id.strip()
        if not lithotype:
            raise ValueError("Идентификатор литотипа не может быть пустым")
        if len(lithotype) > 100:
            raise ValueError("Идентификатор литотипа не должен превышать 100 символов")
        normalized_description = description.strip() if description else None
        if normalized_description and len(normalized_description) > 4000:
            raise ValueError("Описание литологии не должно превышать 4000 символов")
        dataset = self.session.current_dataset
        if dataset is not None:
            finite_depth = dataset.depth[np.isfinite(dataset.depth)]
            if finite_depth.size and (
                top < float(np.min(finite_depth)) or bottom > float(np.max(finite_depth))
            ):
                raise ValueError("Литологический интервал выходит за диапазон dataset")
        return top, bottom, lithotype, normalized_description

    def _ensure_no_overlap(
        self,
        top: float,
        bottom: float,
        *,
        excluded_id: str | None = None,
    ) -> None:
        for interval in self._require_well().lithology:
            if interval.interval_id == excluded_id:
                continue
            if top < interval.bottom_depth and bottom > interval.top_depth:
                raise ValueError(
                    f"Интервал пересекается с существующим: "
                    f"{interval.top_depth:g}–{interval.bottom_depth:g}"
                )

    def _require_well(self) -> Well:
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Сначала выберите скважину")
        return well

    def _require_interval(self, interval_id: str) -> LithologyInterval:
        for interval in self._require_well().lithology:
            if interval.interval_id == interval_id:
                return interval
        raise KeyError(f"Литологический интервал не найден: {interval_id}")
