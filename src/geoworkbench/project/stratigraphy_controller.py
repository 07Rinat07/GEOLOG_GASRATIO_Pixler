from __future__ import annotations

from dataclasses import dataclass
import re

import numpy as np

from geoworkbench.domain.models import StratigraphyInterval, Well, new_id
from geoworkbench.project.session import ProjectSession


STRATIGRAPHY_RANKS = (
    "Eonothem / Eon",
    "Erathem / Era",
    "System / Period",
    "Series / Epoch",
    "Stage / Age",
    "Formation",
    "Member",
    "Bed",
)


def stratigraphy_rank_order(rank: str | None) -> tuple[int, str]:
    normalized = (rank or "").strip()
    try:
        return STRATIGRAPHY_RANKS.index(normalized), normalized.casefold()
    except ValueError:
        return len(STRATIGRAPHY_RANKS), normalized.casefold()


@dataclass(slots=True)
class StratigraphyController:
    session: ProjectSession

    def available(self) -> tuple[StratigraphyInterval, ...]:
        return tuple(
            sorted(
                self._require_well().stratigraphy,
                key=lambda item: (
                    stratigraphy_rank_order(item.rank),
                    item.top_depth,
                    item.bottom_depth,
                    item.interval_id,
                ),
            )
        )

    def add(
        self,
        top_depth: float,
        bottom_depth: float,
        code: str,
        *,
        name: str | None = None,
        rank: str | None = None,
        color: str = "#dbeafe",
        description: str | None = None,
    ) -> StratigraphyInterval:
        values = self._validate(top_depth, bottom_depth, code, name, rank, color, description)
        self._ensure_no_overlap(values[0], values[1], values[4])
        interval = StratigraphyInterval(new_id(), *values)
        self._require_well().stratigraphy.append(interval)
        self.session.dirty = True
        return interval

    def update(
        self,
        interval_id: str,
        *,
        top_depth: float,
        bottom_depth: float,
        code: str,
        name: str | None = None,
        rank: str | None = None,
        color: str = "#dbeafe",
        description: str | None = None,
    ) -> StratigraphyInterval:
        interval = self._require_interval(interval_id)
        values = self._validate(top_depth, bottom_depth, code, name, rank, color, description)
        self._ensure_no_overlap(values[0], values[1], values[4], excluded_id=interval_id)
        (
            interval.top_depth,
            interval.bottom_depth,
            interval.code,
            interval.name,
            interval.rank,
            interval.color,
            interval.description,
        ) = values
        self.session.dirty = True
        return interval

    def remove(self, interval_id: str) -> StratigraphyInterval:
        interval = self._require_interval(interval_id)
        self._require_well().stratigraphy.remove(interval)
        self.session.dirty = True
        return interval

    def _validate(
        self,
        top_depth: float,
        bottom_depth: float,
        code: str,
        name: str | None,
        rank: str | None,
        color: str,
        description: str | None,
    ) -> tuple[float, float, str, str | None, str | None, str, str | None]:
        top, bottom = float(top_depth), float(bottom_depth)
        if not np.isfinite(top) or not np.isfinite(bottom) or top >= bottom:
            raise ValueError("Кровля стратиграфического интервала должна быть меньше подошвы")
        normalized_code = code.strip()
        if not normalized_code or len(normalized_code) > 100:
            raise ValueError(
                "Код стратиграфического интервала обязателен и не длиннее 100 символов"
            )
        normalized_name = self._optional_text(name, 300, "Название")
        normalized_rank = self._optional_text(rank, 100, "Ранг")
        normalized_color = color.strip().lower()
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", normalized_color):
            raise ValueError("Цвет стратиграфии должен быть в формате #RRGGBB")
        normalized_description = self._optional_text(description, 4000, "Описание")
        dataset = self.session.current_dataset
        if dataset is not None:
            finite = dataset.depth[np.isfinite(dataset.depth)]
            if finite.size and (top < float(np.min(finite)) or bottom > float(np.max(finite))):
                raise ValueError("Стратиграфический интервал выходит за диапазон dataset")
        return (
            top,
            bottom,
            normalized_code,
            normalized_name,
            normalized_rank,
            normalized_color,
            normalized_description,
        )

    @staticmethod
    def _optional_text(value: str | None, maximum: int, label: str) -> str | None:
        normalized = value.strip() if value else None
        if normalized and len(normalized) > maximum:
            raise ValueError(f"{label} не должно превышать {maximum} символов")
        return normalized

    def _ensure_no_overlap(
        self,
        top: float,
        bottom: float,
        rank: str | None,
        *,
        excluded_id: str | None = None,
    ) -> None:
        rank_key = (rank or "").strip().casefold()
        for interval in self._require_well().stratigraphy:
            existing_rank_key = (interval.rank or "").strip().casefold()
            if interval.interval_id == excluded_id or existing_rank_key != rank_key:
                continue
            if top < interval.bottom_depth and bottom > interval.top_depth:
                raise ValueError(
                    f"Интервал пересекается с {interval.code} того же ранга: "
                    f"{interval.top_depth:g}–{interval.bottom_depth:g} м"
                )

    def _require_well(self) -> Well:
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Сначала выберите скважину")
        return well

    def _require_interval(self, interval_id: str) -> StratigraphyInterval:
        for interval in self._require_well().stratigraphy:
            if interval.interval_id == interval_id:
                return interval
        raise KeyError(f"Стратиграфический интервал не найден: {interval_id}")
